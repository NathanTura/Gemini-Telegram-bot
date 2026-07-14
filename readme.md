# GemBot (@Theallknowerbot)

A powerful Telegram chatbot powered by Google's Gemini AI. Send it messages, images, or ask it anything — it's always online, always free.

## Features
- 🤖 Powered by Gemini 2.0 Flash
- ⚡ Smart Model Fallback — automatically switches to a less busy model if rate-limited
- 🎛️ Manual Model Switcher — type `/model` to pick your preferred AI model
- 🔄 Auto Mode — let the bot find the fastest available model automatically
- 🖼️ Image Understanding — send a photo and ask about it
- 💬 Persistent Chat History — the bot remembers your conversation (via Neon Postgres)
- 🌤️ Weather Plugin — ask about current weather (optional, requires OpenWeatherMap key)
- 🆓 100% Free Hosting via Vercel (serverless, never sleeps)

## Commands
| Command | Description |
|---|---|
| `/start` | Welcome message + command list |
| `/new_chat` | Wipe history and start a fresh conversation |
| `/model` | Open the model switcher menu |

## Acknowledgements
This bot is a customized fork based on the open-source work by [benincasantonio](https://github.com/benincasantonio/gemini-ai-telegram-bot). Big thanks to the original developer for the foundational architecture!

---

## Local Development (Testing on your PC)

1. Make sure your `.env` file exists in the root folder (see `.env.example` below).
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the bot:
   ```bash
   python run.py
   ```

### .env Variables
```env
GEMINI_API_KEY=your_gemini_api_key_from_aistudio.google.com
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_from_botfather
GEMINI_MODEL_NAME=gemini-2.0-flash
ENABLE_SECURE_WEBHOOK_TOKEN=False
SQLALCHEMY_DATABASE_URI=postgresql://user:password@host/dbname?sslmode=require
# Optional: OWM_API_KEY=your_openweathermap_api_key
```

---

## Permanent 24/7 Deployment (Vercel + Neon)

### 1. Database Setup
1. Go to [Neon.tech](https://neon.tech) and create a free account.
2. Create a new Postgres project.
3. Copy the **Connection String** (e.g. `postgresql://user:password@hostname/dbname?sslmode=require`).

### 2. Get a Gemini API Key
1. Go to 👉 [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)
2. Click **Create API key**.
3. Copy the key.

### 3. Vercel Setup

> ⚠️ **THE "PRODUCTION" CATCH** — Read this carefully!
>
> When you add Environment Variables in Vercel, they default to **Preview only**.
> Your live bot runs in **Production** mode, so you MUST check the **Production** checkbox for every variable, or the bot will crash with missing key errors.
> After adding/editing any variables, always go to **Deployments → Redeploy** to apply the changes.

1. Push this repo to your GitHub.
2. Create a new project on [Vercel](https://vercel.com) and import your repo.
3. Go to **Settings → Environment Variables** and add these:

| Variable | Value |
|---|---|
| `GEMINI_API_KEY` | Your key from AI Studio |
| `TELEGRAM_BOT_TOKEN` | Your bot token from BotFather |
| `SQLALCHEMY_DATABASE_URI` | Your Neon connection string |
| `GEMINI_MODEL_NAME` | `gemini-2.0-flash` |
| `ENABLE_SECURE_WEBHOOK_TOKEN` | `False` |

4. For **every variable**, click `...` → Edit → check ✅ **Production** → Save.
5. Click **Deploy**.

### 4. Connect Telegram Webhook
Once Vercel gives you a URL (e.g. `https://my-gembot.vercel.app`), tell Telegram to use it:

Open your browser and visit:
```
https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook?url=<YOUR_VERCEL_URL>/webhook
```
> Make sure `/webhook` is at the end!

If you see `"Webhook was set"` — your bot is live 🎉

---

## Model Switching

Type `/model` in Telegram to open the model picker:

```
🤖 Choose your AI model:

✅ 🔄 Auto (Smart Fallback)
⚡ Gemini 2.0 Flash (Default)
🪶 Gemini 2.0 Flash Lite (Faster)
🧠 Gemini 1.5 Flash (Stable)
🐣 Gemini 1.5 Flash 8B (Lightest)
```

- **Auto** (default) — the bot silently tries all models top-to-bottom and skips any that are busy. You never see a rate-limit error.
- **Pick a specific model** — that model is always tried first, with auto-fallback if it's unavailable.
