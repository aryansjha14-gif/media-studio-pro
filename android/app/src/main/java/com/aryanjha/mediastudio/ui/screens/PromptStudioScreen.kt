package com.aryanjha.mediastudio.ui.screens

import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
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
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.Close
import androidx.compose.material3.AssistChip
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
import androidx.compose.ui.draw.clip
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.unit.dp
import coil.compose.AsyncImage
import com.aryanjha.mediastudio.ui.components.BusyOverlay
import com.aryanjha.mediastudio.ui.components.ErrorBanner
import com.aryanjha.mediastudio.ui.components.PrimaryButton
import com.aryanjha.mediastudio.ui.components.SectionCard
import com.aryanjha.mediastudio.ui.vm.StudioUiState

private val SAMPLE_PROMPT = """GROUND FLOOR FOR RENT
LIVING ROOM
BEDROOM 1
KITCHEN
Remove the original audio and add soft background music.
Use smooth transitions and subtle zoom effects.
Add a professional opening and closing screen."""

@Composable
fun PromptStudioScreen(
    state: StudioUiState,
    onBack: () -> Unit,
    onAddClip: (Uri) -> Unit,
    onRemoveClip: (String) -> Unit,
    onPromptChange: (String) -> Unit,
    onPlan: () -> Unit,
    onRender: () -> Unit,
    onDismissError: () -> Unit,
    onOpenResult: (String) -> Unit,
) {
    val picker = rememberLauncherForActivityResult(
        ActivityResultContracts.PickMultipleVisualMedia(20)
    ) { uris -> uris.forEach { uri -> onAddClip(uri) } }

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
                    Text("Prompt studio", style = MaterialTheme.typography.titleMedium)
                    Text(
                        "Footage in, finished video out",
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

                SectionCard(
                    "1. Footage",
                    "Any size — uploads stream in chunks and resume if the connection drops",
                ) {
                    LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        item {
                            OutlinedButton(onClick = {
                                picker.launch(
                                    PickVisualMediaRequest(
                                        ActivityResultContracts.PickVisualMedia.ImageAndVideo
                                    )
                                )
                            }) {
                                Icon(Icons.Filled.Add, contentDescription = null)
                                Spacer(Modifier.size(4.dp))
                                Text("Add")
                            }
                        }
                        items(state.clips) { clip ->
                            Box {
                                AsyncImage(
                                    model = clip.thumbUrl ?: clip.url,
                                    contentDescription = null,
                                    modifier = Modifier
                                        .size(96.dp)
                                        .clip(RoundedCornerShape(12.dp)),
                                    contentScale = ContentScale.Crop,
                                )
                                IconButton(
                                    onClick = { onRemoveClip(clip.id) },
                                    modifier = Modifier.align(Alignment.TopEnd),
                                ) {
                                    Icon(Icons.Filled.Close, contentDescription = "Remove")
                                }
                            }
                        }
                    }
                    if (state.uploadProgress > 0f && state.uploadProgress < 1f) {
                        Spacer(Modifier.height(8.dp))
                        LinearProgressIndicator(
                            progress = { state.uploadProgress },
                            modifier = Modifier.fillMaxWidth(),
                        )
                        Text(
                            "${(state.uploadProgress * 100).toInt()}% uploaded",
                            style = MaterialTheme.typography.labelSmall,
                        )
                    }
                    Spacer(Modifier.height(6.dp))
                    Text(
                        "${state.clips.size} clip(s) ready",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }

                SectionCard("2. Describe the video", "Upper-case lines become the titles") {
                    OutlinedTextField(
                        value = state.prompt,
                        onValueChange = onPromptChange,
                        modifier = Modifier.fillMaxWidth(),
                        minLines = 6,
                        placeholder = { Text(SAMPLE_PROMPT) },
                    )
                    Spacer(Modifier.height(8.dp))
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        AssistChip(
                            onClick = { onPromptChange(SAMPLE_PROMPT) },
                            label = { Text("Use the rental example") },
                        )
                    }
                    Spacer(Modifier.height(10.dp))
                    PrimaryButton(
                        "Analyse and plan",
                        enabled = state.canPlan,
                        onClick = onPlan,
                    )
                }

                state.plan?.let { plan ->
                    SectionCard(
                        "3. Review the plan",
                        "Nothing renders until you approve this",
                    ) {
                        Text(
                            "${plan.shotCount} shots · about ${plan.estimated_seconds.toInt()}s",
                            style = MaterialTheme.typography.titleMedium,
                        )
                        Spacer(Modifier.height(6.dp))
                        plan.segments.take(12).forEach { seg ->
                            Text(
                                "${seg.order}. ${seg.title ?: "untitled"} " +
                                    "(${"%.1f".format(seg.end - seg.start)}s)",
                                style = MaterialTheme.typography.bodyMedium,
                            )
                        }
                        if (plan.skipped.isNotEmpty()) {
                            Spacer(Modifier.height(8.dp))
                            Text(
                                "Dropped ${plan.skipped.size}: " +
                                    plan.skipped.take(3).joinToString { it.reason },
                                style = MaterialTheme.typography.labelSmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                        plan.warnings.forEach { warning ->
                            Text(
                                warning,
                                style = MaterialTheme.typography.labelSmall,
                                color = MaterialTheme.colorScheme.error,
                            )
                        }
                        Spacer(Modifier.height(10.dp))
                        PrimaryButton(
                            "Render video",
                            enabled = state.canRender,
                            onClick = onRender,
                        )
                    }
                }

                state.result?.let { result ->
                    SectionCard("4. Result", "Tap to open in the video editor") {
                        AsyncImage(
                            model = result.thumbUrl ?: result.url,
                            contentDescription = null,
                            modifier = Modifier
                                .fillMaxWidth()
                                .height(180.dp)
                                .clip(RoundedCornerShape(12.dp)),
                            contentScale = ContentScale.Crop,
                        )
                        Spacer(Modifier.height(8.dp))
                        Text(
                            "${result.width ?: "?"}×${result.height ?: "?"} · " +
                                "${"%.1f".format(result.duration ?: 0.0)}s",
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                        Spacer(Modifier.height(8.dp))
                        PrimaryButton("Open result", onClick = { onOpenResult(result.id) })
                    }
                }
                Spacer(Modifier.height(24.dp))
            }
        }
        BusyOverlay(state.status)
    }
}
