package com.aryanjha.mediastudio.ui.vm

import android.net.Uri
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import com.aryanjha.mediastudio.data.AdjustRequest
import com.aryanjha.mediastudio.data.FrameRequest
import com.aryanjha.mediastudio.data.GenerateVideoRequest
import com.aryanjha.mediastudio.data.Job
import com.aryanjha.mediastudio.data.MediaAsset
import com.aryanjha.mediastudio.data.MediaRepository
import com.aryanjha.mediastudio.data.TrimRequest
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class EditorUiState(
    // media on the canvas + undo stack
    val current: MediaAsset? = null,
    val history: List<MediaAsset> = emptyList(),
    // deterministic adjust controls
    val brightness: Float = 1f,
    val contrast: Float = 1f,
    val saturation: Float = 1f,
    val sharpness: Float = 1f,
    val blur: Float = 0f,
    val rotate: Float = 0f,
    val filter: String = "none",
    // prompt + video controls
    val prompt: String = "",
    val trimStart: Float = 0f,
    val trimEnd: Float = 0f,
    // status
    val busy: Boolean = false,
    val statusText: String? = null,
    val error: String? = null,
    val providerName: String? = null,
) {
    val canUndo: Boolean get() = history.isNotEmpty()
    val adjustDirty: Boolean
        get() = brightness != 1f || contrast != 1f || saturation != 1f ||
            sharpness != 1f || blur != 0f || rotate != 0f || filter != "none"
}

class EditorViewModel(private val repo: MediaRepository) : ViewModel() {

    private val _state = MutableStateFlow(EditorUiState())
    val state: StateFlow<EditorUiState> = _state.asStateFlow()

    init {
        viewModelScope.launch {
            runCatching { repo.health() }
                .onSuccess { h -> _state.update { it.copy(providerName = h.provider) } }
                .onFailure { e ->
                    _state.update { it.copy(error = "Cannot reach the backend: ${e.friendly()}") }
                }
        }
    }

    // -- loading ---------------------------------------------------------- //
    fun pickAndOpen(uri: Uri, expectVideo: Boolean = false) = launchTask("Uploading…") {
        val asset = repo.upload(uri)
        if (expectVideo && !asset.isVideo) {
            error("That file is not a video")
        }
        _state.update {
            it.copy(current = asset, history = emptyList(), trimStart = 0f,
                trimEnd = (asset.duration ?: 0.0).toFloat())
        }
    }

    fun openAsset(asset: MediaAsset) {
        _state.update {
            it.copy(current = asset, history = emptyList(), error = null,
                trimStart = 0f, trimEnd = (asset.duration ?: 0.0).toFloat())
        }
    }

    fun undo() {
        val history = _state.value.history
        if (history.isEmpty()) return
        _state.update { it.copy(current = history.last(), history = history.dropLast(1)) }
    }

    // -- adjust controls --------------------------------------------------- //
    fun setBrightness(v: Float) = _state.update { it.copy(brightness = v) }
    fun setContrast(v: Float) = _state.update { it.copy(contrast = v) }
    fun setSaturation(v: Float) = _state.update { it.copy(saturation = v) }
    fun setSharpness(v: Float) = _state.update { it.copy(sharpness = v) }
    fun setBlur(v: Float) = _state.update { it.copy(blur = v) }
    fun setRotate(v: Float) = _state.update { it.copy(rotate = v) }
    fun setFilter(name: String) = _state.update { it.copy(filter = name) }
    fun setPrompt(text: String) = _state.update { it.copy(prompt = text) }
    fun setTrim(start: Float, end: Float) = _state.update { it.copy(trimStart = start, trimEnd = end) }

    fun resetAdjust() = _state.update {
        it.copy(brightness = 1f, contrast = 1f, saturation = 1f, sharpness = 1f,
            blur = 0f, rotate = 0f, filter = "none")
    }

    fun clearError() = _state.update { it.copy(error = null) }

    /** Commit the slider values — one instant, free, server-side render. */
    fun applyAdjust() = launchTask("Rendering…") {
        val s = _state.value
        val asset = s.current ?: error("Nothing to edit")
        val edited = repo.adjust(
            asset.id,
            AdjustRequest(
                rotate = s.rotate.takeIf { it != 0f }?.toDouble(),
                brightness = s.brightness,
                contrast = s.contrast,
                saturation = s.saturation,
                sharpness = s.sharpness,
                blur = s.blur,
                filter = s.filter,
            ),
        )
        pushHistory(edited)
        resetAdjust()
    }

    // -- AI: image --------------------------------------------------------- //
    fun runPromptEdit() = launchJobTask("Editing with AI…") { asset, onUpdate ->
        repo.runJob(onUpdate) { repo.promptEdit(asset!!.id, _state.value.prompt.trim()) }
    }

    fun upscale() = launchJobTask("Upscaling…") { asset, onUpdate ->
        repo.runJob(onUpdate) { repo.upscale(asset!!.id, 2f) }
    }

    fun removeBackground() = launchJobTask("Removing background…") { asset, onUpdate ->
        repo.runJob(onUpdate) { repo.removeBackground(asset!!.id) }
    }

    fun generateImage() = launchJobTask("Generating image…", requiresCurrent = false) { _, onUpdate ->
        repo.runJob(onUpdate) { repo.generateImage(_state.value.prompt.trim()) }
    }

    // -- AI: video --------------------------------------------------------- //
    fun trimVideo() = launchTask("Trimming…") {
        val asset = _state.value.current ?: error("Nothing to trim")
        val s = _state.value
        if (s.trimEnd <= s.trimStart) error("End must be after start")
        val trimmed = repo.trim(
            asset.id,
            TrimRequest(start = s.trimStart.toDouble(), end = s.trimEnd.toDouble()),
        )
        pushHistory(trimmed)
        _state.update { it.copy(trimStart = 0f, trimEnd = (trimmed.duration ?: 0.0).toFloat()) }
    }

    fun extractFrame() = launchTask("Extracting frame…") {
        val asset = _state.value.current ?: error("Nothing to read")
        val frame = repo.extractFrame(asset.id, FrameRequest(at = _state.value.trimStart.toDouble()))
        pushHistory(frame)
    }

    fun restyleVideo() = launchJobTask("Restyling video…") { asset, onUpdate ->
        repo.runJob(onUpdate) { repo.restyleVideo(asset!!.id, _state.value.prompt.trim()) }
    }

    fun generateVideo() = launchJobTask("Generating video…", requiresCurrent = false) { _, onUpdate ->
        repo.runJob(onUpdate) { repo.generateVideo(_state.value.prompt.trim()) }
    }

    // -- plumbing ---------------------------------------------------------- //
    private fun pushHistory(newAsset: MediaAsset) {
        _state.update { s ->
            val current = s.current
            s.copy(
                current = newAsset,
                history = if (current != null) s.history + current else s.history,
            )
        }
    }

    private fun launchTask(label: String, block: suspend () -> Unit) {
        viewModelScope.launch {
            _state.update { it.copy(busy = true, statusText = label, error = null) }
            try {
                block()
            } catch (t: Throwable) {
                _state.update { it.copy(error = t.friendly()) }
            } finally {
                _state.update { it.copy(busy = false, statusText = null) }
            }
        }
    }

    private fun launchJobTask(
        label: String,
        requiresCurrent: Boolean = true,
        block: suspend (MediaAsset?, (Job) -> Unit) -> MediaAsset,
    ) {
        viewModelScope.launch {
            val asset = _state.value.current
            if (requiresCurrent && asset == null) {
                _state.update { it.copy(error = "Pick an image first") }
                return@launch
            }
            if (requiresCurrent && asset != null && !asset.isImage) {
                _state.update { it.copy(error = "That tool works on images only") }
                return@launch
            }
            _state.update { it.copy(busy = true, statusText = label, error = null) }
            try {
                val onUpdate: (Job) -> Unit = { job ->
                    _state.update { s ->
                        s.copy(
                            statusText = when (job.status) {
                                "queued" -> "$label queued…"
                                "running" -> "$label ${(job.progress * 100).toInt()}%"
                                else -> label
                            },
                        )
                    }
                }
                val result = block(asset, onUpdate)
                pushHistory(result)
            } catch (t: Throwable) {
                _state.update { it.copy(error = t.friendly()) }
            } finally {
                _state.update { it.copy(busy = false, statusText = null) }
            }
        }
    }

    companion object {
        fun factory(repo: MediaRepository) = viewModelFactory {
            initializer { EditorViewModel(repo) }
        }
    }
}

/** Turn Retrofit/HTTP exceptions into something a person can read. */
private fun Throwable.friendly(): String = when (this) {
    is retrofit2.HttpException -> {
        val body = response()?.errorBody()?.string().orEmpty()
        val detail = Regex("\"detail\"\\s*:\\s*\"([^\"]+)\"").find(body)?.groupValues?.get(1)
        detail ?: "Server error ${code()}"
    }
    is java.net.UnknownHostException -> "No connection to the backend. Check MEDIA_API_BASE_URL."
    is java.net.SocketTimeoutException -> "The server took too long to respond."
    is java.io.IOException -> message ?: "Network problem"
    else -> message ?: this::class.java.simpleName
}
