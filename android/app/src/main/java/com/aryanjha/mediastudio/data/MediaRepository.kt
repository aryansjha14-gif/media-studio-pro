package com.aryanjha.mediastudio.data

import android.content.Context
import android.net.Uri
import android.provider.OpenableColumns
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.toRequestBody

class MediaRepository(
    private val holder: ApiHolder,
    private val settings: SettingsStore,
    private val context: Context,
) {

    private fun api(): MediaApi = holder.api()

    /** Current backend URL, shown in Settings. */
    fun baseUrl(): String = holder.baseUrl()

    /** Point the app at a different server without rebuilding. */
    fun updateBaseUrl(url: String) {
        holder.setBaseUrl(url)
        settings.baseUrl = holder.baseUrl()
    }

    /** Upload a picked image/video and get back the asset to edit. */
    suspend fun upload(uri: Uri): MediaAsset = withContext(Dispatchers.IO) {
        val resolver = context.contentResolver
        val mime = resolver.getType(uri) ?: "application/octet-stream"
        val name = queryDisplayName(uri) ?: "upload_${System.currentTimeMillis()}"
        val bytes = resolver.openInputStream(uri)?.use { it.readBytes() }
            ?: error("Could not read the selected file")

        val part = MultipartBody.Part.createFormData(
            "file",
            name,
            bytes.toRequestBody(mime.toMediaTypeOrNull()),
        )
        api().upload(part)
    }

    private fun queryDisplayName(uri: Uri): String? {
        val projection = arrayOf(OpenableColumns.DISPLAY_NAME)
        return context.contentResolver.query(uri, projection, null, null, null)?.use { cursor ->
            if (cursor.moveToFirst()) cursor.getString(0) else null
        }
    }

    /**
     * Poll a job until it finishes. AI calls take 5-60s, so the client shows a
     * progress state instead of blocking a single request.
     */
    suspend fun awaitJob(
        jobId: String,
        timeoutMs: Long = 10 * 60 * 1000,
        onUpdate: (Job) -> Unit = {},
    ): Job {
        var waited = 0L
        val stepMs = 1200L
        while (waited < timeoutMs) {
            val job = api().job(jobId)
            onUpdate(job)
            if (job.isDone) return job
            delay(stepMs)
            waited += stepMs
        }
        error("Timed out waiting for the job to finish")
    }

    // -- instant edits (no AI, no job) ------------------------------------ //
    suspend fun adjust(assetId: String, body: AdjustRequest): MediaAsset = api().adjust(assetId, body)

    suspend fun trim(assetId: String, body: TrimRequest): MediaAsset = api().trim(assetId, body)

    suspend fun extractFrame(assetId: String, body: FrameRequest): MediaAsset = api().frame(assetId, body)

    // -- AI edits (job-based) --------------------------------------------- //
    suspend fun promptEdit(assetId: String, prompt: String): Job =
        api().promptEdit(assetId, PromptEditRequest(prompt = prompt))

    suspend fun upscale(assetId: String, factor: Float = 2f): Job = api().upscale(assetId, factor)

    suspend fun removeBackground(assetId: String): Job = api().removeBackground(assetId)

    suspend fun generateImage(prompt: String): Job =
        api().generateImage(GenerateImageRequest(prompt = prompt))

    suspend fun restyleVideo(assetId: String, prompt: String): Job =
        api().videoPrompt(assetId, VideoPromptRequest(prompt = prompt))

    suspend fun generateVideo(prompt: String, duration: Int = 5): Job =
        api().generateVideo(GenerateVideoRequest(prompt = prompt, duration = duration))

    /** Run an AI call that returns a Job, then wait for its asset. */
    suspend fun runJob(
        onUpdate: (Job) -> Unit = {},
        start: suspend () -> Job,
    ): MediaAsset {
        val job = start()
        onUpdate(job)
        val finished = awaitJob(job.id, onUpdate = onUpdate)
        return finished.asset
            ?: error(finished.error ?: "The job finished without producing media")
    }

    suspend fun health(): HealthResponse = api().health()

    /**
     * Upload any size of file, in chunks, with resume.
     *
     * The single-shot upload endpoint reads the whole file into memory, which is
     * fine for a photo and impossible for a 20 GB video. This streams the file in
     * 16 MB pieces and resumes from whatever the server already has, so a dropped
     * connection does not restart the transfer.
     */
    suspend fun uploadLarge(
        uri: Uri,
        onProgress: (sent: Long, total: Long) -> Unit = { _, _ -> },
    ): MediaAsset = withContext(Dispatchers.IO) {
        val resolver = context.contentResolver
        val mime = resolver.getType(uri) ?: "application/octet-stream"
        val name = queryDisplayName(uri) ?: "upload_${System.currentTimeMillis()}"
        val total = resolver.openAssetFileDescriptor(uri, "r")?.use { it.length } ?: -1L
        require(total > 0) { "Could not determine the file size" }

        val session = api().uploadInit(UploadInitRequest(name, total, mime))
        val chunkSize = session.chunk_size.toInt().coerceAtLeast(256 * 1024)

        var offset = session.received
        resolver.openInputStream(uri)?.use { input ->
            var skipped = 0L
            while (skipped < offset) {
                val step = input.skip(offset - skipped)
                if (step <= 0) break
                skipped += step
            }
            val buffer = ByteArray(chunkSize)
            while (offset < total) {
                val read = input.read(buffer)
                if (read <= 0) break
                val piece = buffer.copyOf(read)
                val body = piece.toRequestBody(mime.toMediaTypeOrNull())
                val state = api().uploadChunk(session.upload_id, offset, body)
                offset = state.received
                onProgress(offset, total)
            }
        } ?: error("Could not open the selected file")

        api().uploadComplete(session.upload_id)
    }

    /** Analyse the footage and return the proposed edit, without rendering. */
    suspend fun planAutoEdit(
        prompt: String,
        mediaIds: List<String>,
        musicMediaId: String? = null,
        width: Int = 1920,
        height: Int = 1080,
    ): AutoPlan = api().autoPlan(PlanRequest(prompt, mediaIds, musicMediaId, width, height))

    /** Render an approved plan. Long job; poll with awaitJob. */
    suspend fun renderAutoEdit(plan: AutoPlan, musicMediaId: String? = null): Job =
        api().autoRender(RenderRequest(plan, musicMediaId))

    suspend fun featureSummary(): FeatureSummary = api().featureSummary()

    // -- creator packs, lenses, search ------------------------------------ //
    suspend fun platforms(): List<PlatformPreset> = api().platforms()

    suspend fun lenses(): List<LensInfo> = api().lenses()

    suspend fun searchFeatures(query: String): List<FeatureItem> =
        if (query.isBlank()) emptyList() else api().searchFeatures(query)

    suspend fun fitPlatform(asset: MediaAsset, platform: String): MediaAsset =
        if (asset.isVideo) {
            runJob { api().fitPlatformVideo(platform, asset.id) }
        } else {
            api().fitPlatformImage(platform, asset.id)
        }

    suspend fun applyLens(asset: MediaAsset, lens: String, intensity: Float = 1f): MediaAsset =
        if (asset.isVideo) {
            runJob { api().applyLensVideo(lens, asset.id) }
        } else {
            api().applyLensImage(lens, asset.id, intensity)
        }

    suspend fun addSticker(asset: MediaAsset, text: String, style: String = "caption"): MediaAsset =
        api().addSticker(asset.id, StickerRequest(text, style))

    // -- Canva / Runway / Veed packs --------------------------------------- //
    suspend fun magicResize(asset: MediaAsset, platforms: List<String>): List<MediaAsset> =
        api().magicResize(asset.id, MagicResizeRequest(platforms))

    suspend fun applyBrand(
        asset: MediaAsset, headline: String, subline: String, colour: String,
    ): MediaAsset = api().applyBrand(asset.id, BrandRequest(headline, subline, colour))

    suspend fun burnSubtitles(asset: MediaAsset, srt: String): MediaAsset =
        runJob { api().burnSubtitles(asset.id, SubtitleRequest(srt)) }

    suspend fun chromaKey(asset: MediaAsset, colour: String): MediaAsset =
        runJob { api().chromaKey(asset.id, ChromaRequest(colour)) }

    suspend fun cameraMotion(asset: MediaAsset, motion: String): MediaAsset =
        runJob { api().cameraMotion(asset.id, MotionRequest(motion)) }

    suspend fun denoiseAudio(asset: MediaAsset): MediaAsset =
        runJob { api().denoiseAudio(asset.id) }

    suspend fun addProgressBar(asset: MediaAsset, colour: String): MediaAsset =
        runJob { api().progressBar(asset.id, ProgressRequest(colour)) }
}
