from io import BytesIO
from os import getenv
from telegram import Message, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder
from PIL import Image

# Available models for manual selection
AVAILABLE_MODELS = [
    ("⚡ Gemini 2.0 Flash Lite (Free)", "gemini-2.0-flash-lite"),
    ("🧠 Gemini 1.5 Flash (Free)", "gemini-1.5-flash"),
    ("🐣 Gemini 1.5 Flash 8B (Free, Lightest)", "gemini-1.5-flash-8b"),
    ("🚀 Gemini 2.0 Flash (May need billing)", "gemini-2.0-flash"),
]

AUTO_MODEL = "auto"  # Sentinel value meaning "use smart fallback"

# In-memory store: {chat_id: model_name or AUTO_MODEL}
_user_model_preferences: dict[int, str] = {}


def get_model_for_chat(chat_id: int, default: str) -> str | None:
    """Get the manually selected model for a chat.
    Returns None if the user is on Auto mode (smart fallback)."""
    pref = _user_model_preferences.get(chat_id, AUTO_MODEL)
    if pref == AUTO_MODEL:
        return None  # None = let Gemini class handle fallback automatically
    return pref


def set_model_for_chat(chat_id: int, model_name: str) -> None:
    """Save the user's manually selected model (or AUTO_MODEL for auto)."""
    _user_model_preferences[chat_id] = model_name


class TelegramService:
    def __init__(self):
        self._telegram_bot = ApplicationBuilder().token(getenv("TELEGRAM_BOT_TOKEN")).build().bot

    @property
    def bot(self):
        return self._telegram_bot

    def build_update(self, payload: dict) -> Update:
        return Update.de_json(payload, self.bot)

    def is_secure_webhook_enabled(self) -> bool:
        """Check if secure webhook is enabled."""
        return getenv("ENABLE_SECURE_WEBHOOK_TOKEN", "True").lower() == "true"
    
    def get_secure_webhook_token(self) -> str:
        """Get the secure webhook token from environment variable."""
        return getenv("TELEGRAM_WEBHOOK_SECRET")
    
    def is_secure_webhook_token_valid(self, headers_token: str) -> bool:
        """Validate the secure webhook token from headers."""
        secret_token = self.get_secure_webhook_token()
        return bool(secret_token) and headers_token == secret_token
    
    async def send_start_message(self, chat_id: int):
        """Send the start message to the user."""
        await self.send_message(
            chat_id=chat_id,
            text=(
                "👋 Welcome to GemBot!\n\n"
                "Send me a message or image to get started.\n\n"
                "Commands:\n"
                "• /new_chat — Start a fresh conversation\n"
                "• /model — Switch the AI model"
            )
        )

    async def send_unauthorized_message(self, chat_id: int):
        """Send an unauthorized access message to the user."""
        await self.send_message(chat_id=chat_id, text="You are not authorized to access this service.")

    async def send_new_chat_message(self, chat_id: int):
        """Send a new chat started message to the user."""
        await self.send_message(chat_id=chat_id, text="✅ New chat started. How can I assist you?")

    async def send_model_picker(self, chat_id: int):
        """Send a model picker with inline keyboard buttons."""
        current = _user_model_preferences.get(chat_id, AUTO_MODEL)
        keyboard = []

        # Auto option at the top
        auto_label = "✅ 🔄 Auto (Smart Fallback)" if current == AUTO_MODEL else "🔄 Auto (Smart Fallback)"
        keyboard.append([InlineKeyboardButton(auto_label, callback_data="model:auto")])

        for label, model_id in AVAILABLE_MODELS:
            display = f"✅ {label}" if model_id == current else label
            keyboard.append([InlineKeyboardButton(display, callback_data=f"model:{model_id}")])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await self.bot.send_message(
            chat_id=chat_id,
            text="🤖 *Choose your AI model:*\n\n🔄 *Auto* — tries each model in order, skips any that are busy.\nOr pick a specific model to always use that one first.",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

    async def handle_model_callback(self, callback_query) -> None:
        """Handle the inline keyboard callback when user picks a model."""
        model_name = callback_query.data.replace("model:", "")
        chat_id = callback_query.message.chat_id

        set_model_for_chat(chat_id, model_name)

        if model_name == AUTO_MODEL:
            status_text = "✅ Switched to *Auto* mode!\n\nThe bot will automatically try the fastest available model and skip any that are busy."
        else:
            label = next((lbl for lbl, mid in AVAILABLE_MODELS if mid == model_name), model_name)
            status_text = f"✅ Switched to *{label}*!\n\nThe bot will still auto-fallback to other models if this one is busy."

        # Rebuild keyboard with updated checkmarks
        current = model_name
        keyboard = []
        auto_label = "✅ 🔄 Auto (Smart Fallback)" if current == AUTO_MODEL else "🔄 Auto (Smart Fallback)"
        keyboard.append([InlineKeyboardButton(auto_label, callback_data="model:auto")])
        for lbl, mid in AVAILABLE_MODELS:
            display = f"✅ {lbl}" if mid == current else lbl
            keyboard.append([InlineKeyboardButton(display, callback_data=f"model:{mid}")])

        await callback_query.edit_message_text(
            text=status_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        await callback_query.answer()

    async def send_message(self, chat_id: int, text: str) -> Message:
        """Send a message to the user."""
        return await self.bot.send_message(chat_id=chat_id, text=text)
    
    async def update_message(self, chat_id: int, message_id: int, text: str) -> Message:
        """Update a message for the user."""
        return await self.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text)
    
    async def get_image_from_message(self, message: Message) -> Image.Image | None:
        """Retrieve the image file bytes from a Telegram message."""
        if message.photo:
            file_id = message.photo[-1].file_id
            file = await self.bot.get_file(file_id)
            bytes_array = await file.download_as_bytearray()
            bytesIO = BytesIO(bytes_array)
            image = Image.open(bytesIO)
            return image
        return None

    async def close(self) -> None:
        """Close the underlying Telegram bot client if supported."""
        shutdown = getattr(self.bot, "shutdown", None)
        if shutdown is not None:
            await shutdown()
