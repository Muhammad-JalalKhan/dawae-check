import 'dart:math' as math;

import 'package:camera/camera.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:image_picker/image_picker.dart';
import 'package:permission_handler/permission_handler.dart';

import '../core/constants.dart';
import '../core/theme.dart';
import '../models/verify_response.dart';
import '../services/api_service.dart';
import '../widgets/brand_loader.dart';
import '../widgets/camera_guide_card.dart';
import '../widgets/camera_reticle.dart';
import 'error_screen.dart';
import 'result_screen.dart';

class CameraScreen extends StatefulWidget {
  const CameraScreen({super.key});

  @override
  State<CameraScreen> createState() => _CameraScreenState();
}

class _CameraScreenState extends State<CameraScreen>
    with WidgetsBindingObserver {
  CameraController? _controller;
  List<CameraDescription> _cameras = [];
  bool _isInitializing = true;
  bool _isCapturing = false;
  String? _statusMessage;
  double _currentZoom = 3.0;

  /// Scanning-tips card shown once per app launch.
  bool _showGuide = true;

  final ImagePicker _imagePicker = ImagePicker();
  final List<double> _zoomSteps = [1.0, 2.0, 3.0];

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _initCamera();
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _controller?.dispose();
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    final controller = _controller;
    if (controller == null || !controller.value.isInitialized) return;

    if (state == AppLifecycleState.inactive) {
      controller.dispose();
    } else if (state == AppLifecycleState.resumed) {
      _initCamera();
    }
  }

  Future<void> _initCamera() async {
    setState(() {
      _isInitializing = true;
      _statusMessage = null;
    });

    final status = await Permission.camera.request();
    if (!status.isGranted) {
      setState(() {
        _isInitializing = false;
        _statusMessage = 'Camera permission is required.';
      });
      return;
    }

    try {
      _cameras = await availableCameras();
      if (_cameras.isEmpty) {
        setState(() {
          _isInitializing = false;
          _statusMessage = 'No camera found on this device.';
        });
        return;
      }

      final backCamera = _cameras.firstWhere(
        (c) => c.lensDirection == CameraLensDirection.back,
        orElse: () => _cameras.first,
      );

      final controller = CameraController(
        backCamera,
        ResolutionPreset.ultraHigh,
        enableAudio: false,
        imageFormatGroup: ImageFormatGroup.jpeg,
      );

      _controller = controller;
      await controller.initialize();

      // Set initial zoom to 3x if the device supports it.
      await _applyZoom(_currentZoom, animate: false);

      if (mounted) {
        setState(() {
          _isInitializing = false;
        });
      }
    } on CameraException catch (e) {
      setState(() {
        _isInitializing = false;
        _statusMessage = 'Camera error: ${e.description}';
      });
    } catch (e) {
      setState(() {
        _isInitializing = false;
        _statusMessage = 'Failed to initialize camera: $e';
      });
    }
  }

  Future<void> _applyZoom(double zoom, {bool animate = true}) async {
    final controller = _controller;
    if (controller == null || !controller.value.isInitialized) return;

    final minZoom = await controller.getMinZoomLevel();
    final maxZoom = await controller.getMaxZoomLevel();
    final clamped = zoom.clamp(minZoom, maxZoom);

    if (animate) {
      await controller.setZoomLevel(clamped);
    } else {
      await controller.setZoomLevel(clamped);
    }

    setState(() {
      _currentZoom = clamped;
    });
  }

  Future<void> _captureAndUpload() async {
    final controller = _controller;
    if (controller == null || !controller.value.isInitialized || _isCapturing) {
      return;
    }

    HapticFeedback.mediumImpact();
    setState(() => _isCapturing = true);

    try {
      final file = await controller.takePicture();
      await _verifyImage(
        imageFile: file,
        sourceLabel: 'camera capture',
      );
    } on CameraException catch (e) {
      if (mounted) {
        setState(() => _statusMessage = 'Capture failed: ${e.description}');
      }
    } catch (e) {
      await _showVerificationError(e);
    } finally {
      if (mounted) {
        setState(() => _isCapturing = false);
      }
    }
  }

  Future<void> _pickFromGalleryAndUpload() async {
    if (_isCapturing) return;

    HapticFeedback.mediumImpact();
    setState(() => _isCapturing = true);

    try {
      final pickedImage = await _imagePicker.pickImage(
        source: ImageSource.gallery,
        imageQuality: 95,
      );

      if (pickedImage == null) {
        if (mounted) setState(() => _statusMessage = null);
        return;
      }

      await _verifyImage(
        imageFile: pickedImage,
        sourceLabel: 'gallery image',
      );
    } catch (e) {
      await _showVerificationError(e);
    } finally {
      if (mounted) {
        setState(() => _isCapturing = false);
      }
    }
  }

  Future<void> _verifyImage({
    required XFile imageFile,
    required String sourceLabel,
  }) async {
    if (mounted) {
      setState(() => _statusMessage = 'Uploading for verification...');
    }

    final imageBytes = await imageFile.readAsBytes();
    final resultJson = await ApiService.verifyPackaging(
      imageFile,
      imageBytes: imageBytes,
      deviceId: DemoIdentity.deviceId,
      facilityId: DemoIdentity.facilityId,
    );

    // Print the full verification JSON to the debug console (Phase 2 exit condition).
    debugPrint('Verification result ($sourceLabel): $resultJson');

    if (!mounted) return;

    final result = VerifyResponse.fromJson(resultJson);

    await Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => ResultScreen(
          result: result,
          imageBytes: imageBytes,
        ),
      ),
    );

    if (mounted) {
      setState(() => _statusMessage = null);
    }
  }

  Future<void> _showVerificationError(Object error) async {
    debugPrint('Verification failed: $error');
    if (!mounted) return;

    final verificationError = error is ApiException
        ? error.error
        : VerificationError(statusCode: null, message: error.toString());

    await Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => ErrorScreen(error: verificationError),
      ),
    );

    if (mounted) {
      setState(() => _statusMessage = 'Verification failed');
    }
  }

  @override
  Widget build(BuildContext context) {
    final controller = _controller;

    return Scaffold(
      backgroundColor: Colors.black,
      body: SafeArea(
        child: Stack(
          fit: StackFit.expand,
          children: [
            // Camera preview
            if (controller != null && controller.value.isInitialized)
              CameraPreview(controller)
            else
              const BrandLoader(message: 'Starting camera', compact: true),

            // Reticle guide
            if (!_isInitializing && controller != null && controller.value.isInitialized)
              const CameraReticle(),

            // Dynamic enterprise-scanner corner brackets around the reticle
            if (!_isInitializing && controller != null && controller.value.isInitialized)
              Center(
                child: _ScannerBrackets(active: _isCapturing),
              ),

            // Top bar
            Positioned(
              top: 0,
              left: 0,
              right: 0,
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    begin: Alignment.topCenter,
                    end: Alignment.bottomCenter,
                    colors: [Colors.black.withValues(alpha: 0.7), Colors.transparent],
                  ),
                ),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    const Text(
                      'Dawae-Check',
                      style: TextStyle(
                        color: Colors.white,
                        fontSize: 18,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    if (_statusMessage != null)
                      Expanded(
                        child: Padding(
                          padding: const EdgeInsets.only(left: 16),
                          child: Text(
                            _statusMessage!,
                            textAlign: TextAlign.right,
                            style: const TextStyle(
                              color: AppTheme.accent,
                              fontSize: 12,
                            ),
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                      ),
                  ],
                ),
              ),
            ),

            // Dismissible scanning-tips guide card (first launch each session)
            if (_showGuide && controller != null && controller.value.isInitialized)
              Positioned(
                top: 70,
                left: 0,
                right: 0,
                child: CameraGuideCard(
                  onDismiss: () => setState(() => _showGuide = false),
                ),
              ),

            // Persistent scanning guidance banner
            if (!_isInitializing && controller != null && controller.value.isInitialized)
              Positioned(
                bottom: 205,
                left: 24,
                right: 24,
                child: IgnorePointer(
                  child: Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 14,
                      vertical: 10,
                    ),
                    decoration: BoxDecoration(
                      color: Colors.black.withValues(alpha: 0.55),
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(
                        color: AppTheme.accent.withValues(alpha: 0.35),
                      ),
                    ),
                    child: const Row(
                      children: [
                        Icon(
                          Icons.info_outline,
                          color: AppTheme.accent,
                          size: 18,
                        ),
                        SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            'Tip: Align carton flap showing Batch No & Expiry',
                            style: TextStyle(
                              color: Colors.white,
                              fontSize: 13,
                              fontWeight: FontWeight.w500,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),

            // Zoom controls
            Positioned(
              bottom: 140,
              left: 0,
              right: 0,
              child: Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: _zoomSteps.map((zoom) {
                  final selected = (_currentZoom - zoom).abs() < 0.1;
                  return Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 8),
                    child: GestureDetector(
                      onTap: () => _applyZoom(zoom),
                      child: Container(
                        width: 48,
                        height: 48,
                        decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          color: selected
                              ? AppTheme.primary
                              : Colors.black.withValues(alpha: 0.5),
                          border: Border.all(
                            color: selected ? AppTheme.accent : Colors.white54,
                            width: 2,
                          ),
                        ),
                        child: Center(
                          child: Text(
                            '${zoom.toStringAsFixed(0)}x',
                            style: TextStyle(
                              color: selected ? Colors.white : Colors.white70,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                        ),
                      ),
                    ),
                  );
                }).toList(),
              ),
            ),

            // Bottom capture controls: gallery upload + camera shutter.
            Positioned(
              bottom: 40,
              left: 0,
              right: 0,
              child: Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  GestureDetector(
                    onTap: _isCapturing ? null : _pickFromGalleryAndUpload,
                    child: Container(
                      width: 58,
                      height: 58,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        color: Colors.black.withValues(alpha: 0.55),
                        border: Border.all(
                          color: _isCapturing ? Colors.white24 : AppTheme.accent,
                          width: 2,
                        ),
                      ),
                      child: Icon(
                        Icons.photo_library_outlined,
                        color: _isCapturing ? Colors.white38 : Colors.white,
                        size: 28,
                      ),
                    ),
                  ),
                  const SizedBox(width: 24),
                  GestureDetector(
                    onTap: _isCapturing ? null : _captureAndUpload,
                    child: SizedBox(
                      width: 80,
                      height: 80,
                      child: Stack(
                        alignment: Alignment.center,
                        children: [
                          if (_isCapturing)
                            const CircularProgressIndicator(
                              color: AppTheme.accent,
                              strokeWidth: 4,
                            ),
                          Container(
                            width: 64,
                            height: 64,
                            decoration: BoxDecoration(
                              shape: BoxShape.circle,
                              color: _isCapturing ? Colors.grey : Colors.white,
                              border: Border.all(
                                color: _isCapturing ? Colors.white38 : AppTheme.primary,
                                width: 4,
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ],
              ),
            ),

            // Error / permission overlay
            if (_statusMessage != null && _statusMessage!.contains('permission'))
              Center(
                child: Container(
                  margin: const EdgeInsets.all(32),
                  padding: const EdgeInsets.all(24),
                  decoration: BoxDecoration(
                    color: AppTheme.surface,
                    borderRadius: BorderRadius.circular(16),
                  ),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const Icon(Icons.camera_alt, size: 48, color: Colors.white),
                      const SizedBox(height: 16),
                      Text(
                        _statusMessage!,
                        textAlign: TextAlign.center,
                        style: const TextStyle(color: Colors.white),
                      ),
                      const SizedBox(height: 16),
                      const ElevatedButton(
                        onPressed: openAppSettings,
                        child: Text('Open Settings'),
                      ),
                    ],
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }
}

/// Animated green/cyan corner brackets that breathe around the scan
/// reticle, giving an enterprise-scanner feel. While a verification is
/// in flight the brackets lock to bright cyan.
class _ScannerBrackets extends StatefulWidget {
  const _ScannerBrackets({required this.active});

  /// Whether a verification upload is currently in flight.
  final bool active;

  @override
  State<_ScannerBrackets> createState() => _ScannerBracketsState();
}

class _ScannerBracketsState extends State<_ScannerBrackets>
    with SingleTickerProviderStateMixin {
  late final AnimationController _pulse;

  @override
  void initState() {
    super.initState();
    _pulse = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1400),
    )..repeat(reverse: true);
  }

  @override
  void dispose() {
    _pulse.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _pulse,
      builder: (context, _) {
        final t = Curves.easeInOut.transform(_pulse.value);
        final color = widget.active
            ? AppTheme.accent
            : Color.lerp(const Color(0xFF00E676), AppTheme.accent, t)!;
        final opacity = widget.active ? 1.0 : 0.55 + 0.45 * t;
        // Brackets breathe slightly outward from the reticle.
        final scale = widget.active ? 1.02 : 1.0 + 0.03 * t;

        return Transform.scale(
          scale: scale,
          child: Opacity(
            opacity: opacity,
            child: SizedBox(
              width: 292,
              height: 192,
              child: Stack(
                children: [
                  Positioned(top: 0, left: 0, child: _bracket(color)),
                  Positioned(
                    top: 0,
                    right: 0,
                    child: Transform.rotate(
                      angle: math.pi / 2,
                      child: _bracket(color),
                    ),
                  ),
                  Positioned(
                    bottom: 0,
                    right: 0,
                    child: Transform.rotate(
                      angle: math.pi,
                      child: _bracket(color),
                    ),
                  ),
                  Positioned(
                    bottom: 0,
                    left: 0,
                    child: Transform.rotate(
                      angle: -math.pi / 2,
                      child: _bracket(color),
                    ),
                  ),
                ],
              ),
            ),
          ),
        );
      },
    );
  }

  Widget _bracket(Color color) {
    return SizedBox(
      width: 30,
      height: 30,
      child: DecoratedBox(
        decoration: BoxDecoration(
          border: Border(
            top: BorderSide(color: color, width: 3),
            left: BorderSide(color: color, width: 3),
          ),
        ),
      ),
    );
  }
}
