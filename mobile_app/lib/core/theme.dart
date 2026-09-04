import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

/// Dawae-Check brand theme.
class AppTheme {
  const AppTheme._();

  static const Color primary = Color(0xFF0D7377);
  static const Color accent = Color(0xFF14FFEC);
  static const Color darkBackground = Color(0xFF121212);
  static const Color surface = Color(0xFF1E1E1E);
  static const Color genuine = Color(0xFF4CAF50);
  static const Color review = Color(0xFFFFC107);
  static const Color counterfeit = Color(0xFFF44336);

  /// Branded splash / loading background gradient (dark palette).
  static const LinearGradient splashGradient = LinearGradient(
    begin: Alignment.topCenter,
    end: Alignment.bottomCenter,
    colors: [
      Color(0xFF0A0A0A),
      Color(0xFF121212),
      Color(0xFF0D3B3D),
    ],
    stops: [0.0, 0.55, 1.0],
  );

  /// App name + tagline shown on splash / loading states.
  static const String appName = 'Dawae-Check';
  static const String appTagline = 'Pharmaceutical Authenticity Verification';

  /// Standard branded loading indicator.
  static Widget loadingIndicator({double size = 36}) {
    return SizedBox(
      width: size,
      height: size,
      child: const CircularProgressIndicator(
        color: accent,
        strokeWidth: 3,
      ),
    );
  }

  static ThemeData get darkTheme {
    final base = ThemeData.dark();
    return base.copyWith(
      scaffoldBackgroundColor: darkBackground,
      colorScheme: const ColorScheme.dark(
        primary: primary,
        secondary: accent,
        surface: surface,
        error: counterfeit,
      ),
      textTheme: GoogleFonts.interTextTheme(base.textTheme),
      appBarTheme: const AppBarTheme(
        backgroundColor: surface,
        elevation: 0,
        centerTitle: true,
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: primary,
          foregroundColor: Colors.white,
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 14),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
          ),
        ),
      ),
    );
  }
}
