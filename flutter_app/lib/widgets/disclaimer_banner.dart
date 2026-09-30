/// The medical-safety disclaimer, shown on every results view. Deliberately a shared
/// widget (not copy-pasted text) so the wording can't silently drift screen to screen.
library;

import 'package:flutter/material.dart';
import '../utils/theme.dart';

class DisclaimerBanner extends StatelessWidget {
  final String text;
  const DisclaimerBanner({super.key, required this.text});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: HaloScanColors.accentSoft,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: HaloScanColors.accent.withValues(alpha: 0.3)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(Icons.info_outline, size: 18, color: HaloScanColors.accent),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              text,
              style: const TextStyle(fontSize: 12.5, color: HaloScanColors.textSecondary, height: 1.4),
            ),
          ),
        ],
      ),
    );
  }
}
