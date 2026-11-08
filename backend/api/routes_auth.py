from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException
from backend.security.auth import authenticate, create_token

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=200)


@router.post("/login")
def login(payload: LoginRequest):
    user = authenticate(payload.username, payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    return {"access_token": create_token(user), "token_type": "bearer", "user": user}
