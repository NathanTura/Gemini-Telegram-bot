from __future__ import annotations

import logging
from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession
from telegram import Message

from src.chat_service import ChatService
from src.enums import TelegramBotCommands
from src.exceptions.gemini_exceptions import GeminiUserFacingError
from src.gemini import Gemini
from src.services.telegram_service import TelegramService, get_model_for_chat

LOGGER = logging.getLogger(__name__)
PROCESSING_MESSAGE = "Processing your request..."
UNSUPPORTED_MESSAGE = "I can currently process text messages and photos."
FALLBACK_MESSAGE = (
    "Sorry, I am not able to generate content for you right now. Please try again later."
)


class BotService:
    def __init__(
        self,
        telegram_service: TelegramService,
        chat_service: ChatService,
        gemini_factory: Callable[[], Gemini],
    ) -> None:
        self._telegram_service = telegram_service
        self._chat_service = chat_service
        self._gemini_factory = gemini_factory

    async def handle_message(self, message: Message, db: AsyncSession) -> str:
        chat_id = message.chat_id

        if message.text == TelegramBotCommands.START:
            await self._telegram_service.send_start_message(chat_id=chat_id)
            return "OK"

        chat_session = await self._chat_service.get_or_create_session(db, chat_id)

        if message.text == TelegramBotCommands.NEW_CHAT:
            await self._chat_service.clear_chat_history(db, chat_session.id)
            await self._telegram_service.send_new_chat_message(chat_id=chat_id)
            return "OK"

        if message.text == TelegramBotCommands.MODEL:
            await self._telegram_service.send_model_picker(chat_id=chat_id)
            return "OK"

        processing_message: Message | None = None

        try:
            if not message.photo and not message.text:
                await self._telegram_service.send_message(
                    chat_id=chat_id, text=UNSUPPORTED_MESSAGE
                )
                return "OK"

            processing_message = await self._telegram_service.send_message(
                chat_id=chat_id,
                text=PROCESSING_MESSAGE,
            )

            async with self._gemini_factory() as gemini:
                # Use the user's manually chosen model as the preferred first option
                preferred_model = get_model_for_chat(chat_id, gemini._Gemini__fallback_models[0])

                if message.photo:
                    image = await self._telegram_service.get_image_from_message(message)
                    if image is None:
                        raise ValueError(
                            "Telegram photo message did not contain a downloadable image"
                        )

                    prompt = message.caption or "Describe this image in detail."
                    history = await self._chat_service.get_chat_history(db, chat_session.id)
                    response_text = await gemini.send_image(
                        prompt, image, gemini.get_chat(model_name=preferred_model, history=history)
                    )
                    user_text = prompt
                else:
                    history = await self._chat_service.get_chat_history(db, chat_session.id)
                    response_text = await gemini.send_message(
                        message.text, history=history, preferred_model=preferred_model
                    )
                    user_text = message.text

            await self._chat_service.add_message(
                db, chat_session.id, user_text, message.date, "user"
            )
            await self._chat_service.add_message(
                db, chat_session.id, response_text, message.date, "model"
            )
            await self._telegram_service.update_message(
                chat_id=chat_id,
                message_id=processing_message.message_id,
                text=response_text,
            )
        except GeminiUserFacingError as exc:
            LOGGER.warning(
                "Gemini API error while processing Telegram message for chat_id=%s "
                "code=%s status=%s provider_message=%s",
                chat_id,
                exc.code,
                exc.status,
                exc.provider_message,
                exc_info=True,
            )
            await self._send_error_message(chat_id, processing_message, exc.user_message)
        except Exception:
            LOGGER.exception("Failed to process Telegram message for chat_id=%s", chat_id)
            await self._send_fallback_message(chat_id, processing_message)

        return "OK"

    async def _send_fallback_message(
        self,
        chat_id: int,
        processing_message: Message | None,
    ) -> None:
        await self._send_error_message(chat_id, processing_message, FALLBACK_MESSAGE)

    async def _send_error_message(
        self,
        chat_id: int,
        processing_message: Message | None,
        text: str,
    ) -> None:
        try:
            if processing_message is not None:
                await self._telegram_service.update_message(
                    chat_id=chat_id,
                    message_id=processing_message.message_id,
                    text=text,
                )
                return

            await self._telegram_service.send_message(chat_id=chat_id, text=text)
        except Exception:
            LOGGER.exception("Failed to send error Telegram message for chat_id=%s", chat_id)
