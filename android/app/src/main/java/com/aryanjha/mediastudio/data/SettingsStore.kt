package com.aryanjha.mediastudio.data

import android.content.Context

/**
 * Tiny persistent settings store. Only one thing matters today: which backend
 * the app talks to. It is stored on device so the same APK works against an
 * emulator, a laptop on the same Wi-Fi, or a deployed server without a rebuild.
 */
class SettingsStore(context: Context) {

    private val prefs = context.getSharedPreferences("media_studio", Context.MODE_PRIVATE)

    var baseUrl: String?
        get() = prefs.getString(KEY_BASE_URL, null)
        set(value) {
            prefs.edit().putString(KEY_BASE_URL, value).apply()
        }

    var lastUsedPrompt: String?
        get() = prefs.getString(KEY_PROMPT, null)
        set(value) {
            prefs.edit().putString(KEY_PROMPT, value).apply()
        }

    fun clear() = prefs.edit().clear().apply()

    private companion object {
        const val KEY_BASE_URL = "base_url"
        const val KEY_PROMPT = "last_prompt"
    }
}
