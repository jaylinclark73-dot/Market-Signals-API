from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # Market data provider (polygon.io recommended)
    POLYGON_API_KEY: str = "YOUR_POLYGON_API_KEY"

    # Database (SQLite for dev, Postgres for prod)
    DATABASE_URL: str = "sqlite:///./signals.db"

    # API key hashing secret
    SECRET_KEY: str = "change-this-in-production-use-openssl-rand-hex-32"

    # Rate limiting (per plan, per day)
    RATE_LIMITS: dict = {
        "free":       10,
        "starter":    500,
        "pro":        5000,
        "growth":     25000,
        "enterprise": 999999,
    }

    # Stripe
    STRIPE_SECRET_KEY: Optional[str] = None
    STRIPE_WEBHOOK_SECRET: Optional[str] = None

    # Stripe price IDs (create these in your Stripe dashboard)
    STRIPE_PRICES: dict = {
        "starter":  "price_XXXX_starter",
        "pro":      "price_XXXX_pro",
        "growth":   "price_XXXX_growth",
    }

    class Config:
        env_file = ".env"

settings = Settings()
