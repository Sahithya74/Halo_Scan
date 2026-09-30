/// Spec Page 6 — original image, ring overlay, graphs, SHAP feature importance.
/// All images arrive as base64 PNGs already rendered server-side (visualization_service.py)
/// so this screen only needs to decode and display, no client-side plotting.
library;

import 'dart:convert';
import 'package:flutter/material.dart';

import '../models/analysis_result.dart';

class DetailedAnalysisScreen extends StatelessWidget {
  final AnalysisResult result;
  const DetailedAnalysisScreen({super.key, required this.result});

  @override
  Widget build(BuildContext context) {
    final viz = result.visualizations;
    return Scaffold(
      appBar: AppBar(title: const Text('Detailed Analysis')),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            if (viz?.overlayPngBase64 != null) _ImageSection('Ring Detection Overlay', viz!.overlayPngBase64!),
            if (viz?.radialProfilePngBase64 != null) _ImageSection('Radial Intensity Profile', viz!.radialProfilePngBase64!),
            if (viz?.probabilityChartPngBase64 != null) _ImageSection('Classification Probabilities', viz!.probabilityChartPngBase64!),
            if (viz?.featureImportancePngBase64 != null) _ImageSection('Top Contributing Features (SHAP)', viz!.featureImportancePngBase64!),
            if (result.halo != null) _HaloMetricsTable(result: result),
          ],
        ),
      ),
    );
  }
}

class _ImageSection extends StatelessWidget {
  final String title;
  final String base64Png;
  const _ImageSection(this.title, this.base64Png);

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 8),
          ClipRRect(
            borderRadius: BorderRadius.circular(10),
            child: Image.memory(base64Decode(base64Png)),
          ),
        ],
      ),
    );
  }
}

class _HaloMetricsTable extends StatelessWidget {
  final AnalysisResult result;
  const _HaloMetricsTable({required this.result});

  @override
  Widget build(BuildContext context) {
    final halo = result.halo!;
    final rows = {
      'Inner radius (px)': halo.innerRadius.toStringAsFixed(1),
      'Outer radius (px)': halo.outerRadius.toStringAsFixed(1),
      'Halo width (px)': halo.haloWidth.toStringAsFixed(1),
      'Circularity': halo.circularity.toStringAsFixed(3),
      'Symmetry score': halo.symmetryScore.toStringAsFixed(3),
      'Detection confidence': '${(halo.confidence * 100).toStringAsFixed(1)}%',
    };
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('Halo Geometry', style: Theme.of(context).textTheme.titleMedium),
        const SizedBox(height: 8),
        for (final entry in rows.entries)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 3),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [Text(entry.key), Text(entry.value, style: const TextStyle(fontWeight: FontWeight.w600))],
            ),
          ),
      ],
    );
  }
}
