import 'dart:io';

import 'package:camera/camera.dart';
import 'package:flutter/material.dart';
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

    setState(() => _isCapturing = true);

    try {
      final file = await controller.takePicture();
      final imageFile = File(file.path);

      setState(() => _statusMessage = 'Uploading for verification...');

      final resultJson = await ApiService.verifyPackaging(
        imageFile: imageFile,
        deviceId: DemoIdentity.deviceId,
        facilityId: DemoIdentity.facilityId,
      );

      // Print the full verification JSON to the debug console (Phase 2 exit condition).
      debugPrint('Verification result: $resultJson');

      if (!mounted) return;

      final result = VerifyResponse.fromJson(resultJson);

      await Navigator.of(context).push(
        MaterialPageRoute<void>(
          builder: (_) => ResultScreen(
            result: result,
            imagePath: file.path,
          ),
        ),
      );

      setState(() => _statusMessage = null);
    } on ApiException catch (e) {
      debugPrint('Verification failed: $e');
      if (!mounted) return;
      await Navigator.of(context).push(
        MaterialPageRoute<void>(
          builder: (_) => ErrorScreen(error: e.error),
        ),
      );
      setState(() => _statusMessage = 'Verification failed');
    } on CameraException catch (e) {
      setState(() => _statusMessage = 'Capture failed: ${e.description}');
    } catch (e) {
      debugPrint('Unexpected error: $e');
      if (!mounted) return;
      await Navigator.of(context).push(
        MaterialPageRoute<void>(
          builder: (_) => ErrorScreen(
            error: VerificationError(statusCode: null, message: e.toString()),
          ),
        ),
      );
      setState(() => _statusMessage = 'Verification failed');
    } finally {
      if (mounted) {
        setState(() => _isCapturing = false);
      }
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
                    colors: [Colors.black.withOpacity(0.7), Colors.transparent],
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
                              : Colors.black.withOpacity(0.5),
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

            // Shutter button
            Positioned(
              bottom: 40,
              left: 0,
              right: 0,
              child: Center(
                child: GestureDetector(
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
                      ElevatedButton(
                        onPressed: openAppSettings,
                        child: const Text('Open Settings'),
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
