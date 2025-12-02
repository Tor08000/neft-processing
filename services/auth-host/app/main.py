import os
import secrets
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr

# -------------------------------------------------
# Модели
# -------------------------------------------------

class HealthResponse(BaseModel):
    status: str
    service: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    email: EmailStr


# -------------------------------------------------
# Приложение
# -------------------------------------------------

app = FastAPI(title="NEFT Auth Host")

# CORS – чтобы админ-панель могла спокойно ходить в /auth/*
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # для локалки так норм
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -------------------------------------------------
# Healthcheck – как и был
# -------------------------------------------------

@app.get("/api/v1/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok", service="auth-host")


# -------------------------------------------------
# Логин админа
# POST /api/v1/auth/login
# -------------------------------------------------

@app.post("/api/v1/auth/login", response_model=LoginResponse)
async def login(payload: LoginRequest) -> LoginResponse:
    """
    Простейшая авторизация для админ-панели.
    Сверяем логин/пароль с переменными окружения
    и отдаём токен в формате, который ждёт фронт.
    """

    # Можно переопределить в docker-compose через ENV
    admin_email = os.getenv("ADMIN_EMAIL", "admin@example.com")
    admin_password = os.getenv("ADMIN_PASSWORD", "admin123")

    if payload.email != admin_email or payload.password != admin_password:
        # Фронт сейчас просто показывает текст ошибки, ему достаточно 401
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Простейший "токен" – рандомная строка.
    # Для реальной системы сюда потом подвесим нормальный JWT.
    token = secrets.token_urlsafe(32)

    expires_in = int(os.getenv("ACCESS_TOKEN_EXPIRES_IN", "3600"))

    return LoginResponse(
        access_token=token,
        email=payload.email,
        expires_in=expires_in,
    )
