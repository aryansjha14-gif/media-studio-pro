package com.aryanjha.mediastudio.ui.vm

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import com.aryanjha.mediastudio.data.FeatureItem
import com.aryanjha.mediastudio.data.LensInfo
import com.aryanjha.mediastudio.data.MediaRepository
import com.aryanjha.mediastudio.data.PlatformPreset
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class DiscoverUiState(
    val query: String = "",
    val results: List<FeatureItem> = emptyList(),
    val platforms: List<PlatformPreset> = emptyList(),
    val lenses: List<LensInfo> = emptyList(),
    val totalFeatures: Int = 0,
    val implemented: Int = 0,
    val loading: Boolean = false,
    val error: String? = null,
)

/** Search over every function, plus the platform and lens catalogues. */
class DiscoverViewModel(private val repo: MediaRepository) : ViewModel() {

    private val _state = MutableStateFlow(DiscoverUiState())
    val state: StateFlow<DiscoverUiState> = _state.asStateFlow()

    private var searchJob: Job? = null

    init {
        viewModelScope.launch {
            runCatching { repo.featureSummary() }.onSuccess { summary ->
                _state.update {
                    it.copy(totalFeatures = summary.total, implemented = summary.implemented)
                }
            }
            runCatching { repo.platforms() }.onSuccess { list ->
                _state.update { it.copy(platforms = list) }
            }
            runCatching { repo.lenses() }.onSuccess { list ->
                _state.update { it.copy(lenses = list) }
            }
        }
    }

    /** Debounced so typing does not fire a request per keystroke. */
    fun onQueryChange(text: String) {
        _state.update { it.copy(query = text) }
        searchJob?.cancel()
        if (text.isBlank()) {
            _state.update { it.copy(results = emptyList(), loading = false) }
            return
        }
        searchJob = viewModelScope.launch {
            delay(250)
            _state.update { it.copy(loading = true) }
            runCatching { repo.searchFeatures(text) }
                .onSuccess { hits -> _state.update { it.copy(results = hits, loading = false) } }
                .onFailure { e -> _state.update { it.copy(error = e.readable(), loading = false) } }
        }
    }

    fun clearError() = _state.update { it.copy(error = null) }

    companion object {
        fun factory(repo: MediaRepository) = viewModelFactory {
            initializer { DiscoverViewModel(repo) }
        }
    }
}
