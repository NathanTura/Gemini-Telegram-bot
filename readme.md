# GemBot (@Theallknowerbot)

A powerful Telegram chatbot that uses Google's Generative AI (Gemini) to chat, answer questions, and assist you.

This bot is configured to be **100% free forever** by utilizing Vercel's serverless functions and a free PostgreSQL database. It never sleeps, so it's always ready to answer your messages.

## Features
- Powered by Gemini 2.5 Flash
- 100% Free Hosting via Vercel (Scales to zero, never shuts down)
- Persistent Chat History (via Neon.tech/Supabase Postgres)
- Auto-Database Migration on Startup

## Acknowledgements
This bot is a customized fork based on the incredible open-source work by [benincasantonio](https://github.com/benincasantonio/gemini-ai-telegram-bot). Huge thanks to the original developer for creating the foundational architecture!

## Local Development (Testing on your PC)

If you want to run the bot on your computer before deploying:

1. Ensure your `.env` file is present in the root directory and contains your `TELEGRAM_BOT_TOKEN`, `GEMINI_API_KEY`, etc.
2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the bot:
   ```bash
   python run.py
   ```

## Permanent 24/7 Deployment (Vercel)

Follow these steps to deploy the bot so it stays online forever without needing your computer.

### 1. Database Setup
1. Go to [Neon.tech](https://neon.tech) and create a free account.
2. Create a new Postgres project.
3. Copy your **Connection String** (e.g., `postgresql://user:password@hostname/dbname?sslmode=require`).

### 2. Vercel Setup
1. Push this repository to your GitHub account if you haven't already.
2. Create a new project on [Vercel](https://vercel.com) and select your repository.
3. Add the following **Environment Variables** in Vercel before deploying:
   - `GEMINI_API_KEY`: Your Gemini API key
   - `TELEGRAM_BOT_TOKEN`: Your Telegram Bot token
   - `SQLALCHEMY_DATABASE_URI`: Your Neon.tech connection string
   - `ENABLE_SECURE_WEBHOOK_TOKEN`: `False`
4. Deploy the project!

### 3. Connect Telegram to Vercel (Webhook)
Once Vercel gives you a URL (e.g., `https://my-gembot.vercel.app`), tell Telegram to send messages there.

Open your browser and visit:
```text
https://api.telegram.org/bot<YOUR_TELEGRAM_BOT_TOKEN>/setWebhook?url=<YOUR_VERCEL_URL>/webhook
```
*Make sure to include `/webhook` at the end of your Vercel URL!*

If the browser returns `"Webhook was set"`, your bot is now online and running 24/7!
