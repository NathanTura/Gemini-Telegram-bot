import pytest

from src.exceptions.gemini_exceptions import (
    GEMINI_CONFIGURATION_MESSAGE,
    GEMINI_RATE_LIMIT_MESSAGE,
    GEMINI_TIMEOUT_MESSAGE,
    GEMINI_UNAVAILABLE_MESSAGE,
    GEMINI_UNEXPECTED_MESSAGE,
    get_gemini_user_message,
)


@pytest.mark.parametrize(
    ("code", "expected_message"),
    [
        (429, GEMINI_RATE_LIMIT_MESSAGE),
        (500, GEMINI_UNAVAILABLE_MESSAGE),
        (503, GEMINI_UNAVAILABLE_MESSAGE),
        (504, GEMINI_TIMEOUT_MESSAGE),
        (400, GEMINI_CONFIGURATION_MESSAGE),
        (403, GEMINI_CONFIGURATION_MESSAGE),
        (404, GEMINI_CONFIGURATION_MESSAGE),
        (418, GEMINI_UNEXPECTED_MESSAGE),
        (None, GEMINI_UNEXPECTED_MESSAGE),
    ],
)
def test_get_gemini_user_message_maps_api_codes(code, expected_message):
    assert get_gemini_user_message(code) == expected_message
