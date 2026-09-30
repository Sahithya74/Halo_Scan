/// Shows the pipeline stages (spec Page 4) while the single /api/analyze call runs.
/// The backend does everything in one request, so these checkmarks are a UX staging
/// animation over one HTTP call rather than separate requests per stage — /api/detect-halo,
/// /api/extract-features and /api/classify exist for research-mode debugging, not for
/// driving this screen.
library;

import 'dart:async';
import 'dart:typed_data';
import 'package:flutter/material.dart';

import '../services/api_service.dart';
import '../utils/theme.dart';
import 'results_screen.dart';

const _stages = [
  'Image acquired',
  'Quality checked',
  'Sample detected',
  'Halo detected',
  'Features extracted',
  'AI analysis',
  'Confidence calculated',
];

class ProcessingScreen extends StatefulWidget {
  final Uint8List imageBytes;
  final String filename;
  const ProcessingScreen({super.key, required this.imageBytes, required this.filename});

  @override
  State<ProcessingScreen> createState() => _ProcessingScreenState();
}

class _ProcessingScreenState extends State<ProcessingScreen> {
  final _api = ApiService();
  int _visibleStage = 0;
  Timer? _ticker;

  @override
  void initState() {
    super.initState();
    _ticker = Timer.periodic(const Duration(milliseconds: 350), (_) {
      if (_visibleStage < _stages.length - 1) {
        setState(() => _visibleStage++);
      }
    });
    _runAnalysis();
  }

  Future<void> _runAnalysis() async {
    try {
      final result = await _api.analyze(widget.imageBytes, widget.filename);
      _ticker?.cancel();
      if (!mounted) return;
      Navigator.pushReplacement(context, MaterialPageRoute(builder: (_) => ResultsScreen(result: result)));
    } catch (e) {
      _ticker?.cancel();
      if (!mounted) return;
      showDialog(
        context: context,
        builder: (_) => AlertDialog(
          title: const Text('Analysis failed'),
          content: Text('$e'),
          actions: [TextButton(onPressed: () => Navigator.of(context)..pop()..pop(), child: const Text('OK'))],
        ),
      );
    }
  }

  @override
  void dispose() {
    _ticker?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Analyzing')),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 320),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              for (var i = 0; i < _stages.length; i++)
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 6),
                  child: Row(
                    children: [
                      Icon(
                        i <= _visibleStage ? Icons.check_circle : Icons.radio_button_unchecked,
                        color: i <= _visibleStage ? HaloScanColors.success : HaloScanColors.textSecondary,
                        size: 20,
                      ),
                      const SizedBox(width: 12),
                      Text(_stages[i]),
                    ],
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }
}
