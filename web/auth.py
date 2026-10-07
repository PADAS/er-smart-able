"""Who is calling: Firebase Authentication with an email/domain allowlist.

Two ways in, both checked against ALLOWED_EMAILS (default "@earthranger.com";
comma-separated emails or @domains):
- a Firebase session cookie, set by POST /api/session after the browser signs
  in with Google. The browser page under /d/<id>/ loads JSON and photos with
  plain requests, so the credential has to be a cookie, not a header.
- an "Authorization: Bearer <id token>" header, for scripts.

AUTH_DISABLED=true (local development) trusts an X-Dev-User header or a
dev_user cookie and never talks to Firebase.
"""
import logging
import os
from datetime import timedelta

from fastapi import HTTPException, Request, Response

logger = logging.getLogger(__name__)

AUTH_DISABLED = os.environ.get("AUTH_DISABLED", "").lower() == "true"
ALLOWED_EMAILS = os.environ.get("ALLOWED_EMAILS", "@earthranger.com")
SESSION_COOKIE = "session"
SESSION_DAYS = 5

_firebase_initialized = False


def _init_firebase():
    global _firebase_initialized
    if _firebase_initialized:
        return
    import firebase_admin
    firebase_admin.initialize_app()
    _firebase_initialized = True


def email_allowed(email: str) -> bool:
    email = (email or "").lower()
    entries = [e.strip().lower() for e in ALLOWED_EMAILS.split(",") if e.strip()]
    if not entries:
        return True
    return any(email.endswith(e) if e.startswith("@") else email == e for e in entries)


def _dev_user(request: Request) -> dict:
    email = request.headers.get("X-Dev-User") or request.cookies.get("dev_user") or "dev@earthranger.com"
    uid = "dev_" + email.replace("@", "_at_").replace(".", "_")
    return {"uid": uid, "email": email, "name": email.split("@")[0]}


def _from_decoded(decoded: dict) -> dict:
    email = decoded.get("email", "")
    if not email_allowed(email):
        raise HTTPException(status_code=403, detail="This email is not allowed to use smart-able")
    return {"uid": decoded["uid"], "email": email, "name": decoded.get("name") or email}


async def current_user(request: Request) -> dict:
    """FastAPI dependency: the signed-in, allowlisted user, or 401/403."""
    if AUTH_DISABLED:
        return _dev_user(request)
    _init_firebase()
    from firebase_admin import auth

    cookie = request.cookies.get(SESSION_COOKIE)
    if cookie:
        try:
            return _from_decoded(auth.verify_session_cookie(cookie, check_revoked=False))
        except HTTPException:
            raise
        except Exception as e:  # expired, tampered, or from another project
            logger.info("session cookie rejected: %s", e)
    authorization = request.headers.get("Authorization", "")
    if authorization.startswith("Bearer "):
        try:
            return _from_decoded(auth.verify_id_token(authorization[7:]))
        except HTTPException:
            raise
        except Exception as e:
            logger.info("id token rejected: %s", e)
            raise HTTPException(status_code=401, detail="Invalid or expired token")
    raise HTTPException(status_code=401, detail="Sign in required")


def start_session(response: Response, request: Request, id_token: str) -> dict:
    """Exchange a Firebase ID token for a session cookie. Returns the user."""
    secure = request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https"
    if AUTH_DISABLED:
        user = _dev_user(request)
        response.set_cookie("dev_user", user["email"], httponly=True, samesite="lax", secure=secure)
        return user
    _init_firebase()
    from firebase_admin import auth

    try:
        decoded = auth.verify_id_token(id_token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    user = _from_decoded(decoded)
    expires = timedelta(days=SESSION_DAYS)
    cookie = auth.create_session_cookie(id_token, expires_in=expires)
    response.set_cookie(SESSION_COOKIE, cookie, max_age=int(expires.total_seconds()),
                        httponly=True, samesite="lax", secure=secure, path="/")
    return user


def end_session(response: Response):
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.delete_cookie("dev_user", path="/")
