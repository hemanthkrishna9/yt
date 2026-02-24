"""FastAPI dependency for JWT auth."""

import jwt
from fastapi import Depends, HTTPException, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from server.auth.security import decode_access_token

_bearer = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> dict:
    """Extracts and validates JWT from Authorization header."""
    try:
        payload = decode_access_token(credentials.credentials)
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")
    return {"user_id": int(payload["sub"]), "email": payload["email"]}


def get_user_from_query(token: str = Query(...)) -> dict:
    """Extracts JWT from ?token= query param (for SSE / download)."""
    try:
        payload = decode_access_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")
    return {"user_id": int(payload["sub"]), "email": payload["email"]}
