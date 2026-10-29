package com.aryanjha.mediastudio.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Shapes
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp

private val Accent = Color(0xFF6EE7B7)
private val AccentDark = Color(0xFF0F766E)
private val SurfaceDark = Color(0xFF0B0F14)
private val SurfaceCard = Color(0xFF151B23)

private val DarkColors = darkColorScheme(
    primary = Accent,
    onPrimary = Color(0xFF04120C),
    secondary = Color(0xFF93C5FD),
    background = SurfaceDark,
    onBackground = Color(0xFFE8EEF5),
    surface = SurfaceCard,
    onSurface = Color(0xFFE8EEF5),
    surfaceVariant = Color(0xFF1E2630),
    onSurfaceVariant = Color(0xFFA9B6C5),
    error = Color(0xFFFF8A80),
)

private val LightColors = lightColorScheme(
    primary = AccentDark,
    secondary = Color(0xFF1D4ED8),
)

private val AppTypography = Typography(
    headlineSmall = TextStyle(fontSize = 22.sp, fontWeight = FontWeight.SemiBold),
    titleMedium = TextStyle(fontSize = 16.sp, fontWeight = FontWeight.SemiBold),
    bodyMedium = TextStyle(fontSize = 14.sp),
    labelSmall = TextStyle(fontSize = 11.sp, fontWeight = FontWeight.Medium),
)

@Composable
fun MediaStudioTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit,
) {
    MaterialTheme(
        colorScheme = if (darkTheme) DarkColors else LightColors,
        typography = AppTypography,
        shapes = Shapes(
            extraSmall = RoundedCornerShape(8),
            small = RoundedCornerShape(12),
            medium = RoundedCornerShape(16),
            large = RoundedCornerShape(22),
            extraLarge = RoundedCornerShape(28),
        ),
        content = content,
    )
}
