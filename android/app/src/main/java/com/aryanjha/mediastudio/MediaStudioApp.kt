package com.aryanjha.mediastudio

import android.app.Application
import android.content.Context
import com.aryanjha.mediastudio.data.ApiClient
import com.aryanjha.mediastudio.data.MediaApi
import com.aryanjha.mediastudio.data.MediaRepository
import kotlinx.serialization.json.Json

/**
 * Tiny manual DI container. Swap for Hilt/Koin if the app grows.
 */
class AppContainer(context: Context) {
    val json: Json = Json {
        ignoreUnknownKeys = true   // backend may add fields; never crash the app
        encodeDefaults = true      // send explicit values for sliders at 1.0
    }

    val api: MediaApi = ApiClient.create(BuildConfig.API_BASE_URL, json)
    val repository: MediaRepository = MediaRepository(api, context.applicationContext)
}

class MediaStudioApp : Application() {
    lateinit var container: AppContainer
        private set

    override fun onCreate() {
        super.onCreate()
        container = AppContainer(this)
    }
}
