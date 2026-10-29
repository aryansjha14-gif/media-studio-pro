package com.aryanjha.mediastudio.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.Undo
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.RangeSlider
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.media3.common.MediaItem
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.ui.PlayerView
import com.aryanjha.mediastudio.ui.components.BusyOverlay
import com.aryanjha.mediastudio.ui.components.ErrorBanner
import com.aryanjha.mediastudio.ui.components.PrimaryButton
import com.aryanjha.mediastudio.ui.components.SectionCard
import com.aryanjha.mediastudio.ui.vm.EditorUiState

@Composable
fun VideoEditorScreen(
    state: EditorUiState,
    onBack: () -> Unit,
    onUndo: () -> Unit,
    onDismissError: () -> Unit,
    onTrimChange: (Float, Float) -> Unit,
    onTrim: () -> Unit,
    onExtractFrame: () -> Unit,
    onPromptChange: (String) -> Unit,
    onRestyle: () -> Unit,
    onGenerateVideo: () -> Unit,
) {
    val asset = state.current
    val context = LocalContext.current
    val player = remember { ExoPlayer.Builder(context).build() }

    DisposableEffect(Unit) {
        onDispose { player.release() }
    }
    DisposableEffect(asset?.url) {
        asset?.url?.let { url ->
            player.setMediaItem(MediaItem.fromUri(url))
            player.prepare()
        }
        onDispose { player.stop() }
    }

    Box(Modifier.fillMaxSize()) {
        Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState())) {
            Row(
                modifier = Modifier.fillMaxWidth().padding(horizontal = 8.dp, vertical = 6.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                IconButton(onClick = onBack) {
                    Icon(Icons.Filled.ArrowBack, contentDescription = "Back")
                }
                Column(Modifier.weight(1f)) {
                    Text("Video editor", style = MaterialTheme.typography.titleMedium)
                    Text(
                        asset?.duration?.let { "%.1fs · %s×%s".format(it, asset.width ?: "?", asset.height ?: "?") }
                            ?: "no clip",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                IconButton(onClick = onUndo, enabled = state.canUndo) {
                    Icon(Icons.Filled.Undo, contentDescription = "Undo")
                }
            }

            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(230.dp)
                    .padding(horizontal = 12.dp)
                    .clip(RoundedCornerShape(16.dp)),
                contentAlignment = Alignment.Center,
            ) {
                if (asset != null) {
                    AndroidView(
                        factory = { ctx ->
                            PlayerView(ctx).apply {
                                this.player = player
                                useController = true
                            }
                        },
                        modifier = Modifier.fillMaxSize(),
                    )
                } else {
                    Text("Pick a video to start")
                }
            }

            if (state.error != null) {
                Box(Modifier.padding(12.dp)) { ErrorBanner(state.error, onDismissError) }
            }

            Column(
                modifier = Modifier.padding(12.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                val duration = (asset?.duration ?: 0.0).toFloat().coerceAtLeast(0.1f)
                val start = state.trimStart.coerceIn(0f, duration)
                val end = state.trimEnd.coerceIn(0f, duration).coerceAtLeast(start)
                SectionCard("Trim", "Drag the handles, then cut. Re-encodes to H.264.") {
                    RangeSlider(
                        value = start..end,
                        onValueChange = { range -> onTrimChange(range.start, range.endInclusive) },
                        valueRange = 0f..duration,
                    )
                    Text(
                        "%.1fs → %.1fs".format(state.trimStart, state.trimEnd),
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    Spacer(Modifier.height(8.dp))
                    Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                        OutlinedButton(onClick = onExtractFrame, enabled = asset != null && !state.busy) {
                            Text("Grab frame")
                        }
                        PrimaryButton(
                            text = "Cut clip",
                            enabled = asset != null && !state.busy && state.trimEnd > state.trimStart,
                            onClick = onTrim,
                        )
                    }
                }

                SectionCard(
                    "Prompt-based video",
                    "Restyle this clip, or generate a new one from text",
                ) {
                    OutlinedTextField(
                        value = state.prompt,
                        onValueChange = onPromptChange,
                        modifier = Modifier.fillMaxWidth(),
                        minLines = 3,
                        placeholder = { Text("Make it look like a 1990s VHS home video") },
                    )
                    Spacer(Modifier.height(10.dp))
                    PrimaryButton(
                        "Restyle this clip",
                        enabled = state.prompt.isNotBlank() && asset != null && !state.busy,
                        onClick = onRestyle,
                    )
                    Spacer(Modifier.height(8.dp))
                    PrimaryButton(
                        "Generate a new video",
                        enabled = state.prompt.isNotBlank() && !state.busy,
                        onClick = onGenerateVideo,
                    )
                }
                Spacer(Modifier.height(20.dp))
            }
        }
        BusyOverlay(state.statusText)
    }
}
