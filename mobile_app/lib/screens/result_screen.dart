import 'dart:typed_data';

import 'package:flutter/material.dart';

import '../core/theme.dart';
import '../models/verify_response.dart';
import '../widgets/bbox_painter.dart';

/// Displays the full verification result:
/// - Image preview with defect bounding boxes overlaid
/// - Color-coded verdict banner
/// - Layer 1 database verification breakdown card
/// - Layer 2 AI micro-texture breakdown card
/// - Technical summary text container
class ResultScreen extends StatelessWidget {
  const ResultScreen({
    super.key,
    required this.result,
    required this.imageBytes,
  });

  final VerifyResponse result;
  final Uint8List imageBytes;

  Color get _verdictColor {
    switch (result.verdict) {
      case 'GENUINE':
        return AppTheme.genuine;
      case 'REVIEW_RECOMMENDED':
        return AppTheme.review;
      case 'SUSPECTED_COUNTERFEIT':
        return AppTheme.counterfeit;
      default:
        return Colors.grey;
    }
  }

  IconData get _verdictIcon {
    switch (result.verdict) {
      case 'GENUINE':
        return Icons.verified;
      case 'REVIEW_RECOMMENDED':
        return Icons.warning_amber_rounded;
      case 'SUSPECTED_COUNTERFEIT':
        return Icons.dangerous;
      default:
        return Icons.help_outline;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Verification Result'),
      ),
      body: SingleChildScrollView(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            _VerdictBanner(
              color: _verdictColor,
              icon: _verdictIcon,
              verdict: result.verdict,
              emoji: result.verdictEmoji,
              score: result.authenticityScore,
              requestId: result.requestId,
            ),
            _ImageWithOverlay(
              imageBytes: imageBytes,
              defects: result.layer2VisualCheck.detectedDefects,
            ),
            Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                children: [
                  _Layer1Card(layer1: result.layer1DatabaseCheck),
                  const SizedBox(height: 12),
                  _Layer2Card(layer2: result.layer2VisualCheck),
                  const SizedBox(height: 12),
                  _TechnicalSummaryCard(summary: result.technicalSummary),
                  const SizedBox(height: 24),
                  ElevatedButton.icon(
                    onPressed: () => Navigator.of(context).pop(),
                    icon: const Icon(Icons.camera_alt),
                    label: const Text('Scan Another'),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// Full-width color-coded verdict banner.
class _VerdictBanner extends StatelessWidget {
  const _VerdictBanner({
    required this.color,
    required this.icon,
    required this.verdict,
    required this.emoji,
    required this.score,
    required this.requestId,
  });

  final Color color;
  final IconData icon;
  final String verdict;
  final String emoji;
  final double score;
  final String requestId;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(vertical: 20, horizontal: 16),
      color: color.withOpacity(0.18),
      child: Column(
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(icon, color: color, size: 34),
              const SizedBox(width: 10),
              Flexible(
                child: Text(
                  '$emoji ${verdict.replaceAll('_', ' ')}',
                  style: TextStyle(
                    color: color,
                    fontSize: 20,
                    fontWeight: FontWeight.bold,
                    letterSpacing: 0.5,
                  ),
                  overflow: TextOverflow.ellipsis,
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            'Authenticity Score: ${score.toStringAsFixed(0)} / 100',
            style: const TextStyle(
              color: Colors.white,
              fontSize: 16,
              fontWeight: FontWeight.w500,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            'Request: $requestId',
            style: TextStyle(
              color: Colors.white.withOpacity(0.5),
              fontSize: 11,
            ),
          ),
        ],
      ),
    );
  }
}

/// Captured or selected image with defect bounding boxes drawn on top.
///
/// Uses in-memory bytes so the preview works on Flutter Web and mobile.
class _ImageWithOverlay extends StatelessWidget {
  const _ImageWithOverlay({
    required this.imageBytes,
    required this.defects,
  });

  final Uint8List imageBytes;
  final List<DetectedDefect> defects;

  @override
  Widget build(BuildContext context) {
    return AspectRatio(
      aspectRatio: 4 / 3,
      child: Stack(
        fit: StackFit.expand,
        children: [
          Image.memory(
            imageBytes,
            fit: BoxFit.contain,
            errorBuilder: (_, __, ___) => const ColoredBox(
              color: Colors.black26,
              child: Center(
                child: Icon(Icons.broken_image, color: Colors.white38, size: 48),
              ),
            ),
          ),
          if (defects.isNotEmpty)
            CustomPaint(
              painter: BBoxPainter(defects: defects),
            ),
        ],
      ),
    );
  }
}

/// Layer 1 — Database Verification breakdown card.
class _Layer1Card extends StatelessWidget {
  const _Layer1Card({required this.layer1});

  final Layer1DatabaseCheck layer1;

  @override
  Widget build(BuildContext context) {
    final passed = layer1.status == 'PASSED';
    final record = layer1.matchedRecord;

    return _SectionCard(
      title: 'Layer 1 — Database Verification',
      status: layer1.status,
      statusColor: passed ? AppTheme.genuine : AppTheme.counterfeit,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (record != null) ...[
            _kv('GTIN', record['gtin']?.toString()),
            _kv('Brand', record['brand_name']?.toString()),
            _kv('Batch', record['batch_number']?.toString()),
            _kv('Official Expiry', record['official_expiry']?.toString()),
            const SizedBox(height: 8),
          ] else
            const Padding(
              padding: EdgeInsets.only(bottom: 8),
              child: Text(
                'No matching registry record found.',
                style: TextStyle(color: Colors.white70),
              ),
            ),
          if (layer1.reasons.isNotEmpty)
            ...layer1.reasons.map(
              (r) => Padding(
                padding: const EdgeInsets.only(top: 4),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Icon(
                      passed ? Icons.check_circle : Icons.cancel,
                      color: passed ? AppTheme.genuine : AppTheme.counterfeit,
                      size: 16,
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        r,
                        style: const TextStyle(color: Colors.white70, fontSize: 13),
                      ),
                    ),
                  ],
                ),
              ),
            ),
        ],
      ),
    );
  }

  Widget _kv(String key, String? value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 2),
      child: Row(
        children: [
          SizedBox(
            width: 110,
            child: Text(
              key,
              style: TextStyle(color: Colors.white.withOpacity(0.55), fontSize: 13),
            ),
          ),
          Expanded(
            child: Text(
              value ?? '—',
              style: const TextStyle(color: Colors.white, fontSize: 13),
            ),
          ),
        ],
      ),
    );
  }
}

/// Layer 2 — AI Micro-Texture inspection breakdown card.
class _Layer2Card extends StatelessWidget {
  const _Layer2Card({required this.layer2});

  final Layer2VisualCheck layer2;

  @override
  Widget build(BuildContext context) {
    final passed = layer2.status == 'PASSED';

    return _SectionCard(
      title: 'Layer 2 — AI Micro-Texture',
      status: layer2.status,
      statusColor: passed ? AppTheme.genuine : AppTheme.counterfeit,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Expanded(
                child: Text(
                  'Print Quality Score',
                  style: TextStyle(color: Colors.white70, fontSize: 13),
                ),
              ),
              Text(
                layer2.printQualityScore.toStringAsFixed(0),
                style: TextStyle(
                  color: layer2.printQualityScore >= 50
                      ? AppTheme.genuine
                      : AppTheme.counterfeit,
                  fontSize: 18,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          Text(
            'Detected Defects (${layer2.detectedDefects.length})',
            style: const TextStyle(color: Colors.white70, fontSize: 13),
          ),
          if (layer2.detectedDefects.isEmpty)
            const Padding(
              padding: EdgeInsets.only(top: 6),
              child: Text(
                'No visual defects detected.',
                style: TextStyle(color: Colors.white54),
              ),
            )
          else
            ...layer2.detectedDefects.map(
              (d) => Padding(
                padding: const EdgeInsets.only(top: 6),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Icon(Icons.bug_report, color: AppTheme.counterfeit, size: 16),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        '${d.label} (${(d.confidence * 100).toStringAsFixed(0)}%)',
                        style: const TextStyle(color: Colors.white, fontSize: 13),
                      ),
                    ),
                  ],
                ),
              ),
            ),
        ],
      ),
    );
  }
}

/// Technical summary container.
class _TechnicalSummaryCard extends StatelessWidget {
  const _TechnicalSummaryCard({required this.summary});

  final String summary;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.white.withOpacity(0.08)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.science, color: AppTheme.accent.withOpacity(0.8), size: 18),
              const SizedBox(width: 8),
              const Text(
                'Technical Summary',
                style: TextStyle(
                  color: Colors.white,
                  fontWeight: FontWeight.w600,
                  fontSize: 14,
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            summary.isEmpty ? 'No summary available.' : summary,
            style: const TextStyle(color: Colors.white70, fontSize: 13, height: 1.4),
          ),
        ],
      ),
    );
  }
}

/// Shared card shell for breakdown sections.
class _SectionCard extends StatelessWidget {
  const _SectionCard({
    required this.title,
    required this.status,
    required this.statusColor,
    required this.child,
  });

  final String title;
  final String status;
  final Color statusColor;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.white.withOpacity(0.08)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  title,
                  style: const TextStyle(
                    color: Colors.white,
                    fontWeight: FontWeight.w600,
                    fontSize: 14,
                  ),
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 3),
                decoration: BoxDecoration(
                  color: statusColor.withOpacity(0.15),
                  borderRadius: BorderRadius.circular(20),
                  border: Border.all(color: statusColor, width: 1),
                ),
                child: Text(
                  status,
                  style: TextStyle(
                    color: statusColor,
                    fontSize: 11,
                    fontWeight: FontWeight.w700,
                    letterSpacing: 0.5,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          child,
        ],
      ),
    );
  }
}
