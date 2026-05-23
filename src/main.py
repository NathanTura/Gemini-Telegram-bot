from __future__ import annotations

import logging
from collections.abc import Callable
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession
from telegram import Message, Update

from src.chat_service import ChatService
from src.enums import TelegramBotCommands
from src.services.database_service import get_db
from src.services.telegram_service import TelegramService
from src.gemini import Gemini

load_dotenv()

LOGGER = logging.getLogger(__name__)
PROCESSING_MESSAGE = "Processing your request..."
UNSUPPORTED_MESSAGE = "I can currently process text messages and photos."
FALLBACK_MESSAGE = (
    "Sorry, I am not able to generate content for you right now. Please try again later."
)


def get_telegram_service(request: Request) -> TelegramService:
    return request.app.state.telegram_service


def get_chat_service(request: Request) -> ChatService:
    return request.app.state.chat_service


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


async def _send_fallback_message(
    telegram_service: TelegramService,
    chat_id: int,
    processing_message: Message | None,
) -> None:
    try:
        if processing_message is not None:
            await telegram_service.update_message(
                chat_id=chat_id,
                message_id=processing_message.message_id,
                text=FALLBACK_MESSAGE,
            )
            return

        await telegram_service.send_message(chat_id=chat_id, text=FALLBACK_MESSAGE)
    except Exception:
        LOGGER.exception("Failed to send fallback Telegram message for chat_id=%s", chat_id)


async def _handle_message(
    message: Message,
    db: AsyncSession,
    telegram_service: TelegramService,
    chat_service: ChatService,
    gemini_factory: Callable[[], Gemini],
) -> str:
    chat_id = message.chat_id

    if message.text == TelegramBotCommands.START:
        await telegram_service.send_start_message(chat_id=chat_id)
        return "OK"

    chat_session = await chat_service.get_or_create_session(db, chat_id)

    if message.text == TelegramBotCommands.NEW_CHAT:
        await chat_service.clear_chat_history(db, chat_session.id)
        await telegram_service.send_new_chat_message(chat_id=chat_id)
        return "OK"

    processing_message: Message | None = None

    try:
        if not message.photo and not message.text:
            await telegram_service.send_message(chat_id=chat_id, text=UNSUPPORTED_MESSAGE)
            return "OK"

        processing_message = await telegram_service.send_message(
            chat_id=chat_id,
            text=PROCESSING_MESSAGE,
        )

        async with gemini_factory() as gemini:
            if message.photo:
                image = await telegram_service.get_image_from_message(message)
                if image is None:
                    raise ValueError("Telegram photo message did not contain a downloadable image")

                prompt = message.caption or "Describe this image in detail."
                history = await chat_service.get_chat_history(db, chat_session.id)
                response_text = await gemini.send_image(prompt, image, gemini.get_chat(history=history))
                user_text = prompt
            else:
                history = await chat_service.get_chat_history(db, chat_session.id)
                response_text = await gemini.send_message(message.text, gemini.get_chat(history=history))
                user_text = message.text

        await chat_service.add_message(db, chat_session.id, user_text, message.date, "user")
        await chat_service.add_message(db, chat_session.id, response_text, message.date, "model")
        await telegram_service.update_message(
            chat_id=chat_id,
            message_id=processing_message.message_id,
            text=response_text,
        )
    except Exception:
        LOGGER.exception("Failed to process Telegram message for chat_id=%s", chat_id)
        await _send_fallback_message(telegram_service, chat_id, processing_message)

    return "OK"


def create_app(
    telegram_service_factory: Callable[[], TelegramService] = TelegramService,
    chat_service_factory: Callable[[], ChatService] = ChatService,
    gemini_factory: Callable[[], Gemini] = Gemini,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.telegram_service = telegram_service_factory()
        app.state.chat_service = chat_service_factory()
        app.state.gemini_factory = gemini_factory

        try:
            yield
        finally:
            telegram_service = getattr(app.state, "telegram_service", None)
            if telegram_service is not None:
                await telegram_service.close()

    app = FastAPI(lifespan=lifespan)

    @app.get("/")
    async def read_root() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/webhook", response_class=PlainTextResponse)
    async def webhook(
        request: Request,
        db: AsyncSession = Depends(get_db),
        telegram_service: TelegramService = Depends(get_telegram_service),
        chat_service: ChatService = Depends(get_chat_service),
    ) -> str:
        _validate_webhook_token(telegram_service, request)
        telegram_update = await _get_telegram_update(request, telegram_service)

        if telegram_update.edited_message is not None:
            return "OK"

        if telegram_update.message is None:
            return "OK"

        return await _handle_message(
            telegram_update.message,
            db,
            telegram_service,
            chat_service,
            request.app.state.gemini_factory,
        )

    return app


app = create_app()
