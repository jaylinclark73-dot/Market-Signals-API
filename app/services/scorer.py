"""
Signal Scoring Engine
---------------------
Fetches OHLCV data from Polygon.io, runs technical analysis,
and returns a 0-100 score with explainable signal reasons.
"""

import httpx
import json
from datetime import datetime, timedelta
from typing import Optional
import statistics
from app.core.config import settings


POLYGON_BASE = "https://api.polygon.io"


# ── Data fetching ────────────────────────────────────────────────────────────

async def fetch_ohlcv(ticker: str, days: int = 60) -> list[dict]:
    """Fetch daily OHLCV bars from Polygon.io"""
    end = datetime.utcnow().strftime("%Y-%m-%d")
    start = (datetime.utcnow() - timedelta(days=days + 10)).strftime("%Y-%m-%d")

    url = (
        f"{POLYGON_BASE}/v2/aggs/ticker/{ticker}/range/1/day/{start}/{end}"
        f"?adjusted=true&sort=asc&limit=120&apiKey={settings.POLYGON_API_KEY}"
    )

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        data = resp.json()

    if data.get("resultsCount", 0) == 0:
        raise ValueError(f"No data found for ticker: {ticker}")

    return data["results"]  # [{o, h, l, c, v, t}, ...]


async def fetch_quote(ticker: str) -> dict:
    """Fetch latest quote (price + change)"""
    url = f"{POLYGON_BASE}/v2/last/trade/{ticker}?apiKey={settings.POLYGON_API_KEY}"
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.json().get("results", {})


# ── Indicator math ────────────────────────────────────────────────────────────

def ema(values: list[float], period: int) -> list[float]:
    """Exponential moving average"""
    k = 2 / (period + 1)
    result = [values[0]]
    for v in values[1:]:
        result.append(v * k + result[-1] * (1 - k))
    return result


def sma(values: list[float], period: int) -> list[float]:
    """Simple moving average"""
    return [
        sum(values[i:i+period]) / period
        for i in range(len(values) - period + 1)
    ]


def rsi(closes: list[float], period: int = 14) -> float:
    """Relative Strength Index (last value)"""
    changes = [closes[i] - closes[i-1] for i in range(1, len(closes))]
    gains = [max(c, 0) for c in changes]
    losses = [abs(min(c, 0)) for c in changes]

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    for i in range(period, len(changes)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)


def relative_volume(volumes: list[float], lookback: int = 20) -> float:
    """Current volume vs average of past N days"""
    if len(volumes) < lookback + 1:
        return 1.0
    avg = sum(volumes[-lookback-1:-1]) / lookback
    return round(volumes[-1] / avg, 2) if avg > 0 else 1.0


def detect_bull_flag(closes: list[float], highs: list[float]) -> bool:
    """Simplified bull flag: strong uptrend then consolidation"""
    if len(closes) < 15:
        return False
    prior_move = (closes[-10] - closes[-15]) / closes[-15]
    consolidation = (max(closes[-5:]) - min(closes[-5:])) / closes[-10]
    return prior_move > 0.05 and consolidation < 0.03


def detect_cup_handle(closes: list[float]) -> bool:
    """Cup & handle: U-shape over 30 bars, then brief pullback"""
    if len(closes) < 35:
        return False
    left = closes[-35]
    bottom = min(closes[-35:-5])
    right = closes[-5]
    handle = closes[-1]
    cup_depth = (left - bottom) / left
    return (
        cup_depth > 0.08
        and right > left * 0.97
        and handle > bottom * 1.03
        and handle < right * 0.98
    )


def ema_crossover(closes: list[float]) -> Optional[str]:
    """Check 50/200 EMA relationship"""
    if len(closes) < 201:
        return None
    ema50 = ema(closes, 50)
    ema200 = ema(closes, 200)
    if ema50[-1] > ema200[-1] and ema50[-2] <= ema200[-2]:
        return "golden_cross"
    if ema50[-1] < ema200[-1] and ema50[-2] >= ema200[-2]:
        return "death_cross"
    if ema50[-1] > ema200[-1]:
        return "above_200_ema"
    return "below_200_ema"


def detect_support(closes: list[float], lows: list[float]) -> bool:
    """Price bounced off support in last 3 days"""
    if len(lows) < 20:
        return False
    recent_low = min(lows[-3:])
    historical_lows = sorted(lows[-20:-3])
    support_zone = historical_lows[1]  # 2nd lowest as support
    return abs(recent_low - support_zone) / support_zone < 0.02


def detect_bearish_divergence(closes: list[float]) -> bool:
    """Higher price highs but RSI making lower highs"""
    if len(closes) < 30:
        return False
    mid = len(closes) // 2
    rsi_early = rsi(closes[:mid])
    rsi_late = rsi(closes[mid:])
    price_rising = closes[-1] > closes[mid]
    rsi_falling = rsi_late < rsi_early
    return price_rising and rsi_falling


def institutional_buying(volumes: list[float], closes: list[float]) -> bool:
    """High volume + price advance = institutional accumulation"""
    if len(volumes) < 5:
        return False
    avg_vol = sum(volumes[-21:-1]) / 20
    high_vol_days = [
        i for i in range(-5, 0)
        if volumes[i] > avg_vol * 1.5 and closes[i] > closes[i-1]
    ]
    return len(high_vol_days) >= 2


# ── Scoring ───────────────────────────────────────────────────────────────────

async def compute_signal(ticker: str) -> dict:
    """
    Main function: fetch data, run all indicators, produce score + signals.
    Returns a dict ready to serialize as the API response.
    """
    bars = await fetch_ohlcv(ticker.upper())

    closes = [b["c"] for b in bars]
    highs  = [b["h"] for b in bars]
    lows   = [b["l"] for b in bars]
    vols   = [b["v"] for b in bars]

    price = closes[-1]
    prev_close = closes[-2] if len(closes) >= 2 else closes[-1]
    change_pct = round((price - prev_close) / prev_close * 100, 2)

    rsi_val = rsi(closes)
    rvol = relative_volume(vols)
    ema_status = ema_crossover(closes)
    bull_flag = detect_bull_flag(closes, highs)
    cup_handle = detect_cup_handle(closes)
    support_bounce = detect_support(closes, lows)
    bear_div = detect_bearish_divergence(closes)
    inst_buy = institutional_buying(vols, closes)

    signals = []
    score = 50  # Start neutral

    # EMA / trend
    if ema_status == "golden_cross":
        signals.append({"type": "bull", "label": "Golden cross (50/200 EMA)", "weight": 15})
        score += 15
    elif ema_status == "above_200_ema":
        signals.append({"type": "bull", "label": "Above 200 EMA", "weight": 8})
        score += 8
    elif ema_status == "death_cross":
        signals.append({"type": "bear", "label": "Death cross (50/200 EMA)", "weight": -15})
        score -= 15
    elif ema_status == "below_200_ema":
        signals.append({"type": "bear", "label": "Below 200 EMA", "weight": -8})
        score -= 8

    # RSI
    if rsi_val < 30:
        signals.append({"type": "bull", "label": f"RSI oversold ({rsi_val})", "weight": 10})
        score += 10
    elif 30 <= rsi_val <= 50:
        signals.append({"type": "bull", "label": f"RSI reset ({rsi_val})", "weight": 5})
        score += 5
    elif rsi_val > 70:
        signals.append({"type": "bear", "label": f"RSI overbought ({rsi_val})", "weight": -8})
        score -= 8

    # Volume
    if rvol >= 2.0:
        signals.append({"type": "bull", "label": f"Relative volume {rvol}x", "weight": 10})
        score += 10
    elif rvol >= 1.4:
        signals.append({"type": "bull", "label": f"Above-avg volume {rvol}x", "weight": 5})
        score += 5
    elif rvol < 0.7:
        signals.append({"type": "bear", "label": f"Low volume {rvol}x", "weight": -5})
        score -= 5

    # Patterns
    if bull_flag:
        signals.append({"type": "bull", "label": "Bull flag pattern", "weight": 8})
        score += 8

    if cup_handle:
        signals.append({"type": "bull", "label": "Cup & handle pattern", "weight": 10})
        score += 10

    if support_bounce:
        signals.append({"type": "bull", "label": "Support level bounce", "weight": 7})
        score += 7

    # Institutional
    if inst_buy:
        signals.append({"type": "bull", "label": "Institutional buying detected", "weight": 10})
        score += 10

    # Bearish
    if bear_div:
        signals.append({"type": "bear", "label": "Bearish RSI divergence", "weight": -10})
        score -= 10

    # Momentum
    if change_pct > 3:
        signals.append({"type": "bull", "label": f"Strong momentum +{change_pct}%", "weight": 5})
        score += 5
    elif change_pct < -3:
        signals.append({"type": "bear", "label": f"Selling pressure {change_pct}%", "weight": -5})
        score -= 5

    # Clamp score 0–100
    score = max(0, min(100, score))

    # Direction
    if score >= 65:
        direction = "bull"
    elif score <= 40:
        direction = "bear"
    else:
        direction = "neutral"

    return {
        "ticker": ticker.upper(),
        "score": score,
        "direction": direction,
        "price": round(price, 2),
        "change_pct": change_pct,
        "rsi": rsi_val,
        "relative_volume": rvol,
        "signals": signals,
        "generated_at": datetime.utcnow().isoformat() + "Z",
    }
