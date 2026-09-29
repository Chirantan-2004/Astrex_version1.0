# ASTRAX — TEAM NEXUS
### SIH26174 · AI Human Activity Recognition for On-board BAS Experiment

A local-first crew operations prototype for the Team NEXUS concept. Fresh camera observations are checked against a deterministic procedure, uncertainty holds the step, and crew messages remain durable while disconnected instead of pretending an uplink succeeded.

## What is genuinely implemented

### Mission software
- FastAPI local server
- OIDC sign-in with signed, HttpOnly session cookies
- Crew-to-mission-support outbox with durable local queue status
- Responsive field-operations dashboard with live candidate age and confidence
- Deterministic experiment protocol engine
- Automatic camera-to-protocol supervision when a fresh observation is available
- Three distinct, consistent observations within a one-second window
- Stale, duplicate, idle, or out-of-order sensor evidence holds/resets consensus
- Correct-step verification
- Out-of-order detection with expected vs detected explanation
- Offline TTS integration with graceful fallback
- SQLite structured event memory
- JSON/CSV export
- Local experiment video recording
- Loopback-only MJPEG video endpoint

### Perception
- OpenCV camera capture
- OpenCV red/yellow object segmentation fallback
- Motion estimation
- Optional Ultralytics YOLO pose backend
- Hand/object interaction logic when pose keypoints are available
- Annotated camera feed
- Vision telemetry: activity, confidence, objects, interaction, latency, FPS

### AI development path
- Dataset collection script
- Activity training scaffold
- Optional YOLO model bootstrap script
- Explicit separation between probabilistic perception and deterministic protocol validation

## Important scientific boundary

This is a **functional terrestrial prototype**, not a spaceflight-qualified system. The OpenCV fallback is a heuristic and does not currently recognize the full OPEN/PICK/INSERT/ROTATE/CLOSE procedure; an experiment-specific action model and labeled validation set are required before hands-off procedure recognition can be claimed. A false recognition could be dangerous, so stale or low-confidence observations never advance the procedure. This repository does not claim microgravity validation, representative astronaut-HAR accuracy, flight certification, or official BAS procedure coverage.

The mission-support panel stores crew messages locally as `QUEUED_LOCAL`. No ground relay transport is implemented yet, so the UI deliberately reports **NO RELAY** until a real, authenticated transport and ground-station service are designed and tested.

## Recommended environment

For the core app, Python 3.11+ is suitable. For the optional AI stack, prefer Python 3.11 or 3.12 because compatibility of heavyweight vision packages varies by Python release.

## Windows — one command

```powershell
cd astrax
Set-ExecutionPolicy -Scope Process Bypass
.\run_windows.bat
```

The launcher creates a virtual environment, installs the core/runtime requirements and starts the dashboard at:

`http://127.0.0.1:8000`

Before local judge/demo use, create `.env` from `.env.example` and set `ASTRO_ALLOW_LOCAL_AUTH=true`. The default intentionally does not grant access without OIDC.

> Both launchers bind to `127.0.0.1`; open the dashboard on the same machine. Protected APIs fail closed unless OIDC is configured or local demo mode is explicitly enabled. Do not bind to a network interface until TLS, identity-provider registration, host allowlisting, and a ground-relay security review are complete.

## Identity and access

For an OIDC deployment, copy `.env.example` to `.env`, register the exact `/auth/callback` URI with your identity provider, and configure `ASTRO_OIDC_DISCOVERY_URL`, `ASTRO_OIDC_CLIENT_ID`, `ASTRO_OIDC_CLIENT_SECRET`, `ASTRO_OIDC_REDIRECT_URI`, and a random `ASTRO_SESSION_SECRET` of at least 32 characters. Set `ASTRO_COOKIE_SECURE=true` behind HTTPS and set `ASTRO_ALLOWED_HOSTS` to the exact service hosts. `ASTRO_ALLOWED_EMAIL_DOMAINS` can restrict sign-in to approved domains. Keep `.env` private; never commit provider secrets.

For OIDC testing over plain HTTP on loopback only, `ASTRO_COOKIE_SECURE=false` is required for the callback cookie to work. Never use that setting on a shared or network-accessible deployment.

For a judge/demo machine only, set `ASTRO_ALLOW_LOCAL_AUTH=true` and keep the server loopback-only. This explicit bypass is not suitable for crew deployments. Without either OIDC or the local demo bypass, mission-control APIs return `503` rather than running unauthenticated.

## Deploy to Vercel

The Vercel configuration uses the FastAPI app in `app/main.py` and installs only the lightweight web/runtime dependencies. From the project root (the directory containing `app/`), deploy with:

```powershell
npx vercel@latest
npx vercel@latest --prod
```

The first command links the project and creates a preview deployment; the second promotes a production deployment. You can also import the repository in Vercel, making sure the Root Directory is the folder containing `app/`. Set the following Project Environment Variables before promoting a deployment:

| Variable | Value |
| --- | --- |
| `ASTRO_OIDC_DISCOVERY_URL` | `https://accounts.google.com/.well-known/openid-configuration` for Google, or your provider's OIDC discovery URL |
| `ASTRO_OIDC_CLIENT_ID` | OAuth client ID created in your identity provider |
| `ASTRO_OIDC_CLIENT_SECRET` | OAuth client secret; keep it only in Vercel's encrypted environment settings |
| `ASTRO_OIDC_REDIRECT_URI` | `https://YOUR_PROJECT.vercel.app/auth/callback` (must exactly match the provider registration) |
| `ASTRO_SESSION_SECRET` | A random value of at least 32 characters; generate locally with `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `ASTRO_ALLOWED_HOSTS` | The exact production Vercel hostname, plus any custom domain, comma-separated |
| `ASTRO_COOKIE_SECURE` | `true` |
| `ASTRO_ALLOW_LOCAL_AUTH` | `false` |
| `ASTRO_ENABLE_AUTHENTICATED_DEMO` | `true` only if signed-in users should be able to run the simulated demo |

For Google OAuth, create an OAuth client of type **Web application** in Google Cloud Console. Add your production URL as an authorized JavaScript origin, and add the exact callback above as an authorized redirect URI. Copy the client ID and secret into Vercel; those provider credentials are unique to your account and must be created there. Add `ASTRO_ALLOWED_EMAIL_DOMAINS` if sign-in should be limited to verified email domains. After setting variables, redeploy so the function starts with the OIDC configuration.

Vercel serverless storage is temporary and may differ between function instances. This deployment stores SQLite and recordings under `/tmp`; experiment history is therefore not durable or guaranteed to be shared across instances. Camera capture, live video, and local TTS require the original machine and are unavailable in Vercel. Use Vercel for an authenticated dashboard/demo preview, not as the durable mission-recording or camera host. Keep `ASTRO_ENABLE_AUTHENTICATED_DEMO=false` unless this is intentionally a simulated demonstration.

## Linux/macOS

```bash
cd astrax
chmod +x run_linux.sh
./run_linux.sh
```

## Install the optional AI stack

```powershell
.\.venv\Scripts\activate
pip install -r requirements-ai.txt
python scripts/download_models.py
```

If Ultralytics is unavailable on the current Python build, the application continues using the OpenCV fallback. Ultralytics supports local image/video/webcam inference and ONNX export; see the official documentation linked in the project handoff.

## Demo mode — judge-safe

1. Enable the explicit local demo bypass in `.env` and start the dashboard.
2. Click **Start / restart**.
3. Click **Correct Step** to verify actions.
4. Click **Inject Error** to trigger a protocol violation.
5. Show expected vs detected action and guidance.
6. Continue to **Experiment Complete**.
7. Export JSON/CSV.

The deterministic demo is intentionally independent of the optional ML stack so a judging session does not fail because of camera drivers, model downloads or GPU issues.

## Live camera mode

1. Authenticate with the configured mission identity, then click **Acquire camera**.
2. The app opens camera index 0.
3. OpenCV performs local perception.
4. If Ultralytics YOLO pose is installed and its model is available, pose keypoints are added to the pipeline.
5. Each new frame is analyzed automatically; the protocol accepts only fresh, consecutive observations at or above the confidence threshold within one second.
6. No manual replay/confirmation of a cached frame is available. A stale or unavailable sensor puts supervision on hold.

## Project layout

```text
astrax/
├── .agent                 # agent/project operating instructions
├── .agent.md              # detailed implementation instructions
├── README.md
├── PROJECT_SPEC.md
├── requirements-core.txt
├── requirements-ai.txt
├── requirements.txt
├── .env.example
├── run_windows.bat
├── run_linux.sh
│
├── app/
│   ├── main.py
│   ├── database.py
│   ├── protocol.py
│   ├── schemas.py
│   ├── services/
│   │   ├── activity.py
│   │   ├── perception.py
│   │   ├── vision.py
│   │   ├── tts.py
│   │   └── video.py
│   └── static/
│       ├── index.html
│       ├── app.js
│       └── styles.css
│
├── data/
│   ├── protocol.json
│   └── experiments/
├── models/
├── scripts/
│   ├── check_install.py
│   ├── collect_dataset.py
│   ├── download_models.py
│   └── train_activity.py
├── tests/
│   ├── test_protocol.py
│   └── test_vision.py
└── docs/
    ├── ARCHITECTURE.md
    ├── DEMO_RUNBOOK.md
    └── JUDGE_QA.md
```

## Verification

```powershell
python -m compileall -q app scripts tests
python -m pytest -q
python scripts/check_install.py
```

The suite covers API authentication, fail-closed freshness, automatic supervision, camera lifecycle, and experiment/outbox persistence.

## Next research/deployment stages

1. Collect experiment-specific video and labels.
2. Define the official experiment protocol from the authorized procedure.
3. Train and validate the activity/interaction model.
4. Evaluate precision, recall, false alerts, missed steps and temporal latency.
5. Add domain augmentation for lighting, occlusion and camera variation.
6. Export/optimize models for ONNX/TensorRT and benchmark on edge hardware.
7. Add hardware-in-the-loop tests.
8. Validate against relevant microgravity/spaceflight datasets and conditions before making deployment claims.
