from sqlalchemy import create_engine, Column, String, Integer, DateTime, Boolean, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from app.core.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class APIKey(Base):
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, index=True)
    key_hash = Column(String, unique=True, index=True)       # hashed key stored
    key_prefix = Column(String, index=True)                  # first 8 chars for lookup
    email = Column(String, index=True)
    plan = Column(String, default="free")                    # free/starter/pro/growth/enterprise
    stripe_customer_id = Column(String, nullable=True)
    stripe_subscription_id = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    calls_today = Column(Integer, default=0)
    last_reset = Column(DateTime, default=datetime.utcnow)   # for daily counter reset


class SignalCache(Base):
    __tablename__ = "signal_cache"

    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String, index=True)
    score = Column(Integer)
    direction = Column(String)
    price = Column(Float)
    change_pct = Column(Float)
    signals_json = Column(String)     # JSON blob
    cached_at = Column(DateTime, default=datetime.utcnow)


def create_tables():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
