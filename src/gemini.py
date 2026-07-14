from os import getenv

import PIL.Image
from google import genai
from google.genai import errors
from google.genai import types

from google.genai.chats import AsyncChat, GenerateContentConfigOrDict
from .config import Config
from .exceptions.gemini_exceptions import GeminiUserFacingError, get_gemini_user_message
from .plugin_manager import PluginManager

# Fallback model list — tries each in order if the previous is rate-limited or unavailable
FALLBACK_MODELS = [
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-1.5-flash-8b",
    "gemini-1.5-flash",
]


class Gemini:
    
    def __init__(self):
        self.__plugin_manager = PluginManager()

        preferred_model = getenv('GEMINI_MODEL_NAME', Config.DEFAULT_GEMINI_MODEL_NAME)

        # Build fallback list: preferred model first, then the rest (no duplicates)
        self.__fallback_models = [preferred_model] + [
            m for m in FALLBACK_MODELS if m != preferred_model
        ]

        self.__client = genai.Client(
            api_key=getenv('GEMINI_API_KEY')
        ).aio

        self.__generation_config: GenerateContentConfigOrDict = types.GenerateContentConfig(
            temperature=0.5,
            tools=self.__plugin_manager.get_tools(),
        )

    def get_chat(self, model_name: str, history: list) -> AsyncChat:
        return self.__client.chats.create(
            model=model_name,
            history=history,
            config=self.__generation_config,
        )

    async def send_message(self, prompt: str, history: list) -> str:
        """Send a message, automatically falling back to other models if rate-limited."""
        last_exc = None

        for model_name in self.__fallback_models:
            try:
                chat = self.get_chat(model_name=model_name, history=history)
                response = await chat.send_message(prompt)

                print(f"[Gemini] Used model: {model_name}")
                print("Function Request: " + response.__str__())

                candidates = response.candidates or []
                parts = candidates[0].content.parts if candidates else []
                function_call = parts[0].function_call if parts else None

                if not function_call:
                    return response.text

                function_response = await self.__plugin_manager.get_function_response(function_call, chat)

                if function_response is None or function_response.text is None:
                    return "I'm sorry, An error occurred. Please try again."

                print("Response: " + function_response.__str__())
                return function_response.text

            except errors.APIError as exc:
                # If rate-limited or server overloaded, try next model silently
                if exc.code in {429, 500, 503}:
                    print(f"[Gemini] Model {model_name} returned {exc.code}, trying next fallback...")
                    last_exc = exc
                    continue
                # For all other errors (bad key, bad model name, etc.) raise immediately
                raise GeminiUserFacingError(
                    get_gemini_user_message(exc.code),
                    code=exc.code,
                    status=exc.status,
                    provider_message=exc.message,
                ) from exc

        # All fallbacks exhausted
        raise GeminiUserFacingError(
            get_gemini_user_message(last_exc.code if last_exc else None),
            code=last_exc.code if last_exc else None,
            status=last_exc.status if last_exc else None,
            provider_message=last_exc.message if last_exc else None,
        ) from last_exc

    @staticmethod
    async def send_image(prompt: str, image: PIL.Image, chat: AsyncChat) -> str:
        try:
            response = await chat.send_message([prompt, image])
            print("Image response: " + response.text)
            return response.text
        except errors.APIError as exc:
            raise GeminiUserFacingError(
                get_gemini_user_message(exc.code),
                code=exc.code,
                status=exc.status,
                provider_message=exc.message,
            ) from exc

    async def close(self) -> None:
        """Close plugin-managed resources for this Gemini client instance."""
        await self.__plugin_manager.close()

    async def __aenter__(self) -> "Gemini":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()
