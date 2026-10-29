package com.aryanjha.mediastudio.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
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
    Column(Modifier.fillMaxSize().padding(horizontal = 12.dp)) {
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
            placeholder = { Text("Search functions: reel, lens, curve, watermark…") },
        )

        if (state.error != null) {
            Spacer(Modifier.height(8.dp))
            ErrorBanner(state.error, onDismissError)
        }

        LazyColumn(
            modifier = Modifier.fillMaxSize(),
            verticalArrangement = Arrangement.spacedBy(8.dp),
            contentPadding = androidx.compose.foundation.layout.PaddingValues(vertical = 12.dp),
        ) {
            if (state.query.isNotBlank()) {
                item {
                    Text(
                        "${state.results.size} result(s)",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                items(state.results) { feature ->
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
                            "${feature.module_title} · ${feature.note}",
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }
            } else {
                item {
                    Text("Platform frames", style = MaterialTheme.typography.titleMedium)
                }
                item {
                    LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        items(state.platforms) { platform ->
                            AssistChip(
                                onClick = { onApplyPlatform(platform.name) },
                                label = { Text("${platform.label} · ${platform.aspect}") },
                            )
                        }
                    }
                }
                item {
                    Text(
                        "Tap a frame to fit the current media to it.",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                item { Spacer(Modifier.height(8.dp)) }
                item { Text("Lenses", style = MaterialTheme.typography.titleMedium) }
                items(state.lenses) { lens ->
                    Column {
                        Text(lens.name.replaceFirstChar { it.uppercase() },
                            style = MaterialTheme.typography.bodyMedium)
                        Text(
                            lens.description,
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }
                item {
                    Spacer(Modifier.height(6.dp))
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        AssistChip(onClick = { onApplyLens("duotone") }, label = { Text("Try duotone") })
                        AssistChip(onClick = { onApplyLens("bloom") }, label = { Text("Try bloom") })
                    }
                }
            }
        }
    }
}
