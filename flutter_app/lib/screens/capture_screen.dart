/// Live camera preview with an alignment guide, or gallery pick when opened with
/// arguments {'fromGallery': true} from the home screen. Hands the picked image bytes
/// to PreviewScreen — no quality/analysis logic lives here (spec section 3: capture
/// screen just captures; quality checks happen server-side via /api/quality-check,
/// called from PreviewScreen before the user can proceed).
library;

import 'dart:io';
import 'package:camera/camera.dart';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';

import '../utils/theme.dart';
import 'preview_screen.dart';

class CaptureScreen extends StatefulWidget {
  const CaptureScreen({super.key});

  @override
  State<CaptureScreen> createState() => _CaptureScreenState();
}

class _CaptureScreenState extends State<CaptureScreen> {
  CameraController? _controller;
  bool _initializing = true;
  String? _error;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final args = ModalRoute.of(context)?.settings.arguments as Map?;
    if (args?['fromGallery'] == true) {
      WidgetsBinding.instance.addPostFrameCallback((_) => _pickFromGallery());
    } else {
      _initCamera();
    }
  }

  Future<void> _initCamera() async {
    try {
      final cameras = await availableCameras();
      if (cameras.isEmpty) {
        setState(() {
          _error = 'No camera available on this device.';
          _initializing = false;
        });
        return;
      }
      final controller = CameraController(cameras.first, ResolutionPreset.high, enableAudio: false);
      await controller.initialize();
      if (!mounted) return;
      setState(() {
        _controller = controller;
        _initializing = false;
      });
    } catch (e) {
      setState(() {
        _error = 'Camera initialization failed: $e';
        _initializing = false;
      });
    }
  }

  Future<void> _pickFromGallery() async {
    final picked = await ImagePicker().pickImage(source: ImageSource.gallery);
    if (picked == null) {
      if (mounted) Navigator.pop(context);
      return;
    }
    final bytes = await picked.readAsBytes();
    if (!mounted) return;
    Navigator.pushReplacement(
      context,
      MaterialPageRoute(builder: (_) => PreviewScreen(imageBytes: bytes, filename: picked.name)),
    );
  }

  Future<void> _capture() async {
    final controller = _controller;
    if (controller == null || !controller.value.isInitialized) return;
    final file = await controller.takePicture();
    final bytes = await File(file.path).readAsBytes();
    if (!mounted) return;
    Navigator.pushReplacement(
      context,
      MaterialPageRoute(builder: (_) => PreviewScreen(imageBytes: bytes, filename: file.name)),
    );
  }

  @override
  void dispose() {
    _controller?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      appBar: AppBar(backgroundColor: Colors.black, foregroundColor: Colors.white, title: const Text('Capture Sample')),
      body: Center(
        child: _initializing
            ? const CircularProgressIndicator(color: Colors.white)
            : _error != null
                ? Padding(
                    padding: const EdgeInsets.all(24),
                    child: Text(_error!, style: const TextStyle(color: Colors.white), textAlign: TextAlign.center),
                  )
                : Stack(
                    fit: StackFit.expand,
                    children: [
                      CameraPreview(_controller!),
                      const _AlignmentGuide(),
                      Positioned(
                        bottom: 28,
                        left: 0,
                        right: 0,
                        child: Center(
                          child: GestureDetector(
                            onTap: _capture,
                            child: Container(
                              width: 74,
                              height: 74,
                              decoration: BoxDecoration(
                                shape: BoxShape.circle,
                                color: Colors.white,
                                border: Border.all(color: HaloScanColors.accent, width: 4),
                              ),
                            ),
                          ),
                        ),
                      ),
                    ],
                  ),
      ),
    );
  }
}

class _AlignmentGuide extends StatelessWidget {
  const _AlignmentGuide();

  @override
  Widget build(BuildContext context) {
    return IgnorePointer(
      child: Center(
        child: Container(
          width: 260,
          height: 260,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            border: Border.all(color: Colors.white.withValues(alpha: 0.85), width: 2),
          ),
          child: const Center(
            child: Text(
              'Align sample pad within circle',
              textAlign: TextAlign.center,
              style: TextStyle(color: Colors.white, fontSize: 12),
            ),
          ),
        ),
      ),
    );
  }
}
