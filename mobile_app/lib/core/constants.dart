import 'package:flutter/foundation.dart' show kIsWeb;

/// Backend API configuration for Dawae-Check.
///
/// Override the base URL at build time:
///   flutter run -d chrome --dart-define=BASE_URL=http://127.0.0.1:8000
///   flutter build apk --release --dart-define=BASE_URL=https://your-deployed-host
///
/// Defaults:
///   - Web (Chrome): http://localhost:8000
///   - Android emulator: http://10.0.2.2:8000 (maps to host localhost)
///   - iOS simulator / physical device: http://localhost:8000
class ApiConstants {
  const ApiConstants._();

  /// Production / deployed backend URL (override with --dart-define=BASE_URL).
  static const String baseUrl = String.fromEnvironment(
    'BASE_URL',
    defaultValue: kIsWeb ? 'http://localhost:8000' : 'http://10.0.2.2:8000',
  );

  static const String verifyEndpoint = '/api/v1/verify-packaging';
  static const String healthEndpoint = '/api/v1/health';

  /// Maximum allowed image file size in bytes (15 MB).
  static const int maxImageSize = 15 * 1024 * 1024;
}

/// Fixed device/facility identifiers for the demo.
/// In a real app these would come from device registration / user login.
class DemoIdentity {
  const DemoIdentity._();

  static const String deviceId = 'MOB-98421';
  static const String facilityId = 'ALK-DISP-KHI-04';
}
