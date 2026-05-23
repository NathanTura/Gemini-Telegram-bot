from __future__ import annotations

from collections.abc import Callable
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI

from src.bot_service import BotService
from src.chat_service import ChatService
from src.gemini import Gemini
from src.routes import router
from src.services.telegram_service import TelegramService

load_dotenv()


def create_app(
    telegram_service_factory: Callable[[], TelegramService] = TelegramService,
    chat_service_factory: Callable[[], ChatService] = ChatService,
    gemini_factory: Callable[[], Gemini] = Gemini,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        telegram_service = telegram_service_factory()
        app.state.telegram_service = telegram_service
        app.state.bot_service = BotService(
            telegram_service, chat_service_factory(), gemini_factory
        )

        try:
            yield
        finally:
            telegram_service = getattr(app.state, "telegram_service", None)
            if telegram_service is not None:
                await telegram_service.close()

    app = FastAPI(lifespan=lifespan)
    app.include_router(router)
    return app


app = create_app()
