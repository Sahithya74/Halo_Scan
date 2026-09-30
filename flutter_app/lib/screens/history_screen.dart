/// Spec Page 7. Lists past analyses from GET /api/history — id, date, result, confidence.
/// No thumbnails yet (storage_service.py doesn't persist images, only the JSON result —
/// see docs/architecture.md for why: avoiding unnecessary image retention by default).
library;

import 'package:flutter/material.dart';

import '../services/api_service.dart';
import '../utils/theme.dart';

class HistoryScreen extends StatefulWidget {
  const HistoryScreen({super.key});

  @override
  State<HistoryScreen> createState() => _HistoryScreenState();
}

class _HistoryScreenState extends State<HistoryScreen> {
  final _api = ApiService();
  late Future<List<dynamic>> _future;

  @override
  void initState() {
    super.initState();
    _future = _api.history();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Analysis History')),
      body: FutureBuilder<List<dynamic>>(
        future: _future,
        builder: (context, snapshot) {
          if (snapshot.connectionState != ConnectionState.done) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snapshot.hasError) {
            return Center(child: Text('Could not load history: ${snapshot.error}'));
          }
          final items = snapshot.data ?? [];
          if (items.isEmpty) {
            return const Center(child: Text('No analyses yet.'));
          }
          return ListView.separated(
            padding: const EdgeInsets.all(16),
            itemCount: items.length,
            separatorBuilder: (_, __) => const SizedBox(height: 8),
            itemBuilder: (context, i) {
              final item = items[i] as Map<String, dynamic>;
              final label = item['research_classification'] as String?;
              final confidence = item['confidence'] as num?;
              return Card(
                child: ListTile(
                  title: Text(label ?? item['quality_status'] as String? ?? 'Unknown'),
                  subtitle: Text(item['timestamp'] as String? ?? ''),
                  trailing: confidence != null
                      ? Text('${(confidence * 100).toStringAsFixed(0)}%',
                          style: const TextStyle(color: HaloScanColors.textSecondary))
                      : null,
                ),
              );
            },
          );
        },
      ),
    );
  }
}
