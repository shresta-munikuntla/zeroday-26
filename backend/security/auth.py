"""JWT authentication and server-side role enforcement."""
import os
from datetime import datetime, timedelta, timezone
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash

JWT_SECRET = os.getenv("JWT_SECRET_KEY", "")
ALGORITHM = "HS256"
password_hash = PasswordHash.recommended()
bearer = HTTPBearer(auto_error=False)
USERS: dict[str, dict] = {}


def initialize_users() -> None:
    global USERS
    if len(JWT_SECRET) < 32 or "replace-with" in JWT_SECRET:
        raise RuntimeError("JWT_SECRET_KEY must be a non-placeholder value of at least 32 characters")
    values = [
        ("viewer", "viewer", "DEMO_VIEWER_PASSWORD"),
        ("reviewer", "reviewer", "DEMO_REVIEWER_PASSWORD"),
    ]
    for user_id, role, variable in values:
        password = os.getenv(variable)
        if not password:
            raise RuntimeError(f"{variable} must be set in the environment")
        USERS[user_id] = {"user_id": user_id, "username": user_id, "role": role,
                          "password_hash": password_hash.hash(password)}


def authenticate(username: str, password: str) -> dict | None:
    user = USERS.get(username)
    if not user or not password_hash.verify(password, user["password_hash"]):
        return None
    return {k: user[k] for k in ("user_id", "username", "role")}


def create_token(user: dict) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode({"sub": user["user_id"], "username": user["username"], "role": user["role"],
                       "iat": now, "exp": now + timedelta(minutes=30)}, JWT_SECRET, algorithm=ALGORITHM)


def current_user(credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]) -> dict:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Authentication required", headers={"WWW-Authenticate": "Bearer"})
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[ALGORITHM])
        user = USERS.get(payload.get("sub"))
        if not user or payload.get("role") != user["role"]:
            raise ValueError("unknown user")
        return {k: user[k] for k in ("user_id", "username", "role")}
    except (jwt.InvalidTokenError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid or expired token", headers={"WWW-Authenticate": "Bearer"})


def require_role(role: str):
    def check(user: Annotated[dict, Depends(current_user)]) -> dict:
        if user["role"] != role:
            raise HTTPException(status_code=403, detail="Reviewer role required")
        return user
    return check
