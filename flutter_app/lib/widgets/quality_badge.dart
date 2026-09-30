import 'package:flutter/material.dart';
import '../utils/theme.dart';

class QualityBadge extends StatelessWidget {
  final String status; // GOOD | ACCEPTABLE | POOR
  const QualityBadge({super.key, required this.status});

  Color get _color => switch (status) {
        'GOOD' => HaloScanColors.success,
        'ACCEPTABLE' => HaloScanColors.warning,
        _ => HaloScanColors.danger,
      };

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(color: _color.withValues(alpha: 0.15), borderRadius: BorderRadius.circular(20)),
      child: Text(status, style: TextStyle(color: _color, fontWeight: FontWeight.w600, fontSize: 12)),
    );
  }
}
