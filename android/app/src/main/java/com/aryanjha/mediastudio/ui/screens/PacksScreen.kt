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
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.unit.dp
import coil.compose.AsyncImage
import com.aryanjha.mediastudio.data.MediaAsset
import com.aryanjha.mediastudio.ui.components.BusyOverlay
import com.aryanjha.mediastudio.ui.components.ErrorBanner
import com.aryanjha.mediastudio.ui.components.PrimaryButton
import com.aryanjha.mediastudio.ui.components.SectionCard
import com.aryanjha.mediastudio.ui.vm.PacksUiState

private val RESIZE_TARGETS = listOf(
    "instagram_reel", "instagram_feed", "instagram_story",
    "youtube_video", "youtube_thumbnail", "youtube_short",
    "snapchat_snap", "tiktok_video", "whatsapp_status",
)

@Composable
fun PacksScreen(
    asset: MediaAsset?,
    state: PacksUiState,
    onBack: () -> Unit,
    onMagicResize: (List<String>) -> Unit,
    onBrand: (String, String, String) -> Unit,
    onSubtitles: (String) -> Unit,
    onCameraMotion: (String) -> Unit,
    onChroma: (String) -> Unit,
    onDenoise: () -> Unit,
    onProgressBar: () -> Unit,
    onOpenResult: (MediaAsset) -> Unit,
    onDismissError: () -> Unit,
) {
    var headline by remember { mutableStateOf("GROUND FLOOR FOR RENT") }
    var subline by remember { mutableStateOf("Dumra, Sitamarhi") }
    var colour by remember { mutableStateOf("#0F766E") }
    var srt by remember { mutableStateOf("") }
    val selected = remember { mutableStateOf(setOf("instagram_reel", "youtube_thumbnail")) }

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
                    Text("Studio packs", style = MaterialTheme.typography.titleMedium)
                    Text(
                        asset?.let { "${it.kind} · ${it.width ?: "?"}x${it.height ?: "?"}" }
                            ?: "Pick media first",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }

            Column(
                modifier = Modifier.padding(horizontal = 12.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                if (state.error != null) ErrorBanner(state.error, onDismissError)

                if (asset == null) {
                    SectionCard("No media on the canvas", "Pick a photo or video from Home first") {
                        Text(
                            "Every pack works on whatever is currently loaded, and always " +
                                "creates a new copy.",
                            style = MaterialTheme.typography.bodyMedium,
                        )
                    }
                } else {
                    // ---------- Canva ----------
                    SectionCard(
                        "Magic resize",
                        "One photo, every platform size — Canva's signature move",
                    ) {
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            RESIZE_TARGETS.take(5).forEach { name ->
                                val on = selected.value.contains(name)
                                AssistChip(
                                    onClick = {
                                        selected.value = if (on) {
                                            selected.value - name
                                        } else {
                                            selected.value + name
                                        }
                                    },
                                    label = { Text(name.removePrefix("instagram_").replace('_', ' ')) },
                                )
                            }
                        }
                        Spacer(Modifier.height(6.dp))
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            RESIZE_TARGETS.drop(5).forEach { name ->
                                val on = selected.value.contains(name)
                                AssistChip(
                                    onClick = {
                                        selected.value = if (on) {
                                            selected.value - name
                                        } else {
                                            selected.value + name
                                        }
                                    },
                                    label = { Text(name.replace('_', ' ')) },
                                )
                            }
                        }
                        Spacer(Modifier.height(10.dp))
                        PrimaryButton(
                            "Resize to ${selected.value.size} frame(s)",
                            enabled = selected.value.isNotEmpty() && !state.busy && asset.isImage,
                            onClick = { onMagicResize(selected.value.toList()) },
                        )
                    }

                    SectionCard("Brand bar", "Headline, subline and your colour, like a brand kit") {
                        OutlinedTextField(
                            value = headline,
                            onValueChange = { headline = it },
                            modifier = Modifier.fillMaxWidth(),
                            singleLine = true,
                            label = { Text("Headline") },
                        )
                        Spacer(Modifier.height(8.dp))
                        OutlinedTextField(
                            value = subline,
                            onValueChange = { subline = it },
                            modifier = Modifier.fillMaxWidth(),
                            singleLine = true,
                            label = { Text("Subline") },
                        )
                        Spacer(Modifier.height(8.dp))
                        OutlinedTextField(
                            value = colour,
                            onValueChange = { colour = it },
                            modifier = Modifier.fillMaxWidth(),
                            singleLine = true,
                            label = { Text("Colour (hex)") },
                        )
                        Spacer(Modifier.height(10.dp))
                        PrimaryButton(
                            "Apply brand bar",
                            enabled = !state.busy && asset.isImage,
                            onClick = { onBrand(headline, subline, colour) },
                        )
                    }

                    // ---------- Veed ----------
                    SectionCard(
                        "Subtitles",
                        "Paste an SRT and burn it into the video, Veed-style",
                    ) {
                        OutlinedTextField(
                            value = srt,
                            onValueChange = { srt = it },
                            modifier = Modifier.fillMaxWidth(),
                            minLines = 5,
                            placeholder = { Text("1\n00:00:00,000 --> 00:00:03,000\nGROUND FLOOR FOR RENT") },
                        )
                        Spacer(Modifier.height(10.dp))
                        PrimaryButton(
                            "Burn subtitles",
                            enabled = srt.isNotBlank() && !state.busy && asset.isVideo,
                            onClick = { onSubtitles(srt) },
                        )
                    }

                    SectionCard("Clean up", "Audio denoise and a story progress bar") {
                        Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                            PrimaryButton(
                                "Clean audio",
                                enabled = !state.busy && asset.isVideo,
                                onClick = onDenoise,
                            )
                        }
                        Spacer(Modifier.height(8.dp))
                        PrimaryButton(
                            "Add progress bar",
                            enabled = !state.busy && asset.isVideo,
                            onClick = onProgressBar,
                        )
                    }

                    // ---------- Runway ----------
                    SectionCard("Camera motion", "Push in, pull out or pan — Runway-style moves") {
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            listOf("in", "out", "left", "right").forEach { motion ->
                                AssistChip(
                                    onClick = { onCameraMotion(motion) },
                                    label = { Text(motion) },
                                )
                            }
                        }
                    }

                    SectionCard("Green screen", "Chroma key removal without a plugin") {
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            AssistChip(onClick = { onChroma("green") }, label = { Text("Green") })
                            AssistChip(onClick = { onChroma("blue") }, label = { Text("Blue") })
                        }
                    }
                }

                if (state.results.isNotEmpty()) {
                    SectionCard(
                        "Results",
                        "${state.results.size} file(s) from ${state.lastTool ?: "the last action"}",
                    ) {
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            state.results.take(3).forEach { result ->
                                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                                    AsyncImage(
                                        model = result.thumbUrl ?: result.url,
                                        contentDescription = null,
                                        modifier = Modifier
                                            .size(96.dp)
                                            .clip(RoundedCornerShape(12.dp)),
                                        contentScale = ContentScale.Crop,
                                    )
                                    Text(
                                        "${result.width ?: "?"}x${result.height ?: "?"}",
                                        style = MaterialTheme.typography.labelSmall,
                                    )
                                }
                            }
                        }
                        Spacer(Modifier.height(10.dp))
                        PrimaryButton(
                            "Open first result",
                            onClick = { onOpenResult(state.results.first()) },
                        )
                    }
                }
                Spacer(Modifier.height(24.dp))
            }
        }
        BusyOverlay(state.status)
    }
}
