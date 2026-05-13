from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.database import engine, Base
from app.routers import auth, upload, chat

settings = get_settings()

# Create all database tables on startup
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="DocuMind AI",
    description="AI-powered Document & Multimedia Q&A API",
    version="1.0.0",
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