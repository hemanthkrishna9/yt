"""Register + Login endpoints."""

import sqlite3

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr, field_validator

from server.auth.db import create_user, get_user_by_email
from server.auth.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


class AuthRequest(BaseModel):
    email: EmailStr
    password: str

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.lower()

    @field_validator("password")
    @classmethod
    def min_length(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("Password must be at least 6 characters")
        return v


class AuthResponse(BaseModel):
    token: str
    email: str
    user_id: int


@router.post("/register", response_model=AuthResponse)
def register(req: AuthRequest):
    hashed = hash_password(req.password)
    try:
        user_id = create_user(req.email, hashed)
    except sqlite3.IntegrityError:
        raise HTTPException(409, "Email already registered")
    token = create_access_token(user_id, req.email)
    return AuthResponse(token=token, email=req.email, user_id=user_id)


@router.post("/login", response_model=AuthResponse)
def login(req: AuthRequest):
    user = get_user_by_email(req.email)
    if not user or not verify_password(req.password, user["password_hash"]):
        raise HTTPException(401, "Invalid email or password")
    token = create_access_token(user["id"], user["email"])
    return AuthResponse(token=token, email=user["email"], user_id=user["id"])
