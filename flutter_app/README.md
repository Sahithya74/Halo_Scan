# Halo Scan — Flutter App (UNVERIFIED)

This app was written without the Flutter SDK installed on the development machine, so it
has **not been compiled, analyzed, or run**. Treat it as a structural scaffold, not
working software, until it has been checked.

## Before trusting this code

1. Install the Flutter SDK: https://docs.flutter.dev/get-started/install
2. From this directory:
   ```
   flutter pub get
   flutter analyze
   ```
3. Fix whatever `flutter analyze` surfaces (package API drift is likely — versions in
   `pubspec.yaml` were picked from general knowledge, not verified against pub.dev at
   write time).
4. Run against the backend:
   ```
   flutter run --dart-define=API_BASE_URL=http://<your-machine-ip>:8000
   ```
   (Android emulator can usually reach the host backend at `http://10.0.2.2:8000`, the
   default baked into `lib/services/api_service.dart`.)

## What's here

- `lib/screens/` — home, capture (camera + gallery pick), preview (quality pre-check),
  processing (pipeline-stage UI while `/api/analyze` runs), results, detailed analysis
  (overlays/graphs/SHAP), history.
- `lib/services/api_service.dart` — the only place the backend base URL and endpoints are
  referenced.
- `lib/models/analysis_result.dart` — mirrors `backend/app/schemas/analysis.py`. If the
  backend schema changes, update this file by hand (no codegen wired up yet).
- `lib/utils/theme.dart` — the subtle/muted medical-research palette used throughout.
- `lib/widgets/disclaimer_banner.dart` — the shared medical-safety disclaimer widget,
  used on every result-bearing screen so the wording can't drift between screens.

## Known gaps / next steps

- Camera permissions (`AndroidManifest.xml` / `Info.plist`) are not yet configured —
  `flutter create .` over this directory (or manually adding the platform folders) plus
  the `camera` and `image_picker` plugin setup instructions will be needed.
- No automated widget tests yet.
- "Dataset / Research Mode" (spec Page 8) has no UI yet — use the backend's
  `/api/research/*` endpoints directly for now.
