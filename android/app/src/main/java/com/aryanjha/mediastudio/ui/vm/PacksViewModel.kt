package com.aryanjha.mediastudio.ui.vm

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import com.aryanjha.mediastudio.data.MediaAsset
import com.aryanjha.mediastudio.data.MediaRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class PacksUiState(
    val busy: Boolean = false,
    val status: String? = null,
    val error: String? = null,
    val results: List<MediaAsset> = emptyList(),
    val lastTool: String? = null,
)

/**
 * The Canva / Runway / Veed packs. Every action works on the media currently on
 * the canvas and pushes the result back as a new asset, so nothing is destructive.
 */
class PacksViewModel(private val repo: MediaRepository) : ViewModel() {

    private val _state = MutableStateFlow(PacksUiState())
    val state: StateFlow<PacksUiState> = _state.asStateFlow()

    fun clearError() = _state.update { it.copy(error = null) }

    fun clearResults() = _state.update { it.copy(results = emptyList(), lastTool = null) }

    private fun run(tool: String, block: suspend () -> List<MediaAsset>) {
        viewModelScope.launch {
            _state.update { it.copy(busy = true, status = tool, error = null) }
            try {
                val out = block()
                _state.update { it.copy(results = out, lastTool = tool) }
            } catch (t: Throwable) {
                _state.update { it.copy(error = t.readable()) }
            } finally {
                _state.update { it.copy(busy = false, status = null) }
            }
        }
    }

    // -- Canva ------------------------------------------------------------- //
    fun magicResize(asset: MediaAsset, platforms: List<String>) = run("Magic resize") {
        repo.magicResize(asset, platforms)
    }

    fun applyBrand(asset: MediaAsset, headline: String, subline: String, colour: String) =
        run("Brand bar") { listOf(repo.applyBrand(asset, headline, subline, colour)) }

    // -- Veed -------------------------------------------------------------- //
    fun burnSubtitles(asset: MediaAsset, srt: String) = run("Burning subtitles") {
        listOf(repo.burnSubtitles(asset, srt))
    }

    fun denoiseAudio(asset: MediaAsset) = run("Cleaning audio") {
        listOf(repo.denoiseAudio(asset))
    }

    fun addProgressBar(asset: MediaAsset, colour: String) = run("Adding progress bar") {
        listOf(repo.addProgressBar(asset, colour))
    }

    // -- Runway ------------------------------------------------------------ //
    fun cameraMotion(asset: MediaAsset, motion: String) = run("Camera move: $motion") {
        listOf(repo.cameraMotion(asset, motion))
    }

    fun chromaKey(asset: MediaAsset, colour: String) = run("Keying $colour screen") {
        listOf(repo.chromaKey(asset, colour))
    }

    companion object {
        fun factory(repo: MediaRepository) = viewModelFactory {
            initializer { PacksViewModel(repo) }
        }
    }
}
