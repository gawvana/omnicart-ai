# OmniCart AI — Smart Grocery Shopping & Local Market Analytics

An ultra-modern Telegram Mini App (TMA) + Telegram Bot powered by FastAPI, React 18, Tailwind CSS, Framer Motion, and B.AI for intelligent grocery shopping lists, natural language purchase parsing, predictive replenishment, and local market price analytics.

Designed for seamless deployment on **Vercel** serverless infrastructure.

---

## Architecture Overview

```
                          ┌──────────────────────────┐
                          │   Telegram User Client   │
                          └─────────────┬────────────┘
                                        │
                    ┌───────────────────┴───────────────────┐
                    │                                       │
                    ▼                                       ▼
        ┌───────────────────────┐               ┌───────────────────────┐
        │   Telegram WebApp     │               │   Telegram Bot        │
        │   (React 18 + Vite)   │               │   (Webhook updates)   │
        └───────────┬───────────┘               └───────────┬───────────┘
                    │                                       │
                    │   HTTPS /api/v1/*                     │   POST /api/webhook
                    └───────────────────┬───────────────────┘
                                        │
                                        ▼
                        ┌───────────────────────────────┐
                        │       Vercel Serverless       │
                        │       (FastAPI + Python)      │
                        └───────┬───────────────┬───────┘
                                │               │
                ┌───────────────┘               └───────────────┐
                ▼                                               ▼
    ┌───────────────────────┐                       ┌───────────────────────┐
    │     PostgreSQL        │                       │       Redis           │
    │   (Neon / Supabase)   │                       │      (Upstash)        │
    └───────────────────────┘                       └───────────────────────┘
```

- **Frontend**: Vite + React 18 + TypeScript + Tailwind CSS + Framer Motion. Built to `frontend/dist` and served statically via Vercel Edge Network.
- **Backend API**: FastAPI running as Python serverless functions (`api/index.py`).
- **Telegram Bot**: Webhook mode via `api/webhook.py`, dispatched via `aiogram 3.x`.
- **Scheduled Jobs**: Vercel Cron calling `api/cron.py` twice daily to compute predictive replenishment intervals and aggregate local market price indices.
- **Storage**:
  - PostgreSQL (e.g. Neon Serverless Postgres with PgBouncer connection pooling).
  - Redis (e.g. Upstash Serverless Redis for sliding-window rate limiting).

---

## Deploying to Vercel

### 1. Prerequisites
- A [Vercel](https://vercel.com) account.
- A Telegram Bot token from [@BotFather](https://t.me/BotFather).
- A free serverless PostgreSQL database from [Neon](https://neon.tech) or [Supabase](https://supabase.com).
- A free serverless Redis database from [Upstash](https://upstash.com).
- A B.AI API key.

### 2. Push to GitHub
Push this repository to your GitHub account.

### 3. Import Project in Vercel
1. Go to your [Vercel Dashboard](https://vercel.com/dashboard) and click **Add New... > Project**.
2. Select your repository.
3. Vercel will automatically detect the `vercel.json` configuration:
   - **Framework Preset**: Vite
   - **Build Command**: `cd frontend && npm install && npm run build`
   - **Output Directory**: `frontend/dist`
   - **Install Command**: `cd frontend && npm install`

### 4. Configure Environment Variables
In the Vercel Project Import screen (or **Settings > Environment Variables**), add the following:

| Variable | Description | Example |
| :--- | :--- | :--- |
| `TELEGRAM_BOT_TOKEN` | Token from @BotFather | `1234567890:ABCdefGHIjkl...` |
| `TELEGRAM_WEBAPP_URL` | Your Vercel deployment URL | `https://your-app.vercel.app` |
| `TELEGRAM_WEBHOOK_SECRET` | 32-char random string for webhook security | `a1b2c3d4e5f6...` |
| `DATABASE_URL` | Neon/Supabase async connection string | `postgresql+asyncpg://user:pass@ep-pooler.neon.tech/neondb?ssl=require` |
| `REDIS_URL` | Upstash Redis connection string | `rediss://default:token@instance.upstash.io:6379` |
| `BAI_API_KEY` | B.AI API key for LLM parsing & analytics | `sk-...` |
| `SECRET_KEY` | 64-char hex secret for cryptographic operations | `d4f6a...` |
| `CRON_SECRET` | Secret token for Vercel Cron requests | `cron_secret_123` |
| `ALLOWED_ORIGINS` | Permitted CORS origins | `*` |

> **Note on Neon Database URLs**:
> If your Neon connection string starts with `postgresql://`, OmniCart AI automatically converts it to `postgresql+asyncpg://` at runtime. Ensure you use the **Pooled connection string** (`-pooler`) provided by Neon for serverless efficiency!

### 5. Click Deploy
Vercel will build the frontend assets, bundle the Python serverless functions, and deploy your application.

---

## Post-Deployment Setup

### Set Telegram Bot Webhook
Once deployed, activate your Telegram bot webhook so it receives messages:

#### Option A: Via Browser / cURL
Send a POST request to your deployed API:
```bash
curl -X POST "https://your-app.vercel.app/api/v1/bot/setup-webhook"
```
Or with custom webhook URL:
```bash
curl -X POST "https://your-app.vercel.app/api/v1/bot/setup-webhook?webhook_url=https://your-app.vercel.app/api/webhook"
```

#### Option B: Via Python CLI
```bash
python -m bot.set_webhook set https://your-app.vercel.app
```

### Configure Telegram Bot Menu Button
In [@BotFather](https://t.me/BotFather):
1. Send `/setmenubutton`.
2. Choose your bot.
3. Enter your Vercel URL: `https://your-app.vercel.app`.
4. Enter button text: `🛒 Open OmniCart`.

---

## API Endpoints

- `GET /api/health` — Health check status and service connectivity.
- `POST /api/webhook` — Telegram Bot update receiver.
- `POST /api/v1/bot/setup-webhook` — Helper to register Telegram webhook.
- `GET /api/cron` — Scheduled replenishment & price index runner.
- `POST /api/v1/ai/parse-purchase` — Extract items, quantities, and prices from natural language.
- `GET /api/v1/checklist` — Fetch shopping checklist items.
- `POST /api/v1/checklist` — Add or modify checklist items.
- `DELETE /api/v1/checklist/{id}` — Remove item.
- `POST /api/v1/cart/optimize` — Smart cart optimization with market prices.
- `GET /api/v1/analytics` — Purchase analytics and spending trends.
