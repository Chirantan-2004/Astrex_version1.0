from datetime import datetime, timezone
from pathlib import Path
import json
import time
import os
import threading
from urllib.parse import urlsplit

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

BASE = Path(__file__).resolve().parent
STATIC = BASE / "static"
load_dotenv(BASE.parent / ".env")

from .auth import add_session_middleware, begin_login, complete_login, local_auth_allowed, oidc_client, session_status
from .database import add_communication, add_event, communications, export_csv, export_json, finish_experiment, init_db, list_experiments, new_experiment_id, start_experiment
from .protocol import PROTOCOL, ProtocolEngine
from .schemas import ActivityObservation, CommunicationCreate
from .services.activity import TemporalActivityFilter
from .services.ai import AIIntegration
from .services.perception import OptionalPerception
from .services.tts import speak
from .services.video import VideoService
from .services.vision import VisionEngine

EXPERIMENT_ID = new_experiment_id()
EXPERIMENT_NAME = "BAS Sample Experiment"
VISION_MAX_AGE_SECONDS = 1.0

app = FastAPI(title="ASTRAX — TEAM NEXUS", version="2.0.0")
allowed_hosts = [
    host.strip()
    for host in [
        *os.getenv("ASTRO_ALLOWED_HOSTS", "127.0.0.1,localhost").split(","),
        os.getenv("VERCEL_URL", ""),
        os.getenv("VERCEL_BRANCH_URL", ""),
        os.getenv("VERCEL_PROJECT_PRODUCTION_URL", ""),
    ]
    if host.strip()
]
app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)


@app.middleware("http")
async def reject_cross_origin_mutations(request: Request, call_next):
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        origin = request.headers.get("origin")
        if origin:
            parsed_origin = urlsplit(origin)
            if parsed_origin.scheme != request.url.scheme or parsed_origin.netloc != request.headers.get("host"):
                return secure_response(JSONResponse(status_code=403, content={"detail": "Cross-origin changes are not allowed"}))
        if request.headers.get("sec-fetch-site") == "cross-site":
            return secure_response(JSONResponse(status_code=403, content={"detail": "Cross-origin changes are not allowed"}))
    path = request.url.path
    protected = (path.startswith("/api/") and path not in {"/api/health", "/api/auth/session"}) or path == "/video_feed"
    if protected:
        if oidc_client is None and not local_auth_allowed():
            return secure_response(JSONResponse(status_code=503, content={"detail": "Configure an OIDC identity provider before using protected mission controls"}))
        if oidc_client is not None and not request.session.get("user"):
            return secure_response(JSONResponse(status_code=401, content={"detail": "Sign in with your mission identity to continue"}))
        simulation_route = path.startswith("/api/demo/") or path == "/api/observe"
        authenticated_demo = (
            bool(request.session.get("user"))
            and os.getenv("ASTRO_ENABLE_AUTHENTICATED_DEMO", "false").lower() == "true"
        )
        local_demo = oidc_client is None and local_auth_allowed()
        if simulation_route and not (local_demo or authenticated_demo):
            return secure_response(JSONResponse(status_code=403, content={"detail": "Simulation and injected observations are disabled outside local demo mode"}))
    return secure_response(await call_next(request))


def secure_response(response):
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; base-uri 'self'; object-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; form-action 'self'; frame-ancestors 'none'",
    )
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    return response


add_session_middleware(app)
app.mount("/static", StaticFiles(directory=STATIC), name="static")

init_db()
engine = ProtocolEngine()
temporal = TemporalActivityFilter(window=3, min_confidence=0.70)
vision = VisionEngine()
video = VideoService(vision=vision)
perception = OptionalPerception()
ai = AIIntegration()
offline_mode = True
engine_lock = threading.RLock()


def snapshot():
    with engine_lock:
        expected = engine.expected
        last = engine.events[-1] if engine.events else None
        age_ms = (time.monotonic() - vision.last_ts) * 1000 if vision.last_ts else None
        candidate = vision.last
        return {
            "experiment_id": EXPERIMENT_ID,
            "name": EXPERIMENT_NAME,
            "status": engine.status,
            "current_step": min(engine.index + 1, len(PROTOCOL)),
            "total_steps": len(PROTOCOL),
            "expected_activity": expected,
            "detected_activity": last["detected_activity"] if last else None,
            "confidence": last["confidence"] if last else 0.0,
            "protocol": PROTOCOL,
            "events": engine.events,
            "last_message": engine.last_message,
            "offline": offline_mode,
            "recording": video.recording,
            "stream_available": video.running,
            "started_at": engine.started_at,
            "perception": perception.status,
            "vision": vision.status,
            "candidate": {
                "activity": candidate.activity,
                "confidence": candidate.confidence,
                "age_ms": age_ms,
                "fresh": bool(video.running and age_ms is not None and age_ms <= VISION_MAX_AGE_SECONDS * 1000),
            },
            "automatic_supervision": engine.status in {"RUNNING", "ALERT"} and video.running,
            "camera": video.status,
        }


def persist_observation(activity: str, confidence: float, source: str, observed_at: float | None = None):
    with engine_lock:
        if engine.status == "READY":
            raise HTTPException(400, "Start the experiment first")
        confirmed = temporal.observe(activity, confidence, observed_at=observed_at)
        if confirmed is None:
            return {"confirmed": False, **snapshot()}

        expected_before = engine.expected
        event = engine.observe(confirmed, confidence, source)
        event["expected_activity"] = expected_before
        add_event(EXPERIMENT_ID, event, expected_before)

        if event["status"] == "OUT_OF_ORDER":
            speak(f"Warning. Incorrect experiment sequence. {engine.last_message}")
        elif event["status"] in {"VALID", "COMPLETE"}:
            speak("Experiment completed successfully." if engine.complete else engine.last_message)
        if engine.complete:
            finish_experiment(EXPERIMENT_ID, datetime.now(timezone.utc).isoformat(), "COMPLETED")
        return {"confirmed": True, "event": event, **snapshot()}


def process_vision_observation(observation):
    with engine_lock:
        if observation.activity == "IDLE":
            temporal.observe(observation.activity, observation.confidence, observed_at=vision.last_ts)
            return None
        if engine.status not in {"RUNNING", "ALERT"}:
            return None
        age = time.monotonic() - vision.last_ts if vision.last_ts else float("inf")
        if age > VISION_MAX_AGE_SECONDS:
            temporal.clear_history(vision.last_ts)
            return None
        return persist_observation(
            observation.activity,
            observation.confidence,
            observation.source,
            observed_at=vision.last_ts,
        )


video.on_observation = process_vision_observation


@app.get("/", response_class=HTMLResponse)
def root():
    return (STATIC / "index.html").read_text(encoding="utf-8")


@app.get("/auth/login")
async def auth_login(request: Request):
    return await begin_login(request)


@app.get("/auth/callback")
async def auth_callback(request: Request):
    await complete_login(request)
    return RedirectResponse("/", status_code=303)


@app.post("/auth/logout")
def auth_logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=303)


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "service": "ASTRAX",
        "offline": offline_mode,
        "version": app.version,
        "ai": ai.status(),
        "camera": video.status,
        "perception": perception.status,
    }


@app.get("/api/auth/session")
def auth_session(request: Request):
    return session_status(request)


@app.get("/api/status")
def status():
    return snapshot()


@app.get("/api/experiments")
def experiment_history():
    return list_experiments()


@app.get("/api/comms/messages")
def list_communications():
    return communications()


@app.post("/api/comms/messages")
def send_communication(payload: CommunicationCreate, request: Request):
    user = request.session.get("user", {})
    sender = user.get("email") or user.get("name") or "local demo operator"
    message = add_communication("UPLINK", sender, payload.message)
    return {**message, "relay_configured": False}


@app.post("/api/demo/start")
def demo_start():
    global EXPERIMENT_ID
    with engine_lock:
        EXPERIMENT_ID = new_experiment_id()
        engine.start()
        temporal.reset()
        start_experiment(EXPERIMENT_ID, EXPERIMENT_NAME, engine.started_at)
        return snapshot()


@app.post("/api/demo/reset")
def demo_reset():
    global EXPERIMENT_ID
    with engine_lock:
        engine.reset()
        temporal.reset()
        EXPERIMENT_ID = new_experiment_id()
        return snapshot()


@app.post("/api/demo/next-correct")
def next_correct():
    with engine_lock:
        if engine.status == "READY":
            demo_start()
        expected = engine.expected
        result = None
        for _ in range(3):
            result = persist_observation(expected or "IDLE", 0.94, "demo")
        return result


@app.post("/api/demo/wrong")
def wrong_step():
    with engine_lock:
        if engine.status == "READY":
            demo_start()
        expected = engine.expected
        wrong = next((x["activity"] for x in PROTOCOL if x["activity"] != expected), "IDLE")
        result = None
        for _ in range(3):
            result = persist_observation(wrong, 0.92, "demo")
        return result


@app.post("/api/observe")
def observe(payload: ActivityObservation):
    return persist_observation(payload.activity, payload.confidence, payload.source)


@app.post("/api/vision/commit")
def commit_vision():
    with engine_lock:
        obs = vision.last
        age = time.monotonic() - vision.last_ts if vision.last_ts else float("inf")
        if age > VISION_MAX_AGE_SECONDS:
            temporal.clear_history(vision.last_ts)
            return {"confirmed": False, "reason": "Vision observation is stale; protocol held for fresh input.", **snapshot()}
        return {"confirmed": False, "reason": "Fresh frames are supervised automatically; no manual replay of cached frames.", **snapshot()}


@app.post("/api/mode")
def set_mode(payload: dict):
    global offline_mode
    offline_mode = bool(payload.get("offline", True))
    return snapshot()


@app.get("/api/logs/{experiment_id}.json")
def logs_json(experiment_id: str):
    return PlainTextResponse(export_json(experiment_id), media_type="application/json", headers={"Content-Disposition": f"attachment; filename={experiment_id}.json"})


@app.get("/api/logs/{experiment_id}.csv")
def logs_csv(experiment_id: str):
    return PlainTextResponse(export_csv(experiment_id), media_type="text/csv", headers={"Content-Disposition": f"attachment; filename={experiment_id}.csv"})


@app.post("/api/camera/start")
def camera_start(payload: dict | None = None):
    if os.getenv("VERCEL"):
        raise HTTPException(503, "Camera capture is unavailable in Vercel serverless functions")
    index = int((payload or {}).get("index", 0))
    if vision.model is None:
        vision.load("yolo26n-pose.pt")
    ok = video.start_camera(index)
    return {"ok": ok, **snapshot()}


@app.post("/api/camera/stop")
def camera_stop():
    video.stop_camera()
    return {"ok": True, **snapshot()}


@app.post("/api/camera/record")
def camera_record():
    if not video.running:
        raise HTTPException(400, "Start the camera first")
    ok = video.start_recording(EXPERIMENT_ID)
    return {"ok": ok, **snapshot()}


@app.post("/api/camera/record/stop")
def camera_record_stop():
    video.stop_recording()
    return {"ok": True, **snapshot()}


@app.get("/video_feed")
def video_feed():
    if not video.running:
        raise HTTPException(503, "Camera is not running")
    return StreamingResponse(video.frames(), media_type="multipart/x-mixed-replace; boundary=frame")
