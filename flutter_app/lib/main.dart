import 'package:flutter/material.dart';

import 'screens/home_screen.dart';
import 'screens/capture_screen.dart';
import 'screens/history_screen.dart';
import 'utils/theme.dart';

void main() {
  runApp(const HaloScanApp());
}

class HaloScanApp extends StatelessWidget {
  const HaloScanApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Halo Scan',
      debugShowCheckedModeBanner: false,
      theme: buildHaloScanLightTheme(),
      darkTheme: buildHaloScanDarkTheme(),
      themeMode: ThemeMode.system,
      initialRoute: '/',
      routes: {
        '/': (context) => const HomeScreen(),
        '/capture': (context) => const CaptureScreen(),
        '/history': (context) => const HistoryScreen(),
      },
    );
  }
}
