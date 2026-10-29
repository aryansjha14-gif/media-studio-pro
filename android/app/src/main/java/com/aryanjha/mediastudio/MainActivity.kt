package com.aryanjha.mediastudio

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import com.aryanjha.mediastudio.ui.AppNav
import com.aryanjha.mediastudio.ui.theme.MediaStudioTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        val container = (application as MediaStudioApp).container
        setContent {
            MediaStudioTheme {
                AppNav(repository = container.repository, baseUrl = BuildConfig.API_BASE_URL)
            }
        }
    }
}
