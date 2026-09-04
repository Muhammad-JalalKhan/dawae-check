import 'package:flutter/material.dart';

import '../core/theme.dart';

/// Error details shown when verification fails.
class VerificationError {
  const VerificationError({
    required this.statusCode,
    required this.message,
  });

  final int? statusCode;
  final String message;

  /// User-friendly explanation per API_CONTRACT.md error table.
  String get userTitle {
    switch (statusCode) {
      case 400:
        return 'Invalid Upload';
      case 422:
        return 'Unreadable Image';
      case 500:
        return 'Server Error';
      default:
        return 'Verification Failed';
    }
  }

  String get userDetail {
    switch (statusCode) {
      case 400:
        return 'The photo upload was missing or in an invalid format. '
            'Please retake the photo and try again.';
      case 422:
        return 'The AI could not read this packaging. The image may be blurry, '
            'too dark, or corrupted. Retake with steady hands under good lighting.';
      case 500:
        return 'The verification pipeline encountered an internal error '
            '(database or AI service). Please try again in a moment.';
      default:
        return message;
    }
  }

  IconData get icon {
    switch (statusCode) {
      case 400:
        return Icons.upload_file;
      case 422:
        return Icons.image_not_supported;
      case 500:
        return Icons.cloud_off;
      default:
        return Icons.error_outline;
    }
  }
}

/// Full-screen error view for failed verification attempts (HTTP 400/422/500).
class ErrorScreen extends StatelessWidget {
  const ErrorScreen({super.key, required this.error});

  final VerificationError error;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Verification Error')),
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                width: 84,
                height: 84,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: AppTheme.counterfeit.withOpacity(0.15),
                  border: Border.all(color: AppTheme.counterfeit, width: 2),
                ),
                child: Icon(
                  error.icon,
                  color: AppTheme.counterfeit,
                  size: 40,
                ),
              ),
              const SizedBox(height: 24),
              Text(
                error.userTitle,
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 22,
                  fontWeight: FontWeight.bold,
                ),
                textAlign: TextAlign.center,
              ),
              if (error.statusCode != null) ...[
                const SizedBox(height: 8),
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
                  decoration: BoxDecoration(
                    color: Colors.white.withOpacity(0.08),
                    borderRadius: BorderRadius.circular(16),
                  ),
                  child: Text(
                    'HTTP ${error.statusCode}',
                    style: const TextStyle(
                      color: Colors.white70,
                      fontSize: 12,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
              ],
              const SizedBox(height: 16),
              Text(
                error.userDetail,
                style: const TextStyle(
                  color: Colors.white70,
                  fontSize: 14,
                  height: 1.5,
                ),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 32),
              ElevatedButton.icon(
                onPressed: () => Navigator.of(context).pop(),
                icon: const Icon(Icons.refresh),
                label: const Text('Try Again'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
