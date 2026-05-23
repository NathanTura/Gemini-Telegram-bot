from os import getenv

import PIL.Image
from google import genai
from google.genai import errors
from google.genai import types

from google.genai.chats import AsyncChat, GenerateContentConfigOrDict
from .config import Config
from .exceptions.gemini_exceptions import GeminiUserFacingError, get_gemini_user_message
from .plugin_manager import PluginManager


class Gemini:
    
    def __init__(self):
        self.__plugin_manager = PluginManager()
        
        self.__model_name = getenv('GEMINI_MODEL_NAME', Config.DEFAULT_GEMINI_MODEL_NAME)
        self.__client = genai.Client(
            api_key=getenv('GEMINI_API_KEY')
        ).aio

        self.__generation_config: GenerateContentConfigOrDict = types.GenerateContentConfig(
            temperature=0.5,
            tools=self.__plugin_manager.get_tools(),
        )

    def get_chat(self, history: list) -> AsyncChat:
        return self.__client.chats.create(
            model=self.__model_name,
            history=history,
            config=self.__generation_config,
        )

    async def send_message(self, prompt: str, chat: AsyncChat) -> str:
        try:
            response = await chat.send_message(prompt)

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
            raise GeminiUserFacingError(
                get_gemini_user_message(exc.code),
                code=exc.code,
                status=exc.status,
                provider_message=exc.message,
            ) from exc


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
