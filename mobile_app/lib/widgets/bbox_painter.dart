import 'package:flutter/material.dart';

import '../models/verify_response.dart';

/// CustomPainter that draws defect bounding boxes over the captured image.
///
/// Converts normalized [ymin, xmin, ymax, xmax] coordinates on a 0–1000
/// integer scale into screen pixels using the API_CONTRACT.md mapping:
///
///   left   = (xmin / 1000.0) * imageDisplayWidth
///   top    = (ymin / 1000.0) * imageDisplayHeight
///   right  = (xmax / 1000.0) * imageDisplayWidth
///   bottom = (ymax / 1000.0) * imageDisplayHeight
class BBoxPainter extends CustomPainter {
  BBoxPainter({
    required this.defects,
    this.boxColor = const Color(0xFFF44336),
    this.labelTextStyle = const TextStyle(
      color: Colors.white,
      fontSize: 11,
      fontWeight: FontWeight.w600,
    ),
  });

  final List<DetectedDefect> defects;
  final Color boxColor;
  final TextStyle labelTextStyle;

  @override
  void paint(Canvas canvas, Size size) {
    final boxPaint = Paint()
      ..color = boxColor
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2.5;

    final labelBgPaint = Paint()
      ..color = boxColor.withOpacity(0.85)
      ..style = PaintingStyle.fill;

    for (final defect in defects) {
      if (defect.bbox2d.length != 4) continue;

      final ymin = defect.bbox2d[0];
      final xmin = defect.bbox2d[1];
      final ymax = defect.bbox2d[2];
      final xmax = defect.bbox2d[3];

      // Normalized 0–1000 → pixel mapping per API_CONTRACT.md.
      final left = (xmin / 1000.0) * size.width;
      final top = (ymin / 1000.0) * size.height;
      final right = (xmax / 1000.0) * size.width;
      final bottom = (ymax / 1000.0) * size.height;

      if (right <= left || bottom <= top) continue;

      final rect = Rect.fromLTRB(left, top, right, bottom);
      canvas.drawRect(rect, boxPaint);

      // Confidence label chip above the box.
      final label = '${(defect.confidence * 100).toStringAsFixed(0)}%';
      final tp = TextPainter(
        text: TextSpan(
          text: label,
          style: labelTextStyle,
        ),
        textDirection: TextDirection.ltr,
      )..layout();

      final chipRect = Rect.fromLTWH(
        left,
        (top - tp.height - 6).clamp(0, size.height - tp.height - 4),
        tp.width + 10,
        tp.height + 4,
      );
      canvas.drawRRect(
        RRect.fromRectAndRadius(chipRect, const Radius.circular(4)),
        labelBgPaint,
      );
      tp.paint(
        canvas,
        Offset(chipRect.left + 5, chipRect.top + 2),
      );
    }
  }

  @override
  bool shouldRepaint(covariant BBoxPainter oldDelegate) {
    return oldDelegate.defects != defects;
  }
}
