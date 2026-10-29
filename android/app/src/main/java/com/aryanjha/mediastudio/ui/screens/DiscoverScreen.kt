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
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.AssistChip
import androidx.compose.material3.AssistChipDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.aryanjha.mediastudio.data.FeatureItem
import com.aryanjha.mediastudio.data.LensInfo
import com.aryanjha.mediastudio.data.PlatformPreset
import com.aryanjha.mediastudio.ui.components.ErrorBanner
import com.aryanjha.mediastudio.ui.vm.DiscoverUiState

@Composable
fun DiscoverScreen(
    state: DiscoverUiState,
    onBack: () -> Unit,
    onQueryChange: (String) -> Unit,
    onApplyPlatform: (String) -> Unit,
    onApplyLens: (String) -> Unit,
    onDismissError: () -> Unit,
) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 14.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            IconButton(onClick = onBack) {
                Icon(Icons.Filled.ArrowBack, contentDescription = "Back")
            }
            Column(Modifier.weight(1f)) {
                Text("Discover", style = MaterialTheme.typography.titleMedium)
                Text(
                    "${state.implemented} of ${state.totalFeatures} functions ready",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }

        OutlinedTextField(
            value = state.query,
            onValueChange = onQueryChange,
            modifier = Modifier.fillMaxWidth(),
            singleLine = true,
            leadingIcon = { Icon(Icons.Filled.Search, contentDescription = null) },
            placeholder = { Text("Search: reel, lens, curve, subtitle, brand…") },
        )

        if (state.error != null) {
            ErrorBanner(state.error, onDismissError)
        }

        if (state.query.isNotBlank()) {
            Text(
                "${state.results.size} result(s)",
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            for (feature in state.results) {
                FeatureRow(feature)
            }
            if (state.results.isEmpty() && !state.loading) {
                Text(
                    "Nothing matched. Try 'video', 'lens' or 'watermark'.",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        } else {
            Text("Platform frames", style = MaterialTheme.typography.titleMedium)
            Text(
                "Tap a frame to fit the current media to it.",
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            for (platform in state.platforms) {
                PlatformRow(platform, onApplyPlatform)
            }

            Spacer(Modifier.height(6.dp))
            Text("Lenses", style = MaterialTheme.typography.titleMedium)
            for (lens in state.lenses) {
                LensRow(lens, onApplyLens)
            }
        }
        Spacer(Modifier.height(24.dp))
    }
}

@Composable
private fun FeatureRow(feature: FeatureItem) {
    Column(Modifier.fillMaxWidth()) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(feature.name, style = MaterialTheme.typography.bodyMedium)
            AssistChip(
                onClick = {},
                label = { Text(if (feature.isImplemented) "ready" else "planned") },
                colors = AssistChipDefaults.assistChipColors(
                    labelColor = if (feature.isImplemented) {
                        MaterialTheme.colorScheme.primary
                    } else {
                        MaterialTheme.colorScheme.onSurfaceVariant
                    },
                ),
            )
        }
        Text(
            feature.moduleTitle + " · " + feature.note,
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

@Composable
private fun PlatformRow(platform: PlatformPreset, onApply: (String) -> Unit) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(Modifier.weight(1f)) {
            Text(platform.label, style = MaterialTheme.typography.bodyMedium)
            Text(
                platform.frame,
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        AssistChip(onClick = { onApply(platform.name) }, label = { Text("Fit") })
    }
}

@Composable
private fun LensRow(lens: LensInfo, onApply: (String) -> Unit) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(Modifier.weight(1f)) {
            Text(
                lens.name.replaceFirstChar { it.uppercase() },
                style = MaterialTheme.typography.bodyMedium,
            )
            Text(
                lens.description,
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        AssistChip(onClick = { onApply(lens.name) }, label = { Text("Apply") })
    }
}
