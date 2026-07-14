from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession
from telegram import Update

from src.bot_service import BotService
from src.services.database_service import get_db
from src.services.telegram_service import TelegramService

LOGGER = logging.getLogger(__name__)

router = APIRouter()


def get_telegram_service(request: Request) -> TelegramService:
    return request.app.state.telegram_service


def get_bot_service(request: Request) -> BotService:
    return request.app.state.bot_service


def _validate_webhook_token(telegram_service: TelegramService, request: Request) -> None:
    if not telegram_service.is_secure_webhook_enabled():
        return

    secret_token = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    if telegram_service.is_secure_webhook_token_valid(secret_token):
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Invalid webhook token",
    )


async def _get_telegram_update(request: Request, telegram_service: TelegramService) -> Update:
    try:
        payload = await request.json()
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid webhook payload",
        ) from error

    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid webhook payload",
        )

    try:
        return telegram_service.build_update(payload)
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid webhook payload",
        ) from error


@router.get("/")
async def read_root() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/webhook", response_class=PlainTextResponse)
async def webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    telegram_service: TelegramService = Depends(get_telegram_service),
    bot_service: BotService = Depends(get_bot_service),
) -> str:
    _validate_webhook_token(telegram_service, request)
    telegram_update = await _get_telegram_update(request, telegram_service)

    # Handle inline keyboard button taps (model switcher)
    if telegram_update.callback_query is not None:
        callback = telegram_update.callback_query
        if callback.data and callback.data.startswith("model:"):
            await telegram_service.handle_model_callback(callback)
        return "OK"

    if telegram_update.edited_message is not None:
        return "OK"

    if telegram_update.message is None:
        return "OK"

    return await bot_service.handle_message(telegram_update.message, db)
