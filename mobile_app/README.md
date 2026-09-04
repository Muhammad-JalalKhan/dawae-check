# Dawae-Check Mobile App

Flutter mobile client for pharmaceutical packaging verification.

## Prerequisites

- Flutter SDK 3.0+
- Android Studio / Xcode for emulator or physical device
- A running Dawae-Check backend (local or deployed)

## Setup

```bash
cd mobile_app
flutter pub get
```

## Run

### Local backend (Android emulator)

The default `baseUrl` in `lib/core/constants.dart` is `http://10.0.2.2:8000`,
which maps to the host machine's localhost from the Android emulator.

```bash
# In backend/ directory
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000

# In mobile_app/ directory
flutter run
```

### Physical device or iOS simulator

Update `lib/core/constants.dart`:

```dart
static const String baseUrl = 'http://YOUR_MACHINE_IP:8000';
```

For iOS, also update `ios/Runner/Info.plist` if using HTTP in production.

## Features

- High-resolution camera preview
- 1x / 2x / 3x macro zoom toggle (3x default)
- Centered reticle for batch number / 2D DataMatrix alignment
- Shutter button with upload progress
- Multipart upload to `POST /api/v1/verify-packaging`
- Result screen with:
  - Color-coded verdict banner (🟢 GENUINE / 🟡 REVIEW RECOMMENDED / 🔴 SUSPECTED_COUNTERFEIT)
  - Image preview with defect bounding boxes overlaid (0–1000 normalized scale)
  - Layer 1 database verification breakdown card
  - Layer 2 AI micro-texture breakdown card with print quality score & defect tags
  - Technical summary
- Error views for HTTP 400 / 422 / 500 responses

## Project Layout

```
mobile_app/lib/
├── main.dart
├── core/
│   ├── constants.dart      # API base URL, demo identity
│   └── theme.dart          # Dark brand theme
├── models/
│   └── verify_response.dart  # Typed API contract models
├── screens/
│   ├── camera_screen.dart  # Capture + zoom + reticle + upload
│   ├── result_screen.dart   # Verdict + layers + bbox overlay
│   └── error_screen.dart    # HTTP 400/422/500 error views
├── services/
│   └── api_service.dart     # Backend HTTP client
└── widgets/
    ├── bbox_painter.dart    # Defect box painter (0–1000 → pixels)
    └── camera_reticle.dart  # Alignment guide overlay
```

## Build Release APK

```bash
flutter build apk --release
```
