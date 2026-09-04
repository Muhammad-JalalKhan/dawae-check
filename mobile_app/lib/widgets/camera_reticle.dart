import 'package:flutter/material.dart';

/// Centered alignment guide for batch number and 2D DataMatrix capture.
class CameraReticle extends StatelessWidget {
  const CameraReticle({super.key});

  @override
  Widget build(BuildContext context) {
    return IgnorePointer(
      child: Center(
        child: Container(
          width: 260,
          height: 160,
          decoration: BoxDecoration(
            border: Border.all(
              color: Colors.white.withOpacity(0.85),
              width: 2,
            ),
            borderRadius: BorderRadius.circular(12),
          ),
          child: Stack(
            children: [
              // Corner markers
              Positioned(
                top: 0,
                left: 0,
                child: _corner(size: 24, horizontal: true),
              ),
              Positioned(
                top: 0,
                right: 0,
                child: _corner(size: 24, horizontal: true, flip: true),
              ),
              Positioned(
                bottom: 0,
                left: 0,
                child: _corner(size: 24, horizontal: false),
              ),
              Positioned(
                bottom: 0,
                right: 0,
                child: _corner(size: 24, horizontal: false, flip: true),
              ),
              // Helper label
              const Align(
                alignment: Alignment.bottomCenter,
                child: Padding(
                  padding: EdgeInsets.only(bottom: 8),
                  child: Text(
                    'Align batch number & 2D code',
                    style: TextStyle(
                      color: Colors.white,
                      fontSize: 12,
                      fontWeight: FontWeight.w500,
                      shadows: [
                        Shadow(
                          color: Colors.black54,
                          blurRadius: 4,
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _corner({
    required double size,
    required bool horizontal,
    bool flip = false,
  }) {
    return SizedBox(
      width: horizontal ? size : 2,
      height: horizontal ? 2 : size,
      child: DecoratedBox(
        decoration: BoxDecoration(
          color: Colors.cyanAccent,
          borderRadius: BorderRadius.circular(1),
        ),
      ),
    );
  }
}
