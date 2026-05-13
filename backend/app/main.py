# backend/app/main.py
import time
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.core.config import settings
from app.core.database import engine, Base
from app.routers import auth, upload, chat

def create_tables_with_retry(retries: int = 10, delay: float = 2.0):
    for attempt in range(retries):
        try:
            Base.metadata.create_all(bind=engine)
            print("✅ Database tables created/verified")
            return
        except Exception as e:
            print(f"⏳ DB not ready (attempt {attempt+1}/{retries}): {e}")
            time.sleep(delay)
    raise RuntimeError("❌ Could not connect to database after retries")

@asynccontextmanager
async def lifespan(app: FastAPI):
    create_tables_with_retry()
    yield

app = FastAPI(
    title="DocuMind AI",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(upload.router, prefix="/upload", tags=["upload"])
app.include_router(chat.router, prefix="/chat", tags=["chat"])

@app.get("/health")
async def health():
    return {"status": "ok"}