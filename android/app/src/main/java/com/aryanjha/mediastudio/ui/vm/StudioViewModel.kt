package com.aryanjha.mediastudio.ui.vm

import android.net.Uri
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import com.aryanjha.mediastudio.data.AutoPlan
import com.aryanjha.mediastudio.data.MediaAsset
import com.aryanjha.mediastudio.data.MediaRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class StudioUiState(
    val clips: List<MediaAsset> = emptyList(),
    val prompt: String = "",
    val plan: AutoPlan? = null,
    val result: MediaAsset? = null,
    val busy: Boolean = false,
    val status: String? = null,
    val error: String? = null,
    val uploadProgress: Float = 0f,
) {
    val canPlan: Boolean get() = clips.isNotEmpty() && prompt.isNotBlank() && !busy
    val canRender: Boolean get() = plan != null && (plan?.segments?.isNotEmpty() == true) && !busy
}

/**
 * The prompt studio: pick footage, describe the video you want, review the plan,
 * then render. Nothing renders until the plan has been seen.
 */
class StudioViewModel(private val repo: MediaRepository) : ViewModel() {

    private val _state = MutableStateFlow(StudioUiState())
    val state: StateFlow<StudioUiState> = _state.asStateFlow()

    fun setPrompt(text: String) = _state.update { it.copy(prompt = text) }

    fun clearError() = _state.update { it.copy(error = null) }

    fun reset() = _state.update { StudioUiState() }

    /** Chunked upload, so a multi-gigabyte video is fine here. */
    fun addClip(uri: Uri) {
        viewModelScope.launch {
            _state.update { it.copy(busy = true, status = "Uploading footage…", error = null) }
            try {
                val asset = repo.uploadLarge(uri) { sent, total ->
                    _state.update { s ->
                        s.copy(uploadProgress = if (total > 0) sent.toFloat() / total else 0f)
                    }
                }
                _state.update {
                    it.copy(clips = it.clips + asset, uploadProgress = 0f, plan = null)
                }
            } catch (t: Throwable) {
                _state.update { it.copy(error = t.readable()) }
            } finally {
                _state.update { it.copy(busy = false, status = null) }
            }
        }
    }

    fun removeClip(id: String) = _state.update { s ->
        s.copy(clips = s.clips.filterNot { it.id == id }, plan = null)
    }

    fun makePlan() {
        viewModelScope.launch {
            _state.update { it.copy(busy = true, status = "Analysing footage…", error = null) }
            try {
                val plan = repo.planAutoEdit(
                    prompt = _state.value.prompt,
                    mediaIds = _state.value.clips.map { it.id },
                )
                _state.update { it.copy(plan = plan, result = null) }
            } catch (t: Throwable) {
                _state.update { it.copy(error = t.readable()) }
            } finally {
                _state.update { it.copy(busy = false, status = null) }
            }
        }
    }

    fun render() {
        val plan = _state.value.plan ?: return
        viewModelScope.launch {
            _state.update { it.copy(busy = true, status = "Rendering…", error = null) }
            try {
                val asset = repo.runJob(
                    onUpdate = { job ->
                        _state.update { s ->
                            s.copy(status = "Rendering… ${(job.progress * 100).toInt()}%")
                        }
                    },
                ) { repo.renderAutoEdit(plan) }
                _state.update { it.copy(result = asset) }
            } catch (t: Throwable) {
                _state.update { it.copy(error = t.readable()) }
            } finally {
                _state.update { it.copy(busy = false, status = null) }
            }
        }
    }

    companion object {
        fun factory(repo: MediaRepository) = viewModelFactory {
            initializer { StudioViewModel(repo) }
        }
    }
}

internal fun Throwable.readable(): String = when (this) {
    is retrofit2.HttpException -> {
        val body = response()?.errorBody()?.string().orEmpty()
        Regex("\"detail\"\\s*:\\s*\"([^\"]+)\"").find(body)?.groupValues?.get(1)
            ?: "Server error ${code()}"
    }
    is java.net.UnknownHostException -> "No connection to the backend."
    is java.net.SocketTimeoutException -> "The server took too long. Try again."
    else -> message ?: this::class.java.simpleName
}
