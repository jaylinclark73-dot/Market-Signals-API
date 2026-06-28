from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
import json
from datetime import datetime, timedelta

from app.core.auth import verify_and_rate_limit
from app.core.database import get_db, SignalCache, APIKey
from app.services.scorer import compute_signal

router = APIRouter()

CACHE_MINUTES = 5  # Cache signals for 5 min (use 0 for real-time plans)


async def get_cached_or_compute(ticker: str, db: Session, plan: str) -> dict:
    ticker = ticker.upper()

    # Free/starter plans: use cache
    cache_ttl = 0 if plan in ("pro", "growth", "enterprise") else CACHE_MINUTES

    if cache_ttl > 0:
        cached = (
            db.query(SignalCache)
            .filter(SignalCache.ticker == ticker)
            .order_by(SignalCache.cached_at.desc())
            .first()
        )
        if cached and cached.cached_at > datetime.utcnow() - timedelta(minutes=cache_ttl):
            result = json.loads(cached.signals_json)
            result["cached"] = True
            return result

    # Compute fresh signal
    result = await compute_signal(ticker)

    # Store in cache
    db.merge(SignalCache(
        ticker=ticker,
        score=result["score"],
        direction=result["direction"],
        price=result["price"],
        change_pct=result["change_pct"],
        signals_json=json.dumps(result),
        cached_at=datetime.utcnow(),
    ))
    db.commit()

    result["cached"] = False
    return result


@router.get("/signals")
async def get_signal(
    ticker: str = Query(..., description="Stock ticker, e.g. AAPL"),
    db: Session = Depends(get_db),
    api_key: APIKey = Depends(verify_and_rate_limit),
):
    """
    Get a scored market signal for a single ticker.

    Returns a 0–100 score, direction (bull/bear/neutral), and a list of
    detected signals with their type and label.
    """
    if not ticker.isalpha() or len(ticker) > 5:
        raise HTTPException(status_code=400, detail="Invalid ticker symbol.")

    try:
        result = await get_cached_or_compute(ticker, db, api_key.plan)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Market data error: {str(e)}")

    return result


@router.get("/signals/batch")
async def get_signals_batch(
    tickers: str = Query(..., description="Comma-separated tickers, e.g. AAPL,TSLA,NVDA"),
    db: Session = Depends(get_db),
    api_key: APIKey = Depends(verify_and_rate_limit),
):
    """
    Get signals for multiple tickers at once (Pro+ only, max 10).
    Each ticker counts as one API call against your daily limit.
    """
    if api_key.plan not in ("pro", "growth", "enterprise"):
        raise HTTPException(
            status_code=403,
            detail="Batch endpoint requires Pro plan or above. Upgrade at https://yourdomain.com/pricing",
        )

    ticker_list = [t.strip().upper() for t in tickers.split(",")][:10]

    results = []
    for ticker in ticker_list:
        if not ticker.isalpha() or len(ticker) > 5:
            results.append({"ticker": ticker, "error": "invalid_ticker"})
            continue
        try:
            result = await get_cached_or_compute(ticker, db, api_key.plan)
            results.append(result)
        except Exception as e:
            results.append({"ticker": ticker, "error": str(e)})

    return {"results": results, "count": len(results)}


@router.get("/signals/leaderboard")
async def get_leaderboard(
    direction: Optional[str] = Query(None, description="Filter: bull, bear, or neutral"),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    api_key: APIKey = Depends(verify_and_rate_limit),
):
    """
    Return top-scored tickers from the cache, sorted by score.
    Great for building screeners or daily watchlists.
    """
    query = db.query(SignalCache)
    if direction:
        query = query.filter(SignalCache.direction == direction)

    # Only include signals cached in last hour
    cutoff = datetime.utcnow() - timedelta(hours=1)
    query = query.filter(SignalCache.cached_at > cutoff)

    rows = query.order_by(SignalCache.score.desc()).limit(limit).all()

    results = []
    for row in rows:
        data = json.loads(row.signals_json)
        results.append({
            "ticker": row.ticker,
            "score": row.score,
            "direction": row.direction,
            "price": row.price,
            "change_pct": row.change_pct,
        })

    return {"results": results, "count": len(results)}
