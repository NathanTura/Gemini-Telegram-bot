"""Quick test to list available Gemini models for the configured API key."""
import asyncio
from google import genai
from os import getenv
from dotenv import load_dotenv

load_dotenv()

async def main():
    client = genai.Client(api_key=getenv('GEMINI_API_KEY'))
    
    print(f"API Key starts with: {getenv('GEMINI_API_KEY')[:10]}...")
    print("\nAvailable models that support generateContent:")
    print("-" * 60)
    
    for model in client.models.list():
        name = model.name
        methods = model.supported_actions if hasattr(model, 'supported_actions') else []
        if 'generateContent' in str(model):
            print(f"  {name}")

if __name__ == "__main__":
    asyncio.run(main())
