/// Typed models for the POST /api/v1/verify-packaging response contract.
///
/// Field names and nesting MUST match API_CONTRACT.md exactly.
library;

/// Single visual defect from Layer-2 AI analysis.
class DetectedDefect {
  const DetectedDefect({
    required this.label,
    required this.confidence,
    required this.bbox2d,
  });

  final String label;
  final double confidence;

  /// Normalized [ymin, xmin, ymax, xmax] on a 0–1000 integer scale.
  final List<int> bbox2d;

  factory DetectedDefect.fromJson(Map<String, dynamic> json) {
    final bbox = (json['bbox_2d'] as List?) ?? const [];
    return DetectedDefect(
      label: json['label']?.toString() ?? 'Unknown Defect',
      confidence: (json['confidence'] as num?)?.toDouble() ?? 0.0,
      bbox2d: bbox.map((v) => (v as num).toInt()).toList(),
    );
  }
}

/// Layer-1 database verification result.
class Layer1DatabaseCheck {
  const Layer1DatabaseCheck({
    required this.status,
    required this.reasons,
    this.matchedRecord,
  });

  final String status; // PASSED | FAILED
  final List<String> reasons;
  final Map<String, dynamic>? matchedRecord;

  factory Layer1DatabaseCheck.fromJson(Map<String, dynamic> json) {
    return Layer1DatabaseCheck(
      status: json['status']?.toString() ?? 'FAILED',
      reasons: (json['reasons'] as List?)
              ?.map((r) => r.toString())
              .toList() ??
          const [],
      matchedRecord: json['matched_record'] as Map<String, dynamic>?,
    );
  }
}

/// Layer-2 visual (AI micro-texture) inspection result.
class Layer2VisualCheck {
  const Layer2VisualCheck({
    required this.status,
    required this.printQualityScore,
    required this.detectedDefects,
  });

  final String status; // PASSED | FAILED
  final double printQualityScore;
  final List<DetectedDefect> detectedDefects;

  factory Layer2VisualCheck.fromJson(Map<String, dynamic> json) {
    return Layer2VisualCheck(
      status: json['status']?.toString() ?? 'FAILED',
      printQualityScore:
          (json['print_quality_score'] as num?)?.toDouble() ?? 0.0,
      detectedDefects: (json['detected_defects'] as List?)
              ?.map((d) => DetectedDefect.fromJson(d as Map<String, dynamic>))
              .toList() ??
          const [],
    );
  }
}

/// Full verification response.
class VerifyResponse {
  const VerifyResponse({
    required this.requestId,
    required this.verdict,
    required this.authenticityScore,
    required this.layer1DatabaseCheck,
    required this.layer2VisualCheck,
    required this.technicalSummary,
  });

  final String requestId;
  final String verdict; // GENUINE | REVIEW_RECOMMENDED | SUSPECTED_COUNTERFEIT
  final double authenticityScore;
  final Layer1DatabaseCheck layer1DatabaseCheck;
  final Layer2VisualCheck layer2VisualCheck;
  final String technicalSummary;

  factory VerifyResponse.fromJson(Map<String, dynamic> json) {
    return VerifyResponse(
      requestId: json['request_id']?.toString() ?? '',
      verdict: json['verdict']?.toString() ?? 'UNKNOWN',
      authenticityScore:
          (json['authenticity_score'] as num?)?.toDouble() ?? 0.0,
      layer1DatabaseCheck: Layer1DatabaseCheck.fromJson(
        (json['layer1_database_check'] as Map<String, dynamic>?) ?? {},
      ),
      layer2VisualCheck: Layer2VisualCheck.fromJson(
        (json['layer2_visual_check'] as Map<String, dynamic>?) ?? {},
      ),
      technicalSummary: json['technical_summary']?.toString() ?? '',
    );
  }

  /// Verdict badge color per API_CONTRACT.md bands.
  String get verdictEmoji {
    switch (verdict) {
      case 'GENUINE':
        return '🟢';
      case 'REVIEW_RECOMMENDED':
        return '🟡';
      case 'SUSPECTED_COUNTERFEIT':
        return '🔴';
      default:
        return '⚪';
    }
  }
}
