import 'package:flutter/material.dart';

import '../core/theme.dart';

/// Branded logo mark: shield with check, drawn with brand colors.
class BrandLogoMark extends StatelessWidget {
  const BrandLogoMark({super.key, this.size = 72});

  final double size;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        gradient: const RadialGradient(
          colors: [Color(0xFF0D7377), Color(0xFF083A3C)],
        ),
        border: Border.all(color: AppTheme.accent.withOpacity(0.6), width: 2),
        boxShadow: [
          BoxShadow(
            color: AppTheme.accent.withOpacity(0.25),
            blurRadius: 24,
            spreadRadius: 2,
          ),
        ],
      ),
      child: Icon(
        Icons.verified_user_rounded,
        color: AppTheme.accent,
        size: size * 0.52,
      ),
    );
  }
}

/// Branded loading state: logo mark + app name + tagline + spinner.
///
/// Used on the splash screen and while the camera initializes.
class BrandLoader extends StatelessWidget {
  const BrandLoader({
    super.key,
    this.message,
    this.showIndicator = true,
    this.compact = false,
  });

  /// Optional status message shown under the tagline (e.g. 'Starting camera').
  final String? message;
  final bool showIndicator;
  final bool compact;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const BrandLogoMark(),
          const SizedBox(height: 20),
          const Text(
            AppTheme.appName,
            style: TextStyle(
              color: Colors.white,
              fontSize: 26,
              fontWeight: FontWeight.bold,
              letterSpacing: 1.2,
            ),
          ),
          const SizedBox(height: 6),
          Text(
            AppTheme.appTagline,
            textAlign: TextAlign.center,
            style: TextStyle(
              color: AppTheme.accent.withOpacity(0.8),
              fontSize: 12,
              letterSpacing: 0.6,
            ),
          ),
          if (message != null) ...[
            const SizedBox(height: 12),
            Text(
              message!,
              style: TextStyle(
                color: Colors.white.withOpacity(0.6),
                fontSize: 12,
              ),
            ),
          ],
          if (showIndicator) ...[
            SizedBox(height: compact ? 18 : 28),
            AppTheme.loadingIndicator(),
          ],
        ],
      ),
    );
  }
}
