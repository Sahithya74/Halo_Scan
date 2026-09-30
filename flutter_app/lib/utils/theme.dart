/// Subtle, muted medical-research palette — deliberately restrained, not a flashy
/// consumer-app look. Soft neutrals with a single desaturated accent.
library;

import 'package:flutter/material.dart';

class HaloScanColors {
  static const Color background = Color(0xFFF6F5F2); // warm off-white
  static const Color surface = Color(0xFFFFFFFF);
  static const Color surfaceMuted = Color(0xFFEEEDE8);
  static const Color textPrimary = Color(0xFF2A2E32);
  static const Color textSecondary = Color(0xFF6B7280);
  static const Color accent = Color(0xFF3D6E73); // desaturated teal, clinical not clinical-cold
  static const Color accentSoft = Color(0xFFDCE7E8);
  static const Color warning = Color(0xFFB98900);
  static const Color danger = Color(0xFFA23B3B);
  static const Color success = Color(0xFF3F7A5E);
  static const Color divider = Color(0xFFE2E0DA);

  static const Color backgroundDark = Color(0xFF15171A);
  static const Color surfaceDark = Color(0xFF1E2124);
  static const Color textPrimaryDark = Color(0xFFE8E8E6);
}

ThemeData buildHaloScanLightTheme() {
  final base = ThemeData.light(useMaterial3: true);
  return base.copyWith(
    scaffoldBackgroundColor: HaloScanColors.background,
    colorScheme: base.colorScheme.copyWith(
      primary: HaloScanColors.accent,
      secondary: HaloScanColors.accentSoft,
      surface: HaloScanColors.surface,
      error: HaloScanColors.danger,
    ),
    appBarTheme: const AppBarTheme(
      backgroundColor: HaloScanColors.background,
      foregroundColor: HaloScanColors.textPrimary,
      elevation: 0,
      centerTitle: false,
    ),
    textTheme: base.textTheme.apply(
      bodyColor: HaloScanColors.textPrimary,
      displayColor: HaloScanColors.textPrimary,
    ),
    cardTheme: CardThemeData(
      color: HaloScanColors.surface,
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(14),
        side: const BorderSide(color: HaloScanColors.divider),
      ),
    ),
    elevatedButtonTheme: ElevatedButtonThemeData(
      style: ElevatedButton.styleFrom(
        backgroundColor: HaloScanColors.accent,
        foregroundColor: Colors.white,
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
      ),
    ),
    dividerColor: HaloScanColors.divider,
  );
}

ThemeData buildHaloScanDarkTheme() {
  final base = ThemeData.dark(useMaterial3: true);
  return base.copyWith(
    scaffoldBackgroundColor: HaloScanColors.backgroundDark,
    colorScheme: base.colorScheme.copyWith(
      primary: HaloScanColors.accent,
      surface: HaloScanColors.surfaceDark,
      error: HaloScanColors.danger,
    ),
    textTheme: base.textTheme.apply(bodyColor: HaloScanColors.textPrimaryDark),
  );
}
