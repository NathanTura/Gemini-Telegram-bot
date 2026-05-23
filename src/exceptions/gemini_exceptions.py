"""User-facing Gemini API error messages."""

GEMINI_RATE_LIMIT_MESSAGE = (
    "Gemini is receiving too many requests right now. Please wait a minute and try again."
)
GEMINI_UNAVAILABLE_MESSAGE = (
    "Gemini is temporarily overloaded or unavailable. Please try again shortly."
)
GEMINI_TIMEOUT_MESSAGE = (
    "Gemini took too long to answer. Try a shorter message or try again shortly."
)
GEMINI_CONFIGURATION_MESSAGE = (
    "I cannot reach Gemini because the bot configuration or request is invalid. "
    "Please try again later."
)
GEMINI_UNEXPECTED_MESSAGE = "Gemini returned an unexpected error. Please try again later."


class GeminiUserFacingError(Exception):
    """Raised when a Gemini API error has a safe message for Telegram users."""

    def __init__(
        self,
        user_message: str,
        code: int | None = None,
        status: str | None = None,
        provider_message: str | None = None,
    ):
        self.user_message = user_message
        self.code = code
        self.status = status
        self.provider_message = provider_message
        super().__init__(user_message)


def get_gemini_user_message(code: int | None) -> str:
    if code == 429:
        return GEMINI_RATE_LIMIT_MESSAGE

    if code in {500, 503}:
        return GEMINI_UNAVAILABLE_MESSAGE

    if code == 504:
        return GEMINI_TIMEOUT_MESSAGE

    if code in {400, 403, 404}:
        return GEMINI_CONFIGURATION_MESSAGE

    return GEMINI_UNEXPECTED_MESSAGE
