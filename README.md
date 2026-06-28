# Market Signals API 📈

> Scored, explainable trade signals in one GET request.

```
GET /v1/signals?ticker=AAPL
Authorization: Bearer sk-mkt-xxxx

→ { "score": 92, "direction": "bull", "signals": [...] }
```

---

## What's included

```
market-signals-api/
├── app/
│   ├── main.py              # FastAPI app + CORS + error handling
│   ├── core/
│   │   ├── config.py        # Settings (reads from .env)
│   │   ├── database.py      # SQLAlchemy models (APIKey, SignalCache)
│   │   └── auth.py          # Key generation, hashing, rate limiting
│   ├── routers/
│   │   ├── signals.py       # GET /v1/signals, /batch, /leaderboard
│   │   ├── auth.py          # POST /v1/auth/register, /upgrade, /webhook
│   │   └── health.py        # GET /health
│   └── services/
│       └── scorer.py        # Technical analysis engine
├── landing/
│   └── index.html           # Marketing landing page
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── setup.py                 # First-run DB init + admin key generator
└── .env.example
```

---

## Quick start (local dev)

### 1. Clone and install

```bash
git clone https://github.com/you/market-signals-api
cd market-signals-api
pip install -r requirements.txt
```

### 2. Set up environment

```bash
cp .env.example .env
# Edit .env with your Polygon.io API key and a random SECRET_KEY
```

Get a free Polygon.io key at https://polygon.io (Starter = $29/mo for real-time)

### 3. Initialize the database

```bash
python setup.py
# → Creates tables + prints your admin API key
```

### 4. Start the server

```bash
uvicorn app.main:app --reload
```

Visit:
- API docs: http://localhost:8000/docs
- Landing page: open `landing/index.html` in your browser

---

## API endpoints

### `GET /v1/signals?ticker=AAPL`
Returns a scored signal for a single ticker.

**Headers:** `Authorization: Bearer sk-mkt-xxxx`

**Response:**
```json
{
  "ticker": "AAPL",
  "score": 92,
  "direction": "bull",
  "price": 213.45,
  "change_pct": 2.3,
  "rsi": 54.2,
  "relative_volume": 2.3,
  "signals": [
    { "type": "bull", "label": "Broke 200 EMA", "weight": 8 },
    { "type": "bull", "label": "Relative volume 2.3x", "weight": 10 },
    { "type": "bull", "label": "Institutional buying detected", "weight": 10 }
  ],
  "generated_at": "2026-06-28T14:32:00Z",
  "cached": false
}
```

### `GET /v1/signals/batch?tickers=AAPL,TSLA,NVDA`
Batch signals for up to 10 tickers. **Pro+ only.**

### `GET /v1/signals/leaderboard?direction=bull&limit=10`
Top-scored tickers in the cache from the last hour.

### `POST /v1/auth/register`
Register and receive a free API key.
```json
{ "email": "you@company.com" }
```

### `POST /v1/auth/upgrade`
Get a Stripe checkout URL to upgrade your plan.
```json
{ "plan": "pro" }
```

---

## Signals detected

| Signal | Type | Notes |
|--------|------|-------|
| Golden cross (50/200 EMA) | Bull | Strong trend signal |
| Above 200 EMA | Bull | Price in uptrend |
| Death cross | Bear | Trend reversal |
| RSI oversold (<30) | Bull | Bounce setup |
| RSI reset (30–50) | Bull | Momentum reload |
| RSI overbought (>70) | Bear | Exhaustion |
| Relative volume 2x+ | Bull | Unusual activity |
| Bull flag pattern | Bull | Continuation |
| Cup & handle | Bull | Breakout setup |
| Support bounce | Bull | Key level held |
| Institutional buying | Bull | Large volume days |
| Bearish RSI divergence | Bear | Hidden weakness |
| Strong momentum >3% | Bull | Price acceleration |

---

## Pricing tiers

| Plan | Price | Calls/day | Delay | Features |
|------|-------|-----------|-------|----------|
| Free | $0 | 10 | 15 min | 5 tickers |
| Starter | $15/mo | 500 | 5 min | 50 tickers |
| Pro | $49/mo | 5,000 | Real-time | Batch, webhooks |
| Growth | $99/mo | 25,000 | Real-time | Portfolio alerts |
| Enterprise | Custom | Unlimited | Real-time | White-label, SLA |

---

## Deploy to Railway (recommended)

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login and deploy
railway login
railway init
railway up

# Set environment variables in Railway dashboard
# POLYGON_API_KEY, SECRET_KEY, STRIPE_SECRET_KEY, etc.
```

Or deploy to Render, Fly.io, or any Docker host.

---

## Setting up Stripe

1. Create an account at https://stripe.com
2. Create 3 products (Starter $15, Pro $49, Growth $99) with monthly recurring prices
3. Copy the price IDs into your `.env`:
   ```
   STRIPE_PRICES__starter=price_xxxx
   STRIPE_PRICES__pro=price_xxxx
   STRIPE_PRICES__growth=price_xxxx
   ```
4. Set up a webhook endpoint in Stripe dashboard pointing to:
   `https://yourdomain.com/v1/auth/webhook/stripe`
   Events: `checkout.session.completed`, `customer.subscription.deleted`
5. Copy the webhook signing secret to `STRIPE_WEBHOOK_SECRET`

---

## Sell this API

**Best channels:**
- Post on IndieHackers, HackerNews, Reddit (r/algotrading, r/stocks)
- List on RapidAPI marketplace (huge developer audience)
- Reach out to Discord trading server owners directly
- Build a demo Discord bot to show the product in action

**Best early customers:**
- Discord trading bot developers ($49 Pro is an easy sell)
- Trading app developers who don't want to build TA themselves
- Finance YouTubers who want live signal overlays

---

## License

MIT — use, modify, sell. No attribution required.
