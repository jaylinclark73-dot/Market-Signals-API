from pydantic_settings import BaseSettings
from typing import Optional
import os

class Settings(BaseSettings):
    POLYGON_API_KEY: str = "YOUR_POLYGON_API_KEY"
    DATABASE_URL: str = "sqlite:///./signals.db"
    SECRET_KEY: str = "change-this-in-production"
    RATE_LIMITS: dict = {
        "free":       10,
        "starter":    500,
        "pro":        5000,
        "growth":     25000,
        "enterprise": 999999,
    }
    STRIPE_SECRET_KEY: Optional[str] = None
    STRIPE_WEBHOOK_SECRET: Optional[str] = None

    @property
    def STRIPE_PRICES(self) -> dict:
        return {
            "starter":  os.getenv("STRIPE_PRICE_STARTER", ""),
            "pro":      os.getenv("STRIPE_PRICE_PRO", ""),
            "growth":   os.getenv("STRIPE_PRICE_GROWTH", ""),
        }

    class Config:
        env_file = ".env"

settings = Settings()