#!/usr/bin/env python3
"""
Run this once after setting up your .env to initialize the database
and generate a test API key.
"""
from app.core.database import create_tables, SessionLocal
from app.core.auth import create_api_key

print("Creating database tables...")
create_tables()

db = SessionLocal()
key = create_api_key("admin@yourdomain.com", "enterprise", db)
db.close()

print(f"\n✅ Database ready.")
print(f"🔑 Your admin API key (save this!):\n\n   {key}\n")
print("Start the server with:")
print("   uvicorn app.main:app --reload\n")
print("Then visit: http://localhost:8000/docs")
