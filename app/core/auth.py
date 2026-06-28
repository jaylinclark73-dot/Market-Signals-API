import hashlib
import secrets
import string
from datetime import datetime, date
from fastapi import HTTPException, Security, Depends
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session
from app.core.database import get_db, APIKey
from app.core.config import settings

api_key_header = APIKeyHeader(name="Authorization", auto_error=False)


def generate_api_key() -> str:
    """Generate a new API key in format sk-mkt-XXXXXXXXXXXX"""
    alphabet = string.ascii_letters + string.digits
    token = "".join(secrets.choice(alphabet) for _ in range(32))
    return f"sk-mkt-{token}"


def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def get_key_prefix(key: str) -> str:
    return key[:12]  # "sk-mkt-XXXX"


def create_api_key(email: str, plan: str, db: Session) -> str:
    raw_key = generate_api_key()
    db_key = APIKey(
        key_hash=hash_key(raw_key),
        key_prefix=get_key_prefix(raw_key),
        email=email,
        plan=plan,
    )
    db.add(db_key)
    db.commit()
    return raw_key  # Only returned ONCE — never stored in plain text


def verify_and_rate_limit(
    authorization: str = Security(api_key_header),
    db: Session = Depends(get_db),
) -> APIKey:
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing API key. Pass: Authorization: Bearer sk-mkt-...")

    # Strip "Bearer " prefix
    raw_key = authorization.replace("Bearer ", "").strip()

    if not raw_key.startswith("sk-mkt-"):
        raise HTTPException(status_code=401, detail="Invalid API key format.")

    # Look up by hash
    key_hash = hash_key(raw_key)
    db_key = db.query(APIKey).filter(APIKey.key_hash == key_hash).first()

    if not db_key or not db_key.is_active:
        raise HTTPException(status_code=401, detail="Invalid or revoked API key.")

    # Reset daily counter if it's a new day
    if db_key.last_reset.date() < date.today():
        db_key.calls_today = 0
        db_key.last_reset = datetime.utcnow()

    # Check rate limit
    limit = settings.RATE_LIMITS.get(db_key.plan, 10)
    if db_key.calls_today >= limit:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "rate_limit_exceeded",
                "plan": db_key.plan,
                "limit": limit,
                "calls_today": db_key.calls_today,
                "upgrade_url": "https://yourdomain.com/pricing",
            },
        )

    # Increment counter
    db_key.calls_today += 1
    db.commit()

    return db_key
