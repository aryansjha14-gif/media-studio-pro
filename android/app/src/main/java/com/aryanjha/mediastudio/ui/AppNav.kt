package com.aryanjha.mediastudio.ui

import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Scaffold
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.aryanjha.mediastudio.data.MediaRepository
import com.aryanjha.mediastudio.ui.screens.HomeScreen
import com.aryanjha.mediastudio.ui.screens.PromptStudioScreen
import com.aryanjha.mediastudio.ui.screens.ImageEditorScreen
import com.aryanjha.mediastudio.ui.screens.VideoEditorScreen
import com.aryanjha.mediastudio.ui.vm.EditorViewModel
import com.aryanjha.mediastudio.ui.vm.StudioViewModel

private object Routes {
    const val HOME = "home"
    const val IMAGE = "image"
    const val VIDEO = "video"
    const val STUDIO = "studio"
}

@Composable
fun AppNav(repository: MediaRepository, baseUrl: String) {
    val navController = rememberNavController()
    val vm: EditorViewModel = viewModel(factory = EditorViewModel.factory(repository))
    val state by vm.state.collectAsState()
    val studioVm: StudioViewModel = viewModel(factory = StudioViewModel.factory(repository))
    val studioState by studioVm.state.collectAsState()

    Scaffold { padding ->
        NavHost(
            navController = navController,
            startDestination = Routes.HOME,
            modifier = Modifier.padding(padding),
        ) {
            composable(Routes.HOME) {
                HomeScreen(
                    state = state,
                    baseUrl = baseUrl,
                    onMediaPicked = { uri, expectVideo ->
                        vm.pickAndOpen(uri, expectVideo)
                        navController.navigate(if (expectVideo) Routes.VIDEO else Routes.IMAGE)
                    },
                    onOpenStudio = { navController.navigate(Routes.STUDIO) },
                    onOpenEditor = {
                        val target = if (state.current?.isVideo == true) Routes.VIDEO else Routes.IMAGE
                        navController.navigate(target)
                    },
                    onPromptChange = vm::setPrompt,
                    onGenerateImage = {
                        vm.generateImage()
                        navController.navigate(Routes.IMAGE)
                    },
                    onGenerateVideo = {
                        vm.generateVideo()
                        navController.navigate(Routes.VIDEO)
                    },
                    onDismissError = vm::clearError,
                )
            }

            composable(Routes.STUDIO) {
                PromptStudioScreen(
                    state = studioState,
                    onBack = { navController.popBackStack() },
                    onAddClip = studioVm::addClip,
                    onRemoveClip = studioVm::removeClip,
                    onPromptChange = studioVm::setPrompt,
                    onPlan = studioVm::makePlan,
                    onRender = studioVm::render,
                    onDismissError = studioVm::clearError,
                    onOpenResult = { id ->
                        studioState.result?.let { vm.openAsset(it) }
                        navController.navigate(Routes.VIDEO)
                    },
                )
            }

            composable(Routes.IMAGE) {
                ImageEditorScreen(
                    state = state,
                    onBack = { navController.popBackStack() },
                    onUndo = vm::undo,
                    onDismissError = vm::clearError,
                    onBrightness = vm::setBrightness,
                    onContrast = vm::setContrast,
                    onSaturation = vm::setSaturation,
                    onSharpness = vm::setSharpness,
                    onBlur = vm::setBlur,
                    onRotate = vm::setRotate,
                    onFilter = vm::setFilter,
                    onResetAdjust = vm::resetAdjust,
                    onApplyAdjust = vm::applyAdjust,
                    onPromptChange = vm::setPrompt,
                    onPromptEdit = vm::runPromptEdit,
                    onUpscale = vm::upscale,
                    onRemoveBackground = vm::removeBackground,
                )
            }

            composable(Routes.VIDEO) {
                VideoEditorScreen(
                    state = state,
                    onBack = { navController.popBackStack() },
                    onUndo = vm::undo,
                    onDismissError = vm::clearError,
                    onTrimChange = vm::setTrim,
                    onTrim = vm::trimVideo,
                    onExtractFrame = vm::extractFrame,
                    onPromptChange = vm::setPrompt,
                    onRestyle = vm::restyleVideo,
                    onGenerateVideo = vm::generateVideo,
                )
            }
        }
    }
}
