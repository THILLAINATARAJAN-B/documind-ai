from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.database import engine, Base
from app.routers import auth, upload, chat

# Create all database tables on startup
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="DocuMind AI",
    description="AI-powered Document & Multimedia Q&A API",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200", "http://localhost:80"],
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