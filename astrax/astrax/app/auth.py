from __future__ import annotations

import os
import secrets

from authlib.integrations.starlette_client import OAuth
from fastapi import HTTPException, Request
from starlette.middleware.sessions import SessionMiddleware


oauth = OAuth()
discovery_url = os.getenv("ASTRO_OIDC_DISCOVERY_URL", "").strip()
client_id = os.getenv("ASTRO_OIDC_CLIENT_ID", "").strip()
client_secret = os.getenv("ASTRO_OIDC_CLIENT_SECRET", "").strip()
redirect_uri = os.getenv("ASTRO_OIDC_REDIRECT_URI", "").strip()
oidc_client = None

if any((discovery_url, client_id, client_secret, redirect_uri)):
    if not all((discovery_url, client_id, client_secret, redirect_uri)):
        raise RuntimeError("OIDC requires discovery URL, client ID, client secret, and redirect URI")
    oidc_client = oauth.register(
        name="astrax",
        server_metadata_url=discovery_url,
        client_id=client_id,
        client_secret=client_secret,
        client_kwargs={"scope": "openid profile email"},
    )

configured_session_secret = os.getenv("ASTRO_SESSION_SECRET", "").strip()
if oidc_client and len(configured_session_secret) < 32:
    raise RuntimeError("ASTRO_SESSION_SECRET must contain at least 32 characters when OIDC is enabled")
session_secret = configured_session_secret or secrets.token_urlsafe(48)


def local_auth_allowed() -> bool:
    return os.getenv("ASTRO_ALLOW_LOCAL_AUTH", "false").lower() == "true"


def add_session_middleware(app):
    secure_cookie = os.getenv("ASTRO_COOKIE_SECURE", "true").lower() == "true"
    app.add_middleware(
        SessionMiddleware,
        secret_key=session_secret,
        session_cookie="astrax_session",
        max_age=8 * 60 * 60,
        same_site="lax",
        https_only=secure_cookie,
    )


def session_status(request: Request) -> dict:
    user = request.session.get("user")
    local_auth = local_auth_allowed()
    local_demo = local_auth and oidc_client is None
    authenticated = bool(user) or local_demo
    authenticated_demo = (
        bool(user) and os.getenv("ASTRO_ENABLE_AUTHENTICATED_DEMO", "false").lower() == "true"
    )
    return {
        "authenticated": authenticated,
        "user": user or ({"name": "Local demo operator", "role": "local-demo"} if local_auth else None),
        "oidc_enabled": oidc_client is not None,
        "login_available": oidc_client is not None,
        "local_auth": local_demo,
        "demo_mode": local_demo or authenticated_demo,
    }


async def begin_login(request: Request):
    if oidc_client is None:
        raise HTTPException(status_code=503, detail="OIDC identity provider is not configured")
    return await oidc_client.authorize_redirect(request, redirect_uri)


async def complete_login(request: Request):
    if oidc_client is None:
        raise HTTPException(status_code=503, detail="OIDC identity provider is not configured")
    try:
        token = await oidc_client.authorize_access_token(request)
        userinfo = token.get("userinfo") or await oidc_client.userinfo(token=token)
    except Exception as exc:
        raise HTTPException(status_code=401, detail="OIDC sign-in could not be verified") from exc

    subject = userinfo.get("sub")
    if not subject:
        raise HTTPException(status_code=401, detail="OIDC response did not contain a subject")

    email = userinfo.get("email", "")
    allowed_domains = {
        domain.strip().lower()
        for domain in os.getenv("ASTRO_ALLOWED_EMAIL_DOMAINS", "").split(",")
        if domain.strip()
    }
    if allowed_domains:
        email_domain = email.rsplit("@", 1)[-1].lower() if "@" in email else ""
        if not userinfo.get("email_verified") or email_domain not in allowed_domains:
            raise HTTPException(status_code=403, detail="This account is not allowed to access ASTRAX")

    role = userinfo.get("role", "operator")
    if role not in {"crew", "mission_control", "admin", "operator"}:
        role = "operator"
    request.session.clear()
    request.session["user"] = {
        "sub": subject,
        "email": email,
        "name": userinfo.get("name") or email or "ASTRAX operator",
        "role": role,
    }