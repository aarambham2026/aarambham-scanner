import os
import secrets
import hmac
from typing import Optional, Dict
from fastapi import Request, HTTPException, status, Depends
from dotenv import load_dotenv

load_dotenv()

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "aarambham2026")

GUEST_USERNAME = os.getenv("GUEST_USERNAME", "guest")
GUEST_PASSWORD = os.getenv("GUEST_PASSWORD", "aarambham_guest_2026")

SECRET_KEY = os.getenv("SECRET_KEY", "aarambham_secret_key_2026_super_secure")

# Active sessions store: token -> {"username": username, "role": role}
ACTIVE_SESSIONS: Dict[str, dict] = {}


def generate_session_token(username: str, role: str) -> str:
    token = secrets.token_urlsafe(32)
    ACTIVE_SESSIONS[token] = {
        "username": username,
        "role": role
    }
    return token


def verify_credentials(username: str, password: str) -> Optional[dict]:
    clean_user = username.strip()
    clean_pass = password.strip()

    if clean_user.lower() == ADMIN_USERNAME.lower():
        if hmac.compare_digest(clean_pass, ADMIN_PASSWORD):
            return {"username": ADMIN_USERNAME, "role": "admin"}
        return None

    if hmac.compare_digest(clean_pass, GUEST_PASSWORD) or clean_user.lower() == GUEST_USERNAME.lower():
        return {"username": clean_user or GUEST_USERNAME, "role": "guest"}

    return None


def get_current_user_from_request(request: Request) -> Optional[dict]:
    token = request.cookies.get("session_token")
    if not token or token not in ACTIVE_SESSIONS:
        return None
    return ACTIVE_SESSIONS[token]


def get_current_user(request: Request) -> dict:
    user = get_current_user_from_request(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please log in."
        )
    return user


def get_current_admin(request: Request) -> dict:
    user = get_current_user(request)
    if user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required for this action."
        )
    return user
