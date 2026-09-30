/// Shows the captured/picked image with Retake/Analyze (spec Page 3), running a quick
/// server-side quality check first so the user isn't surprised by a RECAPTURE_NEEDED
/// result after waiting through the full processing screen.
library;

import 'dart:typed_data';
import 'package:flutter/material.dart';

import '../services/api_service.dart';
import '../widgets/quality_badge.dart';
import 'processing_screen.dart';

class PreviewScreen extends StatefulWidget {
  final Uint8List imageBytes;
  final String filename;
  const PreviewScreen({super.key, required this.imageBytes, required this.filename});

  @override
  State<PreviewScreen> createState() => _PreviewScreenState();
}

class _PreviewScreenState extends State<PreviewScreen> {
  final _api = ApiService();
  Map<String, dynamic>? _quality;
  bool _checking = true;

  @override
  void initState() {
    super.initState();
    _runQualityCheck();
  }

  Future<void> _runQualityCheck() async {
    try {
      final result = await _api.qualityCheck(widget.imageBytes, widget.filename);
      if (mounted) setState(() => _quality = result);
    } catch (e) {
      if (mounted) setState(() => _quality = {'status': 'UNKNOWN', 'reasons': ['Could not reach backend: $e']});
    } finally {
      if (mounted) setState(() => _checking = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final status = _quality?['status'] as String?;
    final reasons = (_quality?['reasons'] as List?)?.cast<String>() ?? const [];

    return Scaffold(
      appBar: AppBar(title: const Text('Preview')),
      body: SafeArea(
        child: Column(
          children: [
            Expanded(child: Center(child: Image.memory(widget.imageBytes))),
            Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  if (_checking)
                    const Row(children: [SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2)), SizedBox(width: 10), Text('Checking image quality…')])
                  else if (status != null) ...[
                    Row(children: [const Text('Quality: '), QualityBadge(status: status)]),
                    if (reasons.isNotEmpty)
                      Padding(
                        padding: const EdgeInsets.only(top: 6),
                        child: Text(reasons.join(' '), style: const TextStyle(fontSize: 12.5)),
                      ),
                  ],
                  const SizedBox(height: 16),
                  Row(
                    children: [
                      Expanded(
                        child: OutlinedButton(
                          onPressed: () => Navigator.pop(context),
                          child: const Text('Retake'),
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: ElevatedButton(
                          onPressed: status == 'POOR'
                              ? null
                              : () => Navigator.push(
                                    context,
                                    MaterialPageRoute(
                                      builder: (_) => ProcessingScreen(imageBytes: widget.imageBytes, filename: widget.filename),
                                    ),
                                  ),
                          child: const Text('Analyze'),
                        ),
                      ),
                    ],
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
