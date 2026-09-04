import 'package:flutter/material.dart';

import '../core/theme.dart';
import '../widgets/brand_loader.dart';
import 'camera_screen.dart';

/// Branded splash screen shown on app start (dark palette gradient).
///
/// Displays the logo mark, app name and tagline for a short beat while
/// Flutter warms up, then transitions to the camera screen.
class SplashScreen extends StatefulWidget {
  const SplashScreen({super.key});

  @override
  State<SplashScreen> createState() => _SplashScreenState();
}

class _SplashScreenState extends State<SplashScreen>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;
  late final Animation<double> _fade;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 900),
    );
    _fade = CurvedAnimation(parent: _controller, curve: Curves.easeIn);
    _controller.forward();

    Future<void>.delayed(const Duration(milliseconds: 1600), _goToCamera);
  }

  void _goToCamera() {
    if (!mounted) return;
    Navigator.of(context).pushReplacement(
      PageRouteBuilder<void>(
        transitionDuration: const Duration(milliseconds: 400),
        pageBuilder: (_, __, ___) => const CameraScreen(),
        transitionsBuilder: (_, anim, __, child) => FadeTransition(
          opacity: anim,
          child: child,
        ),
      ),
    );
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: DecoratedBox(
        decoration: const BoxDecoration(gradient: AppTheme.splashGradient),
        child: SafeArea(
          child: FadeTransition(
            opacity: _fade,
            child: const BrandLoader(showIndicator: false),
          ),
        ),
      ),
    );
  }
}
