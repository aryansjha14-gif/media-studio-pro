package com.aryanjha.mediastudio.ui.vm

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import com.aryanjha.mediastudio.data.MediaRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class SettingsUiState(
    val savedUrl: String = "",
    val draftUrl: String = "",
    val testing: Boolean = false,
    val result: String? = null,
    val error: String? = null,
    val providerName: String? = null,
    val featureTotal: Int = 0,
    val featureReady: Int = 0,
)

class SettingsViewModel(private val repo: MediaRepository) : ViewModel() {

    private val _state = MutableStateFlow(SettingsUiState(savedUrl = repo.baseUrl(), draftUrl = repo.baseUrl()))
    val state: StateFlow<SettingsUiState> = _state.asStateFlow()

    fun onDraftChange(text: String) = _state.update { it.copy(draftUrl = text, error = null, result = null) }

    fun clearError() = _state.update { it.copy(error = null) }

    fun save() {
        repo.updateBaseUrl(_state.value.draftUrl)
        _state.update {
            it.copy(savedUrl = repo.baseUrl(), draftUrl = repo.baseUrl(), result = "Saved. Testing…")
        }
        test()
    }

    fun test() {
        viewModelScope.launch {
            _state.update { it.copy(testing = true, error = null, result = null) }
            try {
                val health = repo.health()
                val summary = repo.featureSummary()
                _state.update {
                    it.copy(
                        testing = false,
                        providerName = health.provider,
                        featureTotal = summary.total,
                        featureReady = summary.implemented,
                        result = "Connected. Provider: ${health.provider} · " +
                            "${summary.implemented}/${summary.total} functions ready",
                    )
                }
            } catch (t: Throwable) {
                _state.update {
                    it.copy(testing = false, error = "Cannot reach the server: ${t.readable()}")
                }
            }
        }
    }

    companion object {
        fun factory(repo: MediaRepository) = viewModelFactory {
            initializer { SettingsViewModel(repo) }
        }
    }
}
