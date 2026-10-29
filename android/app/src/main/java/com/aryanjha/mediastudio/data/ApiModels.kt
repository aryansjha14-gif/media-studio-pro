package com.aryanjha.mediastudio.data

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonObject

// Mirrors backend/app/schemas.py. Keep the two in sync (docs/API.md is the contract).

@Serializable
data class MediaAsset(
    val id: String,
    val kind: String,                       // "image" | "video"
    val url: String,
    @SerialName("thumb_url") val thumbUrl: String? = null,
    val width: Int? = null,
    val height: Int? = null,
    val duration: Double? = null,
    @SerialName("size_bytes") val sizeBytes: Long? = null,
    val mime: String? = null,
    val meta: JsonObject? = null,
) {
    val isImage: Boolean get() = kind == "image"
    val isVideo: Boolean get() = kind == "video"
}

@Serializable
data class Job(
    val id: String,
    val kind: String,
    val status: String,                     // queued | running | succeeded | failed
    val progress: Float = 0f,
    val asset: MediaAsset? = null,
    val error: String? = null,
) {
    val isDone: Boolean get() = status == "succeeded" || status == "failed"
    val isSuccess: Boolean get() = status == "succeeded"
}

@Serializable
data class CropBox(val x: Int, val y: Int, val width: Int, val height: Int)

@Serializable
data class ResizeSpec(val width: Int? = null, val height: Int? = null, val fit: String = "cover")

@Serializable
data class AdjustRequest(
    val crop: CropBox? = null,
    val rotate: Double? = null,
    @SerialName("flip_horizontal") val flipHorizontal: Boolean = false,
    @SerialName("flip_vertical") val flipVertical: Boolean = false,
    val resize: ResizeSpec? = null,
    val brightness: Float = 1f,
    val contrast: Float = 1f,
    val saturation: Float = 1f,
    val sharpness: Float = 1f,
    val blur: Float = 0f,
    val filter: String = "none",
    val quality: Int = 92,
)

@Serializable
data class PromptEditRequest(
    val prompt: String,
    @SerialName("mask_media_id") val maskMediaId: String? = null,
    @SerialName("negative_prompt") val negativePrompt: String? = null,
)

@Serializable
data class GenerateImageRequest(
    val prompt: String,
    @SerialName("negative_prompt") val negativePrompt: String? = null,
    val width: Int = 1024,
    val height: Int = 1024,
    val steps: Int = 4,
)

@Serializable
data class TrimRequest(val start: Double, val end: Double, val reencode: Boolean = true)

@Serializable
data class FrameRequest(val at: Double)

@Serializable
data class VideoPromptRequest(
    val prompt: String,
    @SerialName("negative_prompt") val negativePrompt: String? = null,
)

@Serializable
data class GenerateVideoRequest(
    val prompt: String,
    @SerialName("negative_prompt") val negativePrompt: String? = null,
    val duration: Int = 5,
    @SerialName("aspect_ratio") val aspectRatio: String = "16:9",
)

@Serializable
data class HealthResponse(val status: String, val provider: String = "unknown")

// --------------------------------------------------------------------------- //
// v2: resumable uploads, prompt planning, feature coverage
// --------------------------------------------------------------------------- //

@Serializable
data class UploadSessionOut(
    val upload_id: String,
    val received: Long,
    val total_bytes: Long,
    val chunk_size: Long,
    val complete: Boolean,
)

@Serializable
data class PlanSegment(
    val source_id: String,
    val start: Double,
    val end: Double,
    val order: Int,
    val title: String? = null,
    val motion: String = "kenburns",
    val quality: Float = 1f,
    val note: String? = null,
)

@Serializable
data class SkippedSegment(val source_id: String, val reason: String)

@Serializable
data class AutoPlan(
    val version: Int = 1,
    val prompt: String,
    val width: Int = 1920,
    val height: Int = 1080,
    val fps: Int = 30,
    val segments: List<PlanSegment> = emptyList(),
    val skipped: List<SkippedSegment> = emptyList(),
    val transitions: Map<String, String> = emptyMap(),
    val audio: Map<String, String?> = emptyMap(),
    val cards: Map<String, String?> = emptyMap(),
    val grade: Map<String, String> = emptyMap(),
    val estimated_seconds: Double = 0.0,
    val warnings: List<String> = emptyList(),
) {
    val shotCount: Int get() = segments.size
    val totalSeconds: Double get() = estimated_seconds
}

@Serializable
data class PlanRequest(
    val prompt: String,
    val media_ids: List<String>,
    val music_media_id: String? = null,
    val width: Int = 1920,
    val height: Int = 1080,
    val fps: Int = 30,
)

@Serializable
data class RenderRequest(val plan: AutoPlan, val music_media_id: String? = null)

@Serializable
data class FeatureSummary(
    val total: Int,
    val implemented: Int,
    val planned: Int,
)


@Serializable
data class UploadInitRequest(
    val filename: String,
    val total_bytes: Long,
    val mime: String? = null,
)

// --------------------------------------------------------------------------- //
// v4: creator platform packs, lenses, function search
// --------------------------------------------------------------------------- //

@Serializable
data class PlatformPreset(
    val name: String,
    val label: String,
    val width: Int,
    val height: Int,
    val aspect: String,
    val notes: String? = null,
) {
    val frame: String get() = "${width}x${height} · $aspect"
}

@Serializable
data class LensInfo(val name: String, val description: String)

@Serializable
data class FeatureItem(
    val id: String,
    val module: String,
    @SerialName("module_title") val moduleTitle: String,
    val name: String,
    val note: String,
    val status: String,
) {
    val isImplemented: Boolean get() = status == "implemented"
}

@Serializable
data class StickerRequest(val text: String, val style: String = "caption")

// --------------------------------------------------------------------------- //
// v5: Canva / Runway / Veed packs
// --------------------------------------------------------------------------- //

@Serializable
data class MagicResizeRequest(
    val platforms: List<String>,
    val mode: String = "cover",
)

@Serializable
data class BrandRequest(
    val headline: String = "",
    val subline: String = "",
    val colour: String = "#0F766E",
    val position: String = "bottom",
)

@Serializable
data class SubtitleRequest(val srt: String)

@Serializable
data class ChromaRequest(
    val colour: String = "green",
    val similarity: Float = 0.3f,
    val smoothness: Float = 0.1f,
)

@Serializable
data class MotionRequest(val motion: String = "in", val strength: Float = 1.12f)

@Serializable
data class ProgressRequest(val colour: String = "#6EE7B7", val height_pct: Float = 0.012f)
