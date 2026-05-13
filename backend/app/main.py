import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.database import engine, Base
from app.core.config import get_settings          # ✅ correct import
from app.routers import auth, upload, chat

settings = get_settings()                         # ✅ call it here


def _create_tables_with_retry(retries: int = 15, delay: float = 2.0) -> None:
    last_exc = None
    for attempt in range(1, retries + 1):
        try:
            Base.metadata.create_all(bind=engine)
            print(f"✅ Database tables ready (attempt {attempt})")
            return
        except Exception as exc:
            last_exc = exc
            print(f"⏳ Postgres not ready yet (attempt {attempt}/{retries}): {exc}")
            time.sleep(delay)
    raise RuntimeError(
        f"❌ Could not connect to Postgres after {retries} attempts"
    ) from last_exc


@asynccontextmanager
async def lifespan(app: FastAPI):
    _create_tables_with_retry()
    yield


app = FastAPI(
    title="DocuMind AI",
    description="AI-powered Document & Multimedia Q&A API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(upload.router)
app.include_router(chat.router)


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "DocuMind AI"}