from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.fuel import FleetTelegramBinding, FleetTelegramChatType
from app.services import fleet_service
from app.services.notifications.telegram_sender import TelegramSendError, send_message
from neft_shared.settings import get_settings

router = APIRouter(prefix="/api/internal/telegram", tags=["internal-telegram"])


def _verify_secret(request: Request) -> None:
    settings = get_settings()
    if not settings.TELEGRAM_WEBHOOK_SECRET:
        return
    header = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    if header != settings.TELEGRAM_WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="invalid_secret")


def _parse_command(text: str | None) -> tuple[str | None, str | None]:
    if not text:
        return None, None
    parts = text.strip().split()
    if not parts:
        return None, None
    command = parts[0].lower()
    token = parts[1] if len(parts) > 1 else None
    return command, token


def _chat_type(value: str | None) -> FleetTelegramChatType:
    if value in {"private", "group", "supergroup", "channel"}:
        return FleetTelegramChatType(value)
    return FleetTelegramChatType.PRIVATE


def _send_reply(chat_id: int, text: str) -> None:
    try:
        send_message(chat_id, text)
    except TelegramSendError:
        return


@router.post("/webhook")
async def telegram_webhook(request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    _verify_secret(request)
    payload = await request.json()
    message = payload.get("message") or payload.get("edited_message") or {}
    chat = message.get("chat") or {}
    text = message.get("text")
    chat_id = chat.get("id")
    if not chat_id:
        return {"ok": True}

    command, token = _parse_command(text)
    if command in {"/start", "/bind"} and token:
        try:
            binding = fleet_service.bind_telegram_chat(
                db,
                token_value=token,
                chat_id=int(chat_id),
                chat_title=chat.get("title") or chat.get("username"),
                chat_type=_chat_type(chat.get("type")),
            )
            db.commit()
        except HTTPException as exc:
            if exc.status_code == 410:
                db.commit()
                _send_reply(chat_id, "Token expired. Please generate a new link in the portal.")
                return {"ok": True}
            if exc.status_code == 409:
                _send_reply(chat_id, "Token already used. Generate a new link in the portal.")
                return {"ok": True}
            _send_reply(chat_id, "Token invalid. Please generate a new link in the portal.")
            return {"ok": True}
        scope_label = "Client" if binding.scope_type.value == "client" else "Group"
        _send_reply(chat_id, f"Bound to {scope_label}. Notifications are enabled.")
        return {"ok": True}

    if command == "/unbind":
        try:
            fleet_service.unbind_telegram_chat(db, chat_id=int(chat_id))
            db.commit()
            _send_reply(chat_id, "Telegram notifications disabled.")
        except HTTPException:
            _send_reply(chat_id, "No active binding found.")
        return {"ok": True}

    if command == "/status":
        binding = db.query(FleetTelegramBinding).filter(FleetTelegramBinding.chat_id == chat_id).one_or_none()
        if not binding:
            _send_reply(chat_id, "No bindings found. Use /start <token> to connect.")
            return {"ok": True}
        scope_label = "Client" if binding.scope_type.value == "client" else "Group"
        status = binding.status.value
        _send_reply(chat_id, f"Status: {status}. Scope: {scope_label}.")
        return {"ok": True}

    _send_reply(chat_id, "Commands: /start <token>, /bind <token>, /status, /unbind")
    return {"ok": True}
