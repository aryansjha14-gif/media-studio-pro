package com.aryanjha.mediastudio.data

import kotlinx.serialization.json.Json

/**
 * Holds the Retrofit client and can swap it when the user changes the server URL.
 *
 * The alternative — rebuilding the app per URL — is what made the earlier APK
 * emulator-only, so this is the fix for that.
 */
class ApiHolder(initialBaseUrl: String, private val json: Json) {

    @Volatile
    private var currentBaseUrl: String = normalise(initialBaseUrl)

    @Volatile
    private var current: MediaApi = ApiClient.create(currentBaseUrl, json)

    fun api(): MediaApi = current

    fun baseUrl(): String = currentBaseUrl

    @Synchronized
    fun setBaseUrl(url: String) {
        val cleaned = normalise(url)
        if (cleaned == currentBaseUrl) return
        currentBaseUrl = cleaned
        current = ApiClient.create(cleaned, json)
    }

    private fun normalise(url: String): String {
        val trimmed = url.trim()
        val withScheme = when {
            trimmed.startsWith("http://") || trimmed.startsWith("https://") -> trimmed
            trimmed.isBlank() -> "http://10.0.2.2:8000/"
            else -> "http://$trimmed"
        }
        return if (withScheme.endsWith("/")) withScheme else "$withScheme/"
    }
}
