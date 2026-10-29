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
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
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
import com.aryanjha.mediastudio.ui.components.BusyOverlay
import com.aryanjha.mediastudio.ui.components.ErrorBanner
import com.aryanjha.mediastudio.ui.components.FilterRow
import com.aryanjha.mediastudio.ui.components.PrimaryButton
import com.aryanjha.mediastudio.ui.components.SectionCard
import com.aryanjha.mediastudio.ui.components.SliderRow
import com.aryanjha.mediastudio.ui.vm.EditorUiState

private val FILTERS = listOf("none", "grayscale", "sepia", "warm", "cool", "vintage", "punch", "mono")

@Composable
fun ImageEditorScreen(
    state: EditorUiState,
    onBack: () -> Unit,
    onUndo: () -> Unit,
    onDismissError: () -> Unit,
    onBrightness: (Float) -> Unit,
    onContrast: (Float) -> Unit,
    onSaturation: (Float) -> Unit,
    onSharpness: (Float) -> Unit,
    onBlur: (Float) -> Unit,
    onRotate: (Float) -> Unit,
    onFilter: (String) -> Unit,
    onResetAdjust: () -> Unit,
    onApplyAdjust: () -> Unit,
    onPromptChange: (String) -> Unit,
    onPromptEdit: () -> Unit,
    onUpscale: () -> Unit,
    onRemoveBackground: () -> Unit,
) {
    var tab by remember { mutableStateOf(0) }
    val asset = state.current

    Box(Modifier.fillMaxSize()) {
        Column(Modifier.fillMaxSize()) {
            // ---- top bar --------------------------------------------------
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 8.dp, vertical = 6.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                IconButton(onClick = onBack) {
                    Icon(Icons.Filled.ArrowBack, contentDescription = "Back")
                }
                Column(Modifier.weight(1f)) {
                    Text("Image editor", style = MaterialTheme.typography.titleMedium)
                    Text(
                        asset?.let { "${it.width ?: "?"}×${it.height ?: "?"}" } ?: "no media",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                IconButton(onClick = onUndo, enabled = state.canUndo) {
                    Icon(Icons.Filled.Undo, contentDescription = "Undo")
                }
            }

            // ---- canvas ---------------------------------------------------
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .weight(1f)
                    .padding(horizontal = 12.dp),
                contentAlignment = Alignment.Center,
            ) {
                if (asset != null) {
                    AsyncImage(
                        model = asset.url,
                        contentDescription = "Editing preview",
                        modifier = Modifier
                            .fillMaxSize()
                            .clip(RoundedCornerShape(16.dp)),
                        contentScale = ContentScale.Fit,
                    )
                } else {
                    Text("Pick an image to start")
                }
            }

            if (state.error != null) {
                Box(Modifier.padding(12.dp)) { ErrorBanner(state.error, onDismissError) }
            }

            // ---- tools ----------------------------------------------------
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 12.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                listOf("Adjust", "Filters", "AI").forEachIndexed { index, label ->
                    FilterChip(
                        selected = tab == index,
                        onClick = { tab = index },
                        label = { Text(label) },
                    )
                }
            }

            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(268.dp)
                    .verticalScroll(rememberScrollState())
                    .padding(12.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                when (tab) {
                    0 -> SectionCard("Light & colour", "Rendered on the server with Pillow — instant and free") {
                        SliderRow("Brightness", state.brightness, 0f..2f, onBrightness)
                        SliderRow("Contrast", state.contrast, 0f..2f, onContrast)
                        SliderRow("Saturation", state.saturation, 0f..2f, onSaturation)
                        SliderRow("Sharpness", state.sharpness, 0f..2f, onSharpness)
                        SliderRow("Blur", state.blur, 0f..12f, onBlur, display = { "%.1f".format(it) })
                        SliderRow("Rotate", state.rotate, -180f..180f, onRotate, display = { "%.0f°".format(it) })
                        Spacer(Modifier.height(6.dp))
                        Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                            OutlinedButton(onClick = onResetAdjust) { Text("Reset") }
                            OutlinedButton(
                                onClick = onApplyAdjust,
                                enabled = state.adjustDirty && !state.busy,
                            ) { Text("Apply") }
                        }
                    }

                    1 -> SectionCard("Filter presets", "Tap to select, then Apply") {
                        FilterRow(FILTERS, state.filter, onFilter)
                        Spacer(Modifier.height(10.dp))
                        PrimaryButton(
                            "Apply filter",
                            enabled = state.filter != "none" && !state.busy,
                            onClick = onApplyAdjust,
                        )
                    }

                    else -> SectionCard(
                        "Prompt-based edit",
                        "Describe the change in words — the image is regenerated by the AI model",
                    ) {
                        OutlinedTextField(
                            value = state.prompt,
                            onValueChange = onPromptChange,
                            modifier = Modifier.fillMaxWidth(),
                            minLines = 3,
                            placeholder = { Text("Turn the background into a rainy Mumbai street at night") },
                        )
                        Spacer(Modifier.height(10.dp))
                        PrimaryButton(
                            "Apply prompt",
                            enabled = state.prompt.isNotBlank() && !state.busy && asset != null,
                            onClick = onPromptEdit,
                        )
                        Spacer(Modifier.height(10.dp))
                        Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                            OutlinedButton(onClick = onUpscale, enabled = !state.busy && asset != null) {
                                Text("Upscale 2×")
                            }
                            OutlinedButton(
                                onClick = onRemoveBackground,
                                enabled = !state.busy && asset != null,
                            ) { Text("Remove BG") }
                        }
                    }
                }
                Spacer(Modifier.height(12.dp))
            }
        }

        BusyOverlay(state.statusText)
    }
}
