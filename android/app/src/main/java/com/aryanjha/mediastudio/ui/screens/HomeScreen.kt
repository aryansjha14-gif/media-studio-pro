package com.aryanjha.mediastudio.ui.screens

import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
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
import androidx.compose.material.icons.filled.AutoAwesome
import androidx.compose.material.icons.filled.Image
import androidx.compose.material.icons.filled.Movie
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.aryanjha.mediastudio.ui.components.ErrorBanner
import com.aryanjha.mediastudio.ui.components.PrimaryButton
import com.aryanjha.mediastudio.ui.components.SectionCard
import com.aryanjha.mediastudio.ui.vm.EditorUiState

@Composable
fun HomeScreen(
    state: EditorUiState,
    baseUrl: String,
    onMediaPicked: (Uri, Boolean) -> Unit,
    onOpenEditor: () -> Unit,
    onOpenStudio: () -> Unit,
    onPromptChange: (String) -> Unit,
    onGenerateImage: () -> Unit,
    onGenerateVideo: () -> Unit,
    onDismissError: () -> Unit,
) {
    val imagePicker = rememberLauncherForActivityResult(
        ActivityResultContracts.PickVisualMedia()
    ) { uri -> uri?.let { onMediaPicked(it, false) } }

    val videoPicker = rememberLauncherForActivityResult(
        ActivityResultContracts.PickVisualMedia()
    ) { uri -> uri?.let { onMediaPicked(it, true) } }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(20.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column {
                Text("Media Studio", style = MaterialTheme.typography.headlineSmall)
                Text(
                    "Edit, regenerate and restyle images & video",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            AssistChip(
                onClick = {},
                label = { Text(state.providerName ?: "offline") },
            )
        }

        if (state.error != null) {
            ErrorBanner(state.error, onDismissError)
        }

        PickCard(
            icon = Icons.Filled.Image,
            title = "Image",
            subtitle = "Crop, filters, upscale, background removal, AI prompt edits",
            actionLabel = "Choose image",
            onClick = {
                imagePicker.launch(
                    PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly)
                )
            },
        )

        PickCard(
            icon = Icons.Filled.AutoAwesome,
            title = "Prompt studio",
            subtitle = "Drop in footage, describe the video, review the plan, render",
            actionLabel = "Open studio",
            onClick = onOpenStudio,
        )

        PickCard(
            icon = Icons.Filled.Movie,
            title = "Video",
            subtitle = "Trim, merge, grab frames, restyle or regenerate with a prompt",
            actionLabel = "Choose video",
            onClick = {
                videoPicker.launch(
                    PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.VideoOnly)
                )
            },
        )

        if (state.current != null) {
            SectionCard(
                title = "On the canvas",
                subtitle = "${state.current.kind} · ${state.current.width ?: "?"}×${state.current.height ?: "?"}",
            ) {
                PrimaryButton("Open editor", onClick = onOpenEditor)
            }
        }

        SectionCard(
            title = "Create from a prompt",
            subtitle = "No source media needed — text-to-image or text-to-video",
        ) {
            OutlinedTextField(
                value = state.prompt,
                onValueChange = onPromptChange,
                modifier = Modifier.fillMaxWidth(),
                minLines = 3,
                label = { Text("Prompt") },
                placeholder = { Text("A monsoon street in Mumbai at dusk, neon reflections, 35mm") },
            )
            Spacer(Modifier.height(12.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                PrimaryButton(
                    text = "Generate image",
                    enabled = state.prompt.isNotBlank() && !state.busy,
                    onClick = onGenerateImage,
                )
            }
            Spacer(Modifier.height(8.dp))
            PrimaryButton(
                text = "Generate video",
                enabled = state.prompt.isNotBlank() && !state.busy,
                onClick = onGenerateVideo,
            )
        }

        Text(
            "Backend: $baseUrl",
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Spacer(Modifier.height(24.dp))
    }
}

@Composable
private fun PickCard(
    icon: ImageVector,
    title: String,
    subtitle: String,
    actionLabel: String,
    onClick: () -> Unit,
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(20.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        onClick = onClick,
    ) {
        Row(
            modifier = Modifier.padding(18.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(14.dp),
        ) {
            Icon(icon, contentDescription = null, tint = MaterialTheme.colorScheme.primary)
            Column(Modifier.weight(1f)) {
                Text(title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                Text(
                    subtitle,
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Spacer(Modifier.height(4.dp))
                Text(
                    actionLabel,
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.primary,
                )
            }
            Icon(Icons.Filled.AutoAwesome, contentDescription = null,
                tint = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}
