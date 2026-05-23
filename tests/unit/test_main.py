from datetime import datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient

from src.bot_service import FALLBACK_MESSAGE, PROCESSING_MESSAGE, UNSUPPORTED_MESSAGE
from src.main import create_app
from src.services.database_service import get_db


class FakeTelegramService:
    def __init__(self, secure_enabled: bool = False, valid_token: str = "secret"):
        self.secure_enabled = secure_enabled
        self.valid_token = valid_token
        self.sent_messages: list[tuple[int, str]] = []
        self.updated_messages: list[tuple[int, int, str]] = []
        self.closed = False

    def build_update(self, payload: dict):
        if payload.get("kind") == "invalid":
            raise ValueError("bad payload")

        if payload.get("edited_message"):
            return SimpleNamespace(edited_message=object(), message=None)

        message_payload = payload.get("message")
        if message_payload is None:
            return SimpleNamespace(edited_message=None, message=None)

        message = SimpleNamespace(
            chat_id=message_payload["chat_id"],
            text=message_payload.get("text"),
            photo=message_payload.get("photo"),
            caption=message_payload.get("caption"),
            date=datetime.fromisoformat(message_payload.get("date", "2026-01-01T12:00:00")),
        )
        return SimpleNamespace(edited_message=None, message=message)

    def is_secure_webhook_enabled(self) -> bool:
        return self.secure_enabled

    def is_secure_webhook_token_valid(self, headers_token: str | None) -> bool:
        return headers_token == self.valid_token

    async def send_start_message(self, chat_id: int):
        self.sent_messages.append((chat_id, "start"))

    async def send_new_chat_message(self, chat_id: int):
        self.sent_messages.append((chat_id, "new_chat"))

    async def send_message(self, chat_id: int, text: str):
        self.sent_messages.append((chat_id, text))
        return SimpleNamespace(message_id=len(self.sent_messages))

    async def update_message(self, chat_id: int, message_id: int, text: str):
        self.updated_messages.append((chat_id, message_id, text))
        return SimpleNamespace(message_id=message_id)

    async def get_image_from_message(self, message):
        return object()

    async def close(self) -> None:
        self.closed = True


class FakeChatService:
    def __init__(self):
        self.session_requests: list[int] = []
        self.clear_requests: list[int] = []
        self.history_requests: list[int] = []
        self.add_calls: list[tuple[int, str, str, datetime]] = []

    async def get_or_create_session(self, db, chat_id: int):
        self.session_requests.append(chat_id)
        return SimpleNamespace(id=chat_id + 1000, chat_id=chat_id)

    async def clear_chat_history(self, db, session_id: int):
        self.clear_requests.append(session_id)
        return 0

    async def get_chat_history(self, db, session_id: int):
        self.history_requests.append(session_id)
        return [{"role": "user", "parts": [{"text": "previous"}]}]

    async def add_message(self, db, session_id: int, text: str, date: datetime, role: str):
        self.add_calls.append((session_id, text, role, date))
        return SimpleNamespace(chat_id=session_id, text=text, role=role, date=date)


class FakeGemini:
    def __init__(self, *, fail: bool = False):
        self.fail = fail
        self.closed = False
        self.chat_histories: list[list[dict]] = []
        self.prompts: list[str] = []
        self.images: list[object] = []

    def get_chat(self, history: list[dict]):
        self.chat_histories.append(history)
        return {"history": history}

    async def send_message(self, prompt: str, chat) -> str:
        self.prompts.append(prompt)
        if self.fail:
            raise RuntimeError("boom")
        return f"reply:{prompt}"

    async def send_image(self, prompt: str, image, chat) -> str:
        self.prompts.append(prompt)
        self.images.append(image)
        return f"image:{prompt}"

    async def close(self) -> None:
        self.closed = True

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()


def build_test_client(*, secure_enabled: bool = False, gemini_fail: bool = False):
    telegram_service = FakeTelegramService(secure_enabled=secure_enabled)
    chat_service = FakeChatService()
    gemini_instances: list[FakeGemini] = []

    def gemini_factory() -> FakeGemini:
        gemini = FakeGemini(fail=gemini_fail)
        gemini_instances.append(gemini)
        return gemini

    app = create_app(
        telegram_service_factory=lambda: telegram_service,
        chat_service_factory=lambda: chat_service,
        gemini_factory=gemini_factory,
    )

    async def override_get_db():
        yield object()

    app.dependency_overrides[get_db] = override_get_db

    client = TestClient(app)
    return client, telegram_service, chat_service, gemini_instances


def test_webhook_rejects_invalid_secure_token():
    client, telegram_service, _, gemini_instances = build_test_client(secure_enabled=True)

    with client:
        response = client.post("/webhook", json={"message": {"chat_id": 1, "text": "hello"}})

    assert response.status_code == 403
    assert response.json()["detail"] == "Invalid webhook token"
    assert telegram_service.sent_messages == []
    assert gemini_instances == []


def test_webhook_returns_bad_request_for_invalid_payload():
    client, _, _, gemini_instances = build_test_client()

    with client:
        response = client.post("/webhook", json=["invalid"])

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid webhook payload"
    assert gemini_instances == []


def test_start_command_skips_gemini_and_sends_start_message():
    client, telegram_service, chat_service, gemini_instances = build_test_client()

    with client:
        response = client.post(
            "/webhook",
            json={"message": {"chat_id": 1, "text": "/start", "date": "2026-01-01T12:00:00"}},
        )

    assert response.status_code == 200
    assert response.text == "OK"
    assert telegram_service.sent_messages == [(1, "start")]
    assert chat_service.session_requests == []
    assert gemini_instances == []
    assert telegram_service.closed is True


def test_text_message_flow_updates_processing_message_and_persists_history():
    client, telegram_service, chat_service, gemini_instances = build_test_client()

    with client:
        response = client.post(
            "/webhook",
            json={"message": {"chat_id": 10, "text": "hello", "date": "2026-01-15T10:30:00"}},
        )

    assert response.status_code == 200
    assert response.text == "OK"
    assert telegram_service.sent_messages == [(10, PROCESSING_MESSAGE)]
    assert telegram_service.updated_messages == [(10, 1, "reply:hello")]
    assert chat_service.session_requests == [10]
    assert chat_service.history_requests == [1010]
    assert [call[1:3] for call in chat_service.add_calls] == [
        ("hello", "user"),
        ("reply:hello", "model"),
    ]
    assert len(gemini_instances) == 1
    assert gemini_instances[0].prompts == ["hello"]
    assert gemini_instances[0].closed is True


def test_photo_message_uses_caption_as_prompt():
    client, telegram_service, chat_service, gemini_instances = build_test_client()

    with client:
        response = client.post(
            "/webhook",
            json={
                "message": {
                    "chat_id": 7,
                    "photo": [{"file_id": "123"}],
                    "caption": "describe it",
                    "date": "2026-01-15T10:30:00",
                }
            },
        )

    assert response.status_code == 200
    assert response.text == "OK"
    assert telegram_service.sent_messages == [(7, PROCESSING_MESSAGE)]
    assert telegram_service.updated_messages == [(7, 1, "image:describe it")]
    assert [call[1:3] for call in chat_service.add_calls] == [
        ("describe it", "user"),
        ("image:describe it", "model"),
    ]
    assert gemini_instances[0].prompts == ["describe it"]


def test_unsupported_message_returns_helpful_response_without_gemini():
    client, telegram_service, chat_service, gemini_instances = build_test_client()

    with client:
        response = client.post(
            "/webhook",
            json={"message": {"chat_id": 4, "date": "2026-01-15T10:30:00"}},
        )

    assert response.status_code == 200
    assert response.text == "OK"
    assert telegram_service.sent_messages == [(4, UNSUPPORTED_MESSAGE)]
    assert chat_service.session_requests == [4]
    assert chat_service.add_calls == []
    assert gemini_instances == []


def test_processing_failure_updates_message_with_fallback():
    client, telegram_service, chat_service, gemini_instances = build_test_client(gemini_fail=True)

    with client:
        response = client.post(
            "/webhook",
            json={"message": {"chat_id": 12, "text": "hello", "date": "2026-01-15T10:30:00"}},
        )

    assert response.status_code == 200
    assert response.text == "OK"
    assert telegram_service.sent_messages == [(12, PROCESSING_MESSAGE)]
    assert telegram_service.updated_messages == [(12, 1, FALLBACK_MESSAGE)]
    assert chat_service.add_calls == []
    assert len(gemini_instances) == 1
