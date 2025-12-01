from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import PlainTextResponse

from neft_shared.logging_setup import get_logger
from app.db import get_conn
from app.models import User
from app.schemas import LoginRequest, RegisterRequest, TokenResponse, UserResponse
from app.security import create_access_token, get_current_user, hash_password, verify_password
from app.services.keys import get_public_key_pem

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
logger = get_logger(__name__)

ADMIN_DEFAULT_EMAIL = os.getenv("ADMIN_DEFAULT_EMAIL", "admin@example.com")
ADMIN_DEFAULT_PASSWORD = os.getenv("ADMIN_DEFAULT_PASSWORD", "admin")


@router.get("/public-key", response_class=PlainTextResponse)
async def get_public_key():
    """
    Return RSA public key (PEM) for verifying JWT (RS256).
    """

    public_pem = get_public_key_pem()
    return public_pem


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest) -> UserResponse:
    async with get_conn() as (conn, cur):
        await cur.execute("SELECT id FROM users WHERE email=%s", (payload.email,))
        if await cur.fetchone():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="user_exists")

        pwd_hash = hash_password(payload.password)
        await cur.execute(
            """
            INSERT INTO users (email, full_name, password_hash)
            VALUES (%s, %s, %s)
            RETURNING id, email, full_name, is_active, created_at, password_hash
            """,
            (payload.email, payload.full_name, pwd_hash),
        )
        row = await cur.fetchone()
        await conn.commit()

    user = User.from_row(row)
    logger.info("User registered", extra={"email": user.email})
    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        created_at=user.created_at,
    )


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest) -> TokenResponse:
    if payload.email == ADMIN_DEFAULT_EMAIL and payload.password == ADMIN_DEFAULT_PASSWORD:
        token = create_access_token(payload.email, ["ADMIN"])
        logger.info("Admin login (static credentials)", extra={"email": payload.email})
        return TokenResponse(access_token=token)

    async with get_conn() as (_, cur):
        await cur.execute(
            "SELECT id, email, full_name, password_hash, is_active, created_at FROM users WHERE email=%s",
            (payload.email,),
        )
        row = await cur.fetchone()

    if not row:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    user = User.from_row(row)
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_inactive")

    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    roles = ["ADMIN"] if user.email.lower().startswith("admin") else ["USER"]
    token = create_access_token(str(user.id), roles)
    logger.info("User logged in", extra={"email": user.email})
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        is_active=current_user.is_active,
        created_at=current_user.created_at,
    )
