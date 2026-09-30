import 'package:flutter/material.dart';
import '../utils/theme.dart';
import '../widgets/disclaimer_banner.dart';
import '../services/api_service.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  final _api = ApiService();
  Map<String, dynamic>? _health;
  bool _checking = true;

  @override
  void initState() {
    super.initState();
    _checkHealth();
  }

  Future<void> _checkHealth() async {
    try {
      final result = await _api.health();
      setState(() => _health = result);
    } catch (_) {
      setState(() => _health = null);
    } finally {
      setState(() => _checking = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Halo Scan')),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(20),
          children: [
            const DisclaimerBanner(
              text: 'Research/decision-support prototype. AI image analysis cannot '
                  'confirm or exclude a CSF leak — beta-2 transferrin lab testing remains '
                  'the specific confirmatory method.',
            ),
            const SizedBox(height: 20),
            _StatusRow(checking: _checking, health: _health),
            const SizedBox(height: 28),
            _HomeButton(
              icon: Icons.camera_alt_outlined,
              label: 'Capture Sample',
              onTap: () => Navigator.pushNamed(context, '/capture'),
            ),
            const SizedBox(height: 12),
            _HomeButton(
              icon: Icons.image_outlined,
              label: 'Analyze Existing Image',
              onTap: () => Navigator.pushNamed(context, '/capture', arguments: {'fromGallery': true}),
            ),
            const SizedBox(height: 12),
            _HomeButton(
              icon: Icons.history,
              label: 'Analysis History',
              onTap: () => Navigator.pushNamed(context, '/history'),
            ),
            const SizedBox(height: 12),
            _HomeButton(
              icon: Icons.science_outlined,
              label: 'Dataset / Research Mode',
              subtitle: 'Development use only — not a clinical interface',
              onTap: () => ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text('Research mode UI not yet built — use the API directly (/api/research/*).')),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _StatusRow extends StatelessWidget {
  final bool checking;
  final Map<String, dynamic>? health;
  const _StatusRow({required this.checking, required this.health});

  @override
  Widget build(BuildContext context) {
    final ok = health != null;
    final modelLoaded = health?['model_loaded'] == true;
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(color: HaloScanColors.surfaceMuted, borderRadius: BorderRadius.circular(10)),
      child: Row(
        children: [
          Icon(
            checking ? Icons.hourglass_empty : (ok ? Icons.check_circle_outline : Icons.error_outline),
            size: 18,
            color: checking ? HaloScanColors.textSecondary : (ok ? HaloScanColors.success : HaloScanColors.danger),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              checking
                  ? 'Checking backend connection…'
                  : (ok
                      ? 'Backend connected — model ${modelLoaded ? "loaded" : "NOT loaded (run scripts/train.py)"}'
                      : 'Backend unreachable at ${ApiConfig.baseUrl}'),
              style: const TextStyle(fontSize: 12.5, color: HaloScanColors.textSecondary),
            ),
          ),
        ],
      ),
    );
  }
}

class _HomeButton extends StatelessWidget {
  final IconData icon;
  final String label;
  final String? subtitle;
  final VoidCallback onTap;

  const _HomeButton({required this.icon, required this.label, required this.onTap, this.subtitle});

  @override
  Widget build(BuildContext context) {
    return Card(
      child: InkWell(
        borderRadius: BorderRadius.circular(14),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Row(
            children: [
              Icon(icon, color: HaloScanColors.accent),
              const SizedBox(width: 16),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(label, style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600)),
                    if (subtitle != null)
                      Padding(
                        padding: const EdgeInsets.only(top: 2),
                        child: Text(subtitle!, style: const TextStyle(fontSize: 11.5, color: HaloScanColors.textSecondary)),
                      ),
                  ],
                ),
              ),
              const Icon(Icons.chevron_right, color: HaloScanColors.textSecondary),
            ],
          ),
        ),
      ),
    );
  }
}
