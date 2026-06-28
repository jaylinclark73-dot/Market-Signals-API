from fastapi import APIRouter
from datetime import datetime

router = APIRouter()

@router.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat() + "Z"}

@router.get("/")
async def root():
    return {
        "name": "Market Signals API",
        "version": "1.0.0",
        "docs": "/docs",
        "register": "POST /v1/auth/register",
    }
