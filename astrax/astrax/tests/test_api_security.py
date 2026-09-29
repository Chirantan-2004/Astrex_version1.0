import importlib
import base64
import csv
import io
import json
import time

import pytest
from itsdangerous import TimestampSigner
from fastapi.testclient import TestClient
from app.services.vision import VisionObservation


@pytest.fixture
def client(tmp_path, monkeypatch):
    from app import database

    monkeypatch.setattr(database, "DB_PATH", tmp_path / "astrax.db")
    monkeypatch.setenv("ASTRO_ALLOW_LOCAL_AUTH", "true")
    monkeypatch.setenv("ASTRO_SESSION_SECRET", "test-session-secret-with-more-than-32-characters")
    monkeypatch.setenv("ASTRO_ALLOWED_HOSTS", "127.0.0.1,localhost,testserver")
    from app import main

    importlib.reload(main)
    with TestClient(main.app) as test_client:
        yield test_client


def test_browser_cross_origin_cannot_mutate_experiment(client):
    response = client.post("/api/demo/reset", headers={"Origin": "https://attacker.example"})

    assert response.status_code == 403
    assert client.get("/api/status").json()["status"] == "READY"


def test_untrusted_host_is_rejected(client):
    response = client.get("/api/health", headers={"Host": "attacker.example"})

    assert response.status_code == 400


def test_mission_responses_set_browser_security_headers(client):
    response = client.get("/api/health")

    assert response.headers["content-security-policy"].startswith("default-src 'self'")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"


def test_browser_scheme_change_is_also_cross_origin(client):
    response = client.post("/api/demo/reset", headers={"Origin": "https://testserver"})

    assert response.status_code == 403


def test_protected_api_fails_closed_without_oidc_or_local_mode(client, monkeypatch):
    monkeypatch.setenv("ASTRO_ALLOW_LOCAL_AUTH", "false")

    response = client.get("/api/status")

    assert response.status_code == 503


def test_configured_oidc_requires_a_verified_session(client, monkeypatch):
    from app import main

    monkeypatch.setenv("ASTRO_ALLOW_LOCAL_AUTH", "false")
    monkeypatch.setattr(main, "oidc_client", object())

    response = client.get("/api/status")

    assert response.status_code == 401


def test_oidc_session_cannot_call_demo_or_forge_activity(client, monkeypatch):
    from app import auth, main

    monkeypatch.setenv("ASTRO_ALLOW_LOCAL_AUTH", "false")
    monkeypatch.setattr(main, "oidc_client", object())
    session = {"user": {"sub": "crew-123", "name": "Crew member", "role": "crew"}}
    payload = base64.b64encode(json.dumps(session, separators=(",", ":")).encode())
    signed_cookie = TimestampSigner(auth.session_secret).sign(payload).decode()
    client.cookies.set("astrax_session", signed_cookie)

    assert client.get("/api/status").status_code == 200
    assert client.post("/api/demo/start").status_code == 403
    assert client.post("/api/observe", json={"activity": "OPEN", "confidence": 1.0, "source": "camera"}).status_code == 403


def test_oidc_user_cannot_use_demo_when_local_bypass_is_enabled(client, monkeypatch):
    from app import auth, main

    monkeypatch.setattr(main, "oidc_client", object())
    session = {"user": {"sub": "crew-123", "name": "Crew member", "role": "crew"}}
    payload = base64.b64encode(json.dumps(session, separators=(",", ":")).encode())
    client.cookies.set("astrax_session", TimestampSigner(auth.session_secret).sign(payload).decode())

    assert client.get("/api/status").status_code == 200
    assert client.post("/api/demo/start").status_code == 403
    assert client.post("/api/observe", json={"activity": "OPEN", "confidence": 1.0, "source": "camera"}).status_code == 403


def test_authenticated_demo_requires_oidc_and_explicit_enablement(client, monkeypatch):
    from app import auth, main

    monkeypatch.setenv("ASTRO_ALLOW_LOCAL_AUTH", "false")
    monkeypatch.setenv("ASTRO_ENABLE_AUTHENTICATED_DEMO", "true")
    monkeypatch.setattr(main, "oidc_client", object())
    session = {"user": {"sub": "crew-123", "name": "Crew member", "role": "crew"}}
    payload = base64.b64encode(json.dumps(session, separators=(",", ":")).encode())
    client.cookies.set("astrax_session", TimestampSigner(auth.session_secret).sign(payload).decode())

    assert client.get("/api/auth/session").json()["demo_mode"] is True
    assert client.post("/api/demo/start").status_code == 200


def test_local_demo_mode_does_not_weaken_secure_cookie_setting(monkeypatch):
    from fastapi import FastAPI
    from app.auth import add_session_middleware

    monkeypatch.setenv("ASTRO_ALLOW_LOCAL_AUTH", "true")
    monkeypatch.setenv("ASTRO_COOKIE_SECURE", "true")
    app = FastAPI()
    add_session_middleware(app)
    middleware = next(item for item in app.user_middleware if item.cls.__name__ == "SessionMiddleware")

    assert middleware.kwargs["https_only"] is True


def test_unverified_email_cannot_satisfy_domain_allowlist(client, monkeypatch):
    from app import auth

    class FakeOIDCClient:
        async def authorize_access_token(self, request):
            return {"userinfo": {
                "sub": "crew-123",
                "email": "crew@example.test",
                "email_verified": False,
            }}

    monkeypatch.setattr(auth, "oidc_client", FakeOIDCClient())
    monkeypatch.setenv("ASTRO_ALLOWED_EMAIL_DOMAINS", "example.test")

    response = client.get("/auth/callback")

    assert response.status_code == 403


def test_same_origin_experiment_controls_remain_available(client):
    response = client.post("/api/demo/start", headers={"Origin": "http://testserver"})

    assert response.status_code == 200
    assert response.json()["status"] == "RUNNING"
    assert response.json()["experiment_id"].startswith("BAS-001-")


def test_camera_capture_is_unavailable_in_vercel_functions(client, monkeypatch):
    monkeypatch.setenv("VERCEL", "1")

    response = client.post("/api/camera/start", json={"index": 0})

    assert response.status_code == 503
    assert "unavailable in Vercel" in response.json()["detail"]


def test_demo_run_archives_events_and_exports(client):
    assert client.get("/").status_code == 200
    assert client.get("/api/health").json()["status"] == "ok"
    assert client.get("/api/status").json()["status"] == "READY"

    started = client.post("/api/demo/start").json()
    experiment_id = started["experiment_id"]
    first_step = client.post("/api/demo/next-correct").json()
    assert first_step["status"] == "RUNNING"
    wrong_step = client.post("/api/demo/wrong").json()
    assert wrong_step["status"] == "ALERT"
    assert wrong_step["current_step"] == 2

    for _ in range(4):
        result = client.post("/api/demo/next-correct").json()
    assert result["status"] == "COMPLETED"

    json_export = json.loads(client.get(f"/api/logs/{experiment_id}.json").text)
    csv_rows = list(csv.DictReader(io.StringIO(client.get(f"/api/logs/{experiment_id}.csv").text)))
    assert len(json_export["events"]) == 6
    assert len(csv_rows) == 6

    reset = client.post("/api/demo/reset").json()
    assert reset["experiment_id"] != experiment_id
    assert len(json.loads(client.get(f"/api/logs/{experiment_id}.json").text)["events"]) == 6
    assert any(run["id"] == experiment_id for run in client.get("/api/experiments").json())


def test_stale_vision_never_advances_protocol(client):
    from app import main

    client.post("/api/demo/start")
    main.vision.last = VisionObservation(activity="OPEN", confidence=0.99, source="test")
    main.vision.last_ts = time.monotonic() - 1.1

    responses = [client.post("/api/vision/commit").json() for _ in range(3)]

    assert all(response["confirmed"] is False for response in responses)
    assert all("stale" in response.get("reason", "").lower() for response in responses)
    assert main.engine.index == 0


def test_new_camera_observations_advance_without_manual_commit(client):
    from app import main

    client.post("/api/demo/start")
    for _ in range(3):
        main.vision.last_ts = time.monotonic()
        main.video.on_observation(VisionObservation(activity="OPEN", confidence=0.95, source="camera-test"))

    assert main.engine.index == 1
    assert main.engine.events[-1]["source"] == "camera-test"


def test_idle_camera_signal_breaks_consensus(client):
    from app import main

    client.post("/api/demo/start")
    for activity in ("OPEN", "OPEN", "IDLE", "OPEN", "OPEN"):
        main.vision.last_ts = time.monotonic()
        main.video.on_observation(VisionObservation(activity=activity, confidence=0.95, source="camera-test"))

    assert main.engine.index == 0
    main.vision.last_ts = time.monotonic()
    main.video.on_observation(VisionObservation(activity="OPEN", confidence=0.95, source="camera-test"))
    assert main.engine.index == 1


def test_uplink_is_saved_as_local_queue_not_claimed_delivered(client, monkeypatch):
    monkeypatch.setenv("ASTRO_GROUND_RELAY_URL", "https://relay.invalid")
    response = client.post("/api/comms/messages", json={"message": "Request next-step guidance."})

    assert response.status_code == 200
    assert response.json()["direction"] == "UPLINK"
    assert response.json()["delivery_status"] == "QUEUED_LOCAL"
    assert response.json()["relay_configured"] is False
    assert client.get("/api/comms/messages").json()[-1]["message"] == "Request next-step guidance."