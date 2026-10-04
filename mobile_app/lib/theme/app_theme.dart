import 'package:flutter/material.dart';

class AppTheme {
  // Brand colors
  static const Color darkBg = Color(0xFF0B0C10);
  static const Color cardBg = Color(0xFF1F2833);
  static const Color surfaceGlass = Color(0x331F2833);
  static const Color primaryRose = Color(0xFFFF2A6D);
  static const Color accentCyan = Color(0xFF05D5E6);
  static const Color softPurple = Color(0xFF9D4EDD);
  static const Color textLight = Color(0xFFC5C6C7);
  static const Color textWhite = Color(0xFFFFFFFF);
  static const Color userBubble = Color(0xFF2A2D34);
  static const Color assistantBubble = Color(0xFF1E1E2C);

  static ThemeData get darkTheme {
    return ThemeData(
      brightness: Brightness.dark,
      scaffoldBackgroundColor: darkBg,
      primaryColor: primaryRose,
      colorScheme: const ColorScheme.dark(
        primary: primaryRose,
        secondary: accentCyan,
        surface: cardBg,
        background: darkBg,
      ),
      appBarTheme: const AppBarTheme(
        backgroundColor: darkBg,
        elevation: 0,
        centerTitle: false,
        titleTextStyle: TextStyle(
          color: textWhite,
          fontSize: 20,
          fontWeight: FontWeight.bold,
        ),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: primaryRose,
          foregroundColor: textWhite,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(16),
          ),
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 14),
        ),
      ),
    );
  }
}
