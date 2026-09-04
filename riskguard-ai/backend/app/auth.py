"""Minimal RBAC layer for the buildathon demo (no external dependencies).

Roles:
    viewer  -> read-only analytics and lists
    analyst -> + review decisions, alert handling, feedback outcomes, ingestion
    admin   -> + model retraining/approval and settings

Passwords: salted PBKDF2-HMAC-SHA256 (stdlib), stored as
`pbkdf2$<iterations>$<salt_b64>$<hash_b64>`.
Tokens: stateless HMAC-SHA256 signed `header.payload.signature` with an expiry
claim (`exp`), signed with SECRET_KEY. No JWKS/certs needed for the demo.
"""
import base64
import hashlib
import hmac
import json
import os
import time

from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.models.database import SessionLocal
from app.models.models import User

load_dotenv()

ROLES = ("viewer", "analyst", "admin")
ROLE_RANK = {"viewer": 0, "analyst": 1, "admin": 2}

_HASH_ALGO = "sha256"
_PBKDF2_ITERATIONS = 100_000
_MAX_TOKEN_AGE_SECONDS = 8 * 60 * 60

_bearer = HTTPBearer(auto_error=False)


def _secret_key() -> bytes:
    key = os.getenv("SECRET_KEY", "change-me-in-production")
    return key.encode("utf-8")


# ---------------------------------------------------------------- passwords
def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac(_HASH_ALGO, password.encode("utf-8"), salt, _PBKDF2_ITERATIONS)
    return "pbkdf2${}${}${}".format(
        _PBKDF2_ITERATIONS,
        base64.b64encode(salt).decode("ascii"),
        base64.b64encode(digest).decode("ascii"),
    )


def verify_password(password: str, stored: str) -> bool:
    try:
        _algo, iters, salt_b64, hash_b64 = stored.split("$")
        if _algo != "pbkdf2":
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(hash_b64)
        digest = hashlib.pbkdf2_hmac(_HASH_ALGO, password.encode("utf-8"), salt, int(iters))
        return hmac.compare_digest(digest, expected)
    except Exception:
        return False


# ------------------------------------------------------------------ tokens
def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(text: str) -> bytes:
    pad = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + pad)


def create_access_token(username: str, role: str) -> str:
    header = _b64url(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload = _b64url(json.dumps({
        "sub": username,
        "role": role,
        "exp": int(time.time()) + _MAX_TOKEN_AGE_SECONDS,
    }).encode())
    signature = _b64url(hmac.new(_secret_key(), f"{header}.{payload}".encode(), hashlib.sha256).digest())
    return f"{header}.{payload}.{signature}"


def decode_access_token(token: str) -> dict:
    """Return {'sub': username, 'role': role} or raise ValueError."""
    try:
        header, payload, signature = token.split(".")
        expected = _b64url(hmac.new(_secret_key(), f"{header}.{payload}".encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(expected, signature):
            raise ValueError("bad signature")
        data = json.loads(_b64url_decode(payload))
        if int(data.get("exp", 0)) < int(time.time()):
            raise ValueError("token expired")
        if data.get("role") not in ROLES:
            raise ValueError("unknown role")
        return {"sub": data["sub"], "role": data["role"]}
    except (ValueError, KeyError, TypeError):
        raise ValueError("invalid token")


# -------------------------------------------------------------- dependencies
def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> User:
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = decode_access_token(credentials.credentials)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == payload["sub"]).first()
    finally:
        db.close()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User no longer exists")
    return user


def require_roles(*roles: str):
    allowed = set(roles)

    def _dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permission")
        return user

    return _dependency


# -------------------------------------------------------------- default users
DEFAULT_USERS = (
    ("riskadmin", "admin", "Risk Admin"),
    ("riskanalyst", "analyst", "Risk Analyst"),
    ("riskviewer", "viewer", "Risk Viewer"),
)


def default_user_password(username: str) -> str:
    """Password is overridable via env (e.g. RISK_ADMIN_PASSWORD) and defaults
    to a documented demo password."""
    env_name = f"RISK_{username.upper().replace('ANALYST', 'ANALYST')}_PASSWORD"
    return os.getenv(env_name, f"RiskGuard@{username}")


def ensure_default_users() -> None:
    """Idempotent: seed viewer/analyst/admin accounts into whatever DB the app
    is pointed at (demo DB, tests' throwaway DB, or the container's)."""
    db = SessionLocal()
    try:
        for username, role, display in DEFAULT_USERS:
            existing = db.query(User).filter(User.username == username).first()
            if existing is None:
                db.add(User(
                    username=username,
                    role=role,
                    display_name=display,
                    password_hash=hash_password(default_user_password(username)),
                ))
        db.commit()
    finally:
        db.close()