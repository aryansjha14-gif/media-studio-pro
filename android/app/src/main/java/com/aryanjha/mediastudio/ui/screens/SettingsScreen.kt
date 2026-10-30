package com.aryanjha.mediastudio.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.aryanjha.mediastudio.ui.components.ErrorBanner
import com.aryanjha.mediastudio.ui.components.PrimaryButton
import com.aryanjha.mediastudio.ui.components.SectionCard
import com.aryanjha.mediastudio.ui.vm.SettingsUiState

@Composable
fun SettingsScreen(
    state: SettingsUiState,
    onBack: () -> Unit,
    onDraftChange: (String) -> Unit,
    onSave: () -> Unit,
    onTest: () -> Unit,
    onDismissError: () -> Unit,
) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 14.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            IconButton(onClick = onBack) {
                Icon(Icons.Filled.ArrowBack, contentDescription = "Back")
            }
            Text("Settings", style = MaterialTheme.typography.titleMedium)
        }

        if (state.error != null) ErrorBanner(state.error, onDismissError)

        SectionCard(
            "Server address",
            "The app talks to your Media Studio backend. Change this without rebuilding.",
        ) {
            OutlinedTextField(
                value = state.draftUrl,
                onValueChange = onDraftChange,
                modifier = Modifier.fillMaxWidth(),
                singleLine = true,
                label = { Text("Base URL") },
                placeholder = { Text("http://192.168.1.42:8000/") },
            )
            Spacer(Modifier.height(8.dp))
            Text(
                "Emulator: http://10.0.2.2:8000/   ·   Phone on the same Wi-Fi: " +
                    "http://<your-computer-IP>:8000/   ·   Deployed: https://…",
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Spacer(Modifier.height(12.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                PrimaryButton("Save and test", onClick = onSave)
            }
            Spacer(Modifier.height(8.dp))
            OutlinedButton(onClick = onTest, enabled = !state.testing) {
                Text(if (state.testing) "Testing…" else "Test connection")
            }
            if (state.testing) {
                Spacer(Modifier.height(8.dp))
                LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
            }
            state.result?.let {
                Spacer(Modifier.height(8.dp))
                Text(
                    it,
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.primary,
                )
            }
        }

        SectionCard("Status", "What this build can do right now") {
            Text("Saved URL: ${state.savedUrl}", style = MaterialTheme.typography.bodyMedium)
            Text(
                "Provider: ${state.providerName ?: "not checked yet"}",
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Text(
                "Functions ready: ${state.featureReady} of ${state.featureTotal}",
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }

        SectionCard("About", null) {
            Text(
                "Media Studio Pro · image and video editing with prompt-driven automation. " +
                    "Deterministic edits run on your own server; AI edits use the provider " +
                    "configured on that server.",
                style = MaterialTheme.typography.bodyMedium,
            )
        }
        Spacer(Modifier.height(24.dp))
    }
}
