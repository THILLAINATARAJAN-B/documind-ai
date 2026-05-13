from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.database import engine, Base
from app.core.config import get_settings
from app.routers import auth, upload, chat

settings = get_settings()

# Create all database tables on startup
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="DocuMind AI",
    description="AI-powered Document & Multimedia Q&A API",
    version="1.0.0",
)

# Dynamic CORS — configured via ALLOWED_ORIGINS env variable
# Supports both browser (localhost:4200) and SSR (frontend docker service)
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
