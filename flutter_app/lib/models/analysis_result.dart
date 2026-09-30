/// Mirrors backend/app/schemas/analysis.py — keep these in sync manually until an
/// OpenAPI codegen step is added. `researchClassification` deliberately mirrors the
/// API's `research_classification` field name (never "diagnosis").
library;

class QualityResult {
  final String status; // GOOD | ACCEPTABLE | POOR
  final double score;
  final List<String> reasons;

  QualityResult({required this.status, required this.score, required this.reasons});

  factory QualityResult.fromJson(Map<String, dynamic> json) => QualityResult(
        status: json['status'] as String,
        score: (json['score'] as num).toDouble(),
        reasons: (json['reasons'] as List?)?.map((e) => e as String).toList() ?? const [],
      );
}

class HaloResult {
  final bool detected;
  final double innerRadius;
  final double outerRadius;
  final double haloWidth;
  final double circularity;
  final double symmetryScore;
  final double confidence;

  HaloResult({
    required this.detected,
    required this.innerRadius,
    required this.outerRadius,
    required this.haloWidth,
    required this.circularity,
    required this.symmetryScore,
    required this.confidence,
  });

  factory HaloResult.fromJson(Map<String, dynamic> json) => HaloResult(
        detected: json['detected'] as bool,
        innerRadius: (json['inner_radius'] as num).toDouble(),
        outerRadius: (json['outer_radius'] as num).toDouble(),
        haloWidth: (json['halo_width'] as num).toDouble(),
        circularity: (json['circularity'] as num).toDouble(),
        symmetryScore: (json['symmetry_score'] as num).toDouble(),
        confidence: (json['confidence'] as num).toDouble(),
      );
}

class ClassificationResult {
  final String researchClassification;
  final double confidence;
  final Map<String, double> classProbabilities;
  final bool uncertain;
  final double disagreement;

  ClassificationResult({
    required this.researchClassification,
    required this.confidence,
    required this.classProbabilities,
    required this.uncertain,
    required this.disagreement,
  });

  factory ClassificationResult.fromJson(Map<String, dynamic> json) => ClassificationResult(
        researchClassification: json['research_classification'] as String,
        confidence: (json['confidence'] as num).toDouble(),
        classProbabilities: (json['class_probabilities'] as Map<String, dynamic>)
            .map((k, v) => MapEntry(k, (v as num).toDouble())),
        uncertain: json['uncertain'] as bool,
        disagreement: (json['disagreement'] as num).toDouble(),
      );
}

class DecisionSupport {
  final String message;
  final bool recommendLabConfirmation;
  final String disclaimer;

  DecisionSupport({
    required this.message,
    required this.recommendLabConfirmation,
    required this.disclaimer,
  });

  factory DecisionSupport.fromJson(Map<String, dynamic> json) => DecisionSupport(
        message: json['message'] as String,
        recommendLabConfirmation: json['recommend_lab_confirmation'] as bool,
        disclaimer: json['disclaimer'] as String,
      );
}

class Visualizations {
  final String? overlayPngBase64;
  final String? radialProfilePngBase64;
  final String? probabilityChartPngBase64;
  final String? featureImportancePngBase64;

  Visualizations({
    this.overlayPngBase64,
    this.radialProfilePngBase64,
    this.probabilityChartPngBase64,
    this.featureImportancePngBase64,
  });

  factory Visualizations.fromJson(Map<String, dynamic> json) => Visualizations(
        overlayPngBase64: json['overlay_png_base64'] as String?,
        radialProfilePngBase64: json['radial_profile_png_base64'] as String?,
        probabilityChartPngBase64: json['probability_chart_png_base64'] as String?,
        featureImportancePngBase64: json['feature_importance_png_base64'] as String?,
      );
}

class AnalysisResult {
  final String analysisId;
  final String timestamp;
  final String status; // OK | RECAPTURE_NEEDED | NO_HALO_DETECTED
  final QualityResult quality;
  final HaloResult? halo;
  final ClassificationResult? classification;
  final Visualizations? visualizations;
  final DecisionSupport decisionSupport;

  AnalysisResult({
    required this.analysisId,
    required this.timestamp,
    required this.status,
    required this.quality,
    this.halo,
    this.classification,
    this.visualizations,
    required this.decisionSupport,
  });

  factory AnalysisResult.fromJson(Map<String, dynamic> json) => AnalysisResult(
        analysisId: json['analysis_id'] as String,
        timestamp: json['timestamp'] as String,
        status: json['status'] as String,
        quality: QualityResult.fromJson(json['quality'] as Map<String, dynamic>),
        halo: json['halo'] != null ? HaloResult.fromJson(json['halo'] as Map<String, dynamic>) : null,
        classification: json['classification'] != null
            ? ClassificationResult.fromJson(json['classification'] as Map<String, dynamic>)
            : null,
        visualizations: json['visualizations'] != null
            ? Visualizations.fromJson(json['visualizations'] as Map<String, dynamic>)
            : null,
        decisionSupport: DecisionSupport.fromJson(json['decision_support'] as Map<String, dynamic>),
      );
}
