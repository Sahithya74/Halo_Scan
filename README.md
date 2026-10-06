# Halo Scan

A research/education decision-support prototype that analyzes a photo of a fluid-drop
halo/double-ring pattern (the classic gauze/filter-paper test for suspected CSF leaks) and
reports a research classification — **never a diagnosis**.

## Problem

The halo/double-ring sign is widely taught as a bedside indicator of CSF in bloody
drainage, but the clinical literature is clear that it is **not specific**: saline, tap
water, and normal nasal secretions mixed with blood can all produce the same visual
pattern (see `docs/dataset.md` for the sources). Beta-2 transferrin lab testing remains the
recognized specific confirmatory test. Any software that photographs this test has to make
that limitation structural, not a footnote.

## Proposed solution

A smartphone photo of the pad → a CV pipeline that detects and measures the ring pattern →
a calibrated ML ensemble that gives the chance of CSF-like / saline-like / saliva-like /
tear-like / nasal-mucus-like / other
→ a decision-support message that always recommends lab confirmation rather than presenting
a label as a diagnosis. See `docs/architecture.md` for the full pipeline diagram.

## Status of this build

Software-only (hardware — phone stand, ring light, sample pad — deferred).
- **Backend** (`backend/`): FastAPI + OpenCV + scikit-learn. Photo **and 10-second video**
  analysis, role-based access, encrypted patient data, tamper-evident audit log. A **sample
  gate** responds only to fluid-stain photos: faces, people, objects and unrelated scenes are
  refused before analysis and never stored (see `docs/validation.md`). 80/80 tests
  pass; real metrics in `docs/validation.md`.
- **Web app** (`web_app/`): served by the backend at the server root — one URL for the whole
  system. Role-based login (administrator / doctor·nurse / patient), live camera capture and
  10-second recording, and a bold result report with measurement diagram, chances of each
  fluid (CSF / saline / saliva / tear / nasal mucus / other), comparison radar, video frame
  timeline and printable report.
- **Flutter app** (`flutter_app/`): written as real Dart code but **unverified** — no
  Flutter SDK on the dev machine, and not yet updated for login. See `flutter_app/README.md`.
- **Database**: SQLite, file-based, created automatically (`backend/analysis_history.db`) —
  no separate database server to run. Patient identifiers and results are encrypted inside it.

## Roles

| Role | Can | Cannot |
|---|---|---|
| Administrator | Create/deactivate staff accounts, reset passwords, view audit log, system stats, model card, research mode | See patient results |
| Doctor / Nurse | Register patients (issues them a login), capture and analyse samples, view their patients' results | Manage staff, see the audit log |
| Patient | See their own results with a plain-language explanation | See anyone else's results, run analyses |
- **Dataset** (`backend/datasets/`, `docs/dataset.md`): no public dataset exists for this
  problem (confirmed by search); a procedural synthetic generator was built instead, with
  deliberately overlapping CSF-like/saline-like parameter distributions reflecting the
  real optical ambiguity, fully documented as synthetic/demo data.

## Hardware (future)

Smartphone + fixed stand + LED ring light + sample pad + optional macro lens. Not built in
this pass — the MVP only assumes a smartphone camera and controlled lighting.

## Software

- **Backend**: Python, FastAPI, OpenCV, NumPy, SciPy, scikit-image, scikit-learn, SHAP,
  Matplotlib, SQLite. See `backend/README.md`.
- **Web app**: static HTML/CSS/JS modules (`web_app/`), no build step, served by the backend
  itself. Pointer-driven motion (3D tilt, magnetic buttons, animated halo rings), disabled
  automatically for users who prefer reduced motion.
- **Mobile**: Flutter/Dart (unverified scaffold). See `flutter_app/README.md`.

## Architecture

See `docs/architecture.md`.

## AI pipeline / Algorithms

See `docs/algorithms.md` for the full list of CV algorithms, engineered features, and ML
models used, and what was deliberately left out (CNN/U-Net/Grad-CAM) and why.

## Dataset

See `docs/dataset.md` — the public-dataset search result, the literature grounding the
synthetic generator's parameters, and its limitations.

## Model

Ensemble of calibrated Logistic Regression / Random Forest / SVM on a hand-engineered
feature vector (geometry, intensity, radial profile, color, texture, spreading), with
Mahalanobis out-of-distribution detection and SHAP explainability. See `docs/algorithms.md`.

## API

See `docs/api.md`.

## Flutter app

See `flutter_app/README.md`.

## Security

- **Passwords**: Argon2id hashes; ≥10 chars with a letter and digit; temporary passwords
  must be changed at first sign-in; 5 failures → 15-min lockout, plus a per-IP limit.
- **Sessions**: random server-side tokens (only their SHA-256 is stored), HttpOnly +
  SameSite=Strict cookies, CSRF token on every write, 30-min idle / 8-h absolute expiry.
- **Encryption at rest**: patient name, record number, date of birth and every stored result
  are encrypted with Fernet (AES + HMAC). The key lives in `backend/secrets/data.key`
  (gitignored) or `HALO_DATA_KEY` — **back it up; losing it makes the data unreadable**.
- **Access control**: role checks on every endpoint; patients get 404 for records that aren't
  theirs; administrators manage the system but cannot open patient results.
- **Audit trail**: logins, failures, lockouts, patient registrations, analyses and record
  views are written to a SHA-256 hash-chained log; the admin page shows whether it verifies.
- **HTTP hardening**: strict Content-Security-Policy (no inline scripts), `X-Frame-Options:
  DENY`, `nosniff`, no-referrer, `no-store` on API responses, camera-only permissions policy;
  CORS closed by default.
- **Uploads**: content-type allowlist, 25 MB / 15 s limits; the raw upload is processed in
  memory or a temp file deleted immediately. A downsized copy of the analysed image/frame is
  kept inside the encrypted result so the report can show it later.

## Limitations

This is a research/education prototype, not a medical device. See the disclaimer embedded
in every API response (`decision_support.disclaimer`) and `docs/dataset.md` /
`docs/validation.md` for the full scientific and dataset limitations.

## Installation

```
git clone <this repo>
cd Halo_Scan/backend
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
```

## Running everything (web app + backend + database)

1. Create accounts — either a real administrator (prompts for a password):
   ```
   cd backend
   .venv/Scripts/python.exe ../scripts/create_admin.py --username admin --name "College Admin"
   ```
   or demo accounts for every role, with random passwords printed once:
   ```
   .venv/Scripts/python.exe ../scripts/seed_demo_users.py
   ```
2. Start the server (the SQLite database needs no separate process):
   ```
   .venv/Scripts/python.exe -m uvicorn app.main:app
   ```
3. Open **http://localhost:8000/** and sign in. The camera works on `localhost` directly.

**Using the camera from a phone/tablet on the same network** needs HTTPS (browsers block the
camera on plain HTTP except for localhost):
```
.venv/Scripts/python.exe ../scripts/make_dev_cert.py --host <your-LAN-IP>
set HALO_COOKIE_SECURE=true
.venv/Scripts/python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8443 --ssl-keyfile secrets/dev-key.pem --ssl-certfile secrets/dev-cert.pem
```
then open `https://<your-LAN-IP>:8443/` on the phone and accept the certificate warning once.

## Training

```
cd backend
.venv/Scripts/python.exe ../scripts/generate_dataset.py
.venv/Scripts/python.exe ../scripts/train.py
.venv/Scripts/python.exe ../scripts/evaluate.py
```

## Testing

```
cd backend
.venv/Scripts/python.exe -m pytest -v
```

## Demo

```
cd backend
.venv/Scripts/python.exe ../scripts/predict.py path/to/image.png --save-overlay out.png
```
Runs the full pipeline on a single image and prints the JSON `AnalysisResult` — the
primary way to see the system work end-to-end without the (unverified) Flutter app.
