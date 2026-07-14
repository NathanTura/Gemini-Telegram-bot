import asyncio
from telegram.ext import ApplicationBuilder
from os import getenv
from telegram import BotCommand


async def set_telegram_bot_commands():
    telegram_app = ApplicationBuilder().token(getenv('TELEGRAM_BOT_TOKEN')).build()
    commands = [
        BotCommand("new_chat", "Start a fresh conversation"),
        BotCommand("model", "Switch the AI model"),
    ]
    await telegram_app.bot.set_my_commands(commands=commands)

if __name__ == '__main__':
    asyncio.run(set_telegram_bot_commands())
    print('Commands set')
