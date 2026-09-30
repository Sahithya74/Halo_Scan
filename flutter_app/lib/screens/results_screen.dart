/// Spec Page 5. The decision-support message and disclaimer are always shown together,
/// directly under the classification — never a bare label with the caveat buried below.
library;

import 'package:flutter/material.dart';

import '../models/analysis_result.dart';
import '../utils/theme.dart';
import '../widgets/disclaimer_banner.dart';
import 'detailed_analysis_screen.dart';

class ResultsScreen extends StatelessWidget {
  final AnalysisResult result;
  const ResultsScreen({super.key, required this.result});

  static const _labelDisplay = {
    'csf_like': 'CSF-like',
    'saline_like': 'Saline-like',
    'saliva_like': 'Saliva-like',
    'other': 'Other / atypical',
  };

  @override
  Widget build(BuildContext context) {
    final classification = result.classification;
    final halo = result.halo;

    return Scaffold(
      appBar: AppBar(title: const Text('Results')),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(20),
          children: [
            _HaloStatusChip(detected: halo?.detected ?? false, status: result.status),
            const SizedBox(height: 20),
            if (classification != null) ...[
              Text(
                'Most likely research classification:',
                style: Theme.of(context).textTheme.labelLarge,
              ),
              const SizedBox(height: 6),
              Row(
                children: [
                  Text(
                    _labelDisplay[classification.researchClassification] ?? classification.researchClassification,
                    style: const TextStyle(fontSize: 24, fontWeight: FontWeight.w700),
                  ),
                  const SizedBox(width: 10),
                  if (classification.uncertain)
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                      decoration: BoxDecoration(color: HaloScanColors.warning.withValues(alpha: 0.15), borderRadius: BorderRadius.circular(12)),
                      child: const Text('UNCERTAIN', style: TextStyle(color: HaloScanColors.warning, fontWeight: FontWeight.w700, fontSize: 11)),
                    ),
                ],
              ),
              const SizedBox(height: 4),
              Text('Confidence: ${(classification.confidence * 100).toStringAsFixed(1)}%',
                  style: const TextStyle(color: HaloScanColors.textSecondary)),
              const SizedBox(height: 20),
            ],
            DisclaimerBanner(text: result.decisionSupport.message),
            const SizedBox(height: 10),
            DisclaimerBanner(text: result.decisionSupport.disclaimer),
            const SizedBox(height: 24),
            if (result.status == 'OK')
              ElevatedButton.icon(
                onPressed: () => Navigator.push(
                  context,
                  MaterialPageRoute(builder: (_) => DetailedAnalysisScreen(result: result)),
                ),
                icon: const Icon(Icons.insights),
                label: const Text('View Detailed Analysis'),
              ),
            const SizedBox(height: 12),
            OutlinedButton(
              onPressed: () => Navigator.popUntil(context, ModalRoute.withName('/')),
              child: const Text('Back to Home'),
            ),
          ],
        ),
      ),
    );
  }
}

class _HaloStatusChip extends StatelessWidget {
  final bool detected;
  final String status;
  const _HaloStatusChip({required this.detected, required this.status});

  @override
  Widget build(BuildContext context) {
    final label = status == 'RECAPTURE_NEEDED'
        ? 'IMAGE QUALITY INSUFFICIENT'
        : (detected ? 'HALO DETECTED' : 'NO HALO DETECTED');
    final color = status == 'RECAPTURE_NEEDED'
        ? HaloScanColors.danger
        : (detected ? HaloScanColors.success : HaloScanColors.warning);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
      decoration: BoxDecoration(color: color.withValues(alpha: 0.12), borderRadius: BorderRadius.circular(10)),
      child: Text(label, style: TextStyle(color: color, fontWeight: FontWeight.w700, letterSpacing: 0.4)),
    );
  }
}
