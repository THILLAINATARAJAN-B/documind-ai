<div align="center">

# 🧠 DocuMind AI

### AI-Powered Document & Multimedia Q&A System

[








Upload PDFs, audio, and video files — then ask intelligent questions about their content using GPT-4 with Retrieval-Augmented Generation (RAG).

</div>

***

## 📸 Screenshots

<table>
  <tr>
    <td align="center" width="50%">
      <img src="Test/Screenshots/Dashboard.png" alt="Dashboard — File Manager" width="100%"/>
      
      <br/>
      <sub><b>📁 Dashboard — Upload & manage your documents and media</b></sub>
    </td>
    <td align="center" width="50%">
      <img src="Test/Screenshots/pdf-chat.png" alt="PDF Chat Interface" width="100%"/>
      <br/>
      <sub><b>📄 PDF Chat — Ask questions about your PDF documents</b></sub>
    </td>
  </tr>
  <tr>
    <td align="center" colspan="2">
      <img src="Test/Screenshots/audio-video-chat.png" alt="Audio & Video Chat with Timestamps" width="75%"/>
      <br/>
      <sub><b>🎵 Audio / Video Chat — Answers linked to exact timestamps in the media</b></sub>
    </td>
  </tr>
</table>

***

## 📌 Overview

DocuMind AI lets users upload documents and media, then have natural language conversations about their content. The backend extracts text and transcripts, builds a semantic vector index with FAISS, and streams GPT-4 answers back in real time via Server-Sent Events (SSE). Audio and video answers include exact **timestamp references** back to the source moment in the file.

***

## ✨ Features

| Feature | Description |
|---|---|
| 📄 **PDF Processing** | Extract and chunk text from PDF documents using PyMuPDF |
| 🎵 **Audio/Video Transcription** | Whisper-powered transcription with segment-level timestamps |
| 🧠 **RAG Q&A** | GPT-4 answers grounded in uploaded content via FAISS semantic search |
| ⏱️ **Timestamp References** | Audio/video answers link back to exact moments in the file |
| 💬 **Chat Sessions** | Multi-turn conversations with persistent message history |
| ⚡ **Real-time Streaming** | Live response streaming via Server-Sent Events |
| 🔐 **JWT Authentication** | Register, login, refresh tokens, and secure route protection |
| 🚦 **Rate Limiting** | Redis-backed per-user request throttling |
| 📦 **Docker Compose** | One-command local deployment with Postgres + Redis + backend |

***

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                      Client Browser                      │
│              Angular 21 SSR (port 4200)                  │
└──────────────────────────┬──────────────────────────────┘
                           │ HTTP / SSE
┌──────────────────────────▼──────────────────────────────┐
│                   FastAPI Backend                         │
│                     (port 8001)                          │
│                                                          │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │ Auth Router │  │Upload Router │  │  Chat Router  │  │
│  │  /auth/*    │  │  /upload/*   │  │   /chat/ask   │  │
│  └─────────────┘  └──────┬───────┘  └──────┬────────┘  │
│                           │                  │           │
│  ┌────────────────────────▼──────────────────▼────────┐ │
│  │               Services Layer                        │ │
│  │  PdfProcessor │ AudioProcessor │ ChatEngine         │ │
│  │  Embeddings (FAISS) │ Security (JWT/bcrypt)         │ │
│  └────────────┬─────────────────────────┬─────────────┘ │
└───────────────┼─────────────────────────┼───────────────┘
                │                         │
   ┌────────────▼──────┐       ┌──────────▼──────────┐
   │  PostgreSQL 15    │       │     Redis 7          │
   │  (port 5432)      │       │  (port 6380)         │
   │  Users, Files,    │       │  Rate limiting,      │
   │  Chat history     │       │  Summary cache       │
   └───────────────────┘       └─────────────────────┘
```

***

## 🛠️ Tech Stack

### Backend

| Layer | Technology |
|---|---|
| Framework | FastAPI 0.136 (async) |
| Language | Python 3.11 |
| Database | PostgreSQL 15 + SQLAlchemy 2.0 |
| Migrations | Alembic |
| Cache | Redis 7 |
| Auth | JWT (PyJWT) + bcrypt |
| Vector Search | FAISS 1.13 |
| LLM | OpenAI GPT-4 |
| PDF Parsing | PyMuPDF |
| Transcription | OpenAI Whisper |
| Text Chunking | LangChain |
| Testing | Pytest + pytest-cov (96% coverage) |

### Frontend

| Layer | Technology |
|---|---|
| Framework | Angular 21 with SSR |
| Language | TypeScript 5.9 |
| UI Library | Angular Material 21 |
| State/Async | RxJS 7.8 |
| File Upload | ngx-dropzone |
| Streaming | Server-Sent Events (SSE) |
| Web Server | Express.js 5 (SSR runtime) |

***

## 🚀 Quick Start

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) & Docker Compose
- An [OpenAI API key](https://platform.openai.com/api-keys)

### 1. Clone the repository

```bash
git clone https://github.com/THILLAINATARAJAN-B/documind-ai.git
cd documind-ai
```

### 2. Configure environment variables

Create a `.env` file in the project root:

```env
# Required
OPENAI_API_KEY=sk-your-openai-api-key-here
SECRET_KEY=your-super-secret-jwt-key-change-this

# Pre-configured for Docker Compose (do not change unless running locally)
DATABASE_URL=postgresql://documind:documind123@postgres:5432/documinddb
REDIS_URL=redis://redis:6379/0

# Optional
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
MAX_FILE_SIZE_MB=50
UPLOAD_DIR=/app/uploads
FAISS_STORE_DIR=/app/faiss_store
```

### 3. Start all services

```bash
docker-compose up --build
```

| Service | URL |
|---|---|
| Backend API | http://localhost:8001 |
| API Docs (Swagger) | http://localhost:8001/docs |
| Frontend | http://localhost:4200 |

***

## 🔧 Local Development (Without Docker)

### Backend

```bash
cd backend

# Install dependencies
pip install -r requirements.txt

# Set environment variables
export DATABASE_URL=postgresql://documind:documind123@localhost:5432/documinddb
export REDIS_URL=redis://localhost:6380/0
export OPENAI_API_KEY=sk-...
export SECRET_KEY=your-secret-key
export UPLOAD_DIR=./uploads
export FAISS_STORE_DIR=./faiss_store

# Create upload directories
mkdir -p uploads faiss_store

# Start the server
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm start
# Runs on http://localhost:4200
```

***

## 🧪 Testing

```bash
cd backend

# Run all tests with coverage report
python -m pytest tests/ --cov=app --cov-report=term-missing -v

# Run a specific test file
python -m pytest tests/test_auth.py -v

# Generate HTML coverage report
python -m pytest tests/ --cov=app --cov-report=html
```

### Coverage Summary

```
Name                              Stmts   Miss  Cover
-------------------------------------------------------
app/core/__init__.py                  1      0   100%
app/core/config.py                   21      0   100%
app/core/database.py                 13      0   100%
app/core/redis_client.py             12      1    92%
app/core/security.py                 26      1    96%
app/main.py                          32      5    84%
app/models/models.py                 59      0   100%
app/routers/auth.py                  57      1    98%
app/routers/chat.py                  68      0   100%
app/routers/upload.py               158     11    93%
app/services/audio_processor.py      52      7    87%
app/services/chat_engine.py          96      2    98%
app/services/embeddings.py           91      5    95%
app/services/pdf_processor.py        14      0   100%
-------------------------------------------------------
TOTAL                               750     33    96%
```

**101 tests** across 4 test files covering authentication, file upload, chat streaming, service logic, and edge cases.

***

## 📡 API Reference

### Authentication

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/auth/register` | Create a new user account |
| `POST` | `/auth/login` | Login and receive JWT tokens |
| `POST` | `/auth/refresh` | Refresh access token |
| `POST` | `/auth/logout` | Invalidate refresh token |

### File Management

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/upload/pdf` | Upload and index a PDF file |
| `POST` | `/upload/audio` | Upload and transcribe audio/video |
| `GET` | `/upload/files` | List all uploaded files |
| `DELETE` | `/upload/files/{id}` | Delete a file and its index |
| `GET` | `/upload/files/{id}/summary` | Get AI-generated file summary |
| `GET` | `/upload/files/{id}/segments` | Get transcript segments (audio/video) |
| `GET` | `/upload/files/{id}/stream` | Stream media file |

### Chat

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/chat/ask` | Ask a question (streams SSE response) |
| `GET` | `/chat/sessions/{id}/messages` | Get chat message history |

### Health

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Service health check |

Full interactive docs available at **`/docs`** (Swagger UI) and **`/redoc`**.

***

## 🗄️ Database Schema

```
users                  files                    chat_sessions
─────────────          ──────────────────────   ─────────────────────
id (PK)                id (PK)                  id (PK)
email (UNIQUE)         user_id (FK → users)     user_id (FK → users)
hashed_password        filename                 created_at
created_at             original_filename
                       file_type                chat_messages
                       file_path                ─────────────────────
                       uploaded_at              id (PK)
                                                session_id (FK)
transcript_segments                             file_id (FK)
─────────────────────                           role (user|assistant)
id (PK)                                         content
file_id (FK → files)                            timestamp_ref
text                                            created_at
start_seconds
end_seconds
segment_index
```

***

## 🐳 Docker Services

```yaml
services:
  backend   → FastAPI app  (host: 8001 → container: 8000)
  postgres  → PostgreSQL 15 (port 5432)
  redis     → Redis 7       (host: 6380 → container: 6379)

volumes:
  postgres_data   → database persistence
  uploads_data    → uploaded files
  faiss_data      → vector embeddings

network:
  documind_net (bridge) → internal service communication
```

***

## ⚙️ CI/CD Pipeline

The GitHub Actions pipeline runs on every push to `main` and `develop`:

```
push to main / develop
        │
        ▼
┌─────────────────────────────┐
│       test-backend          │
│  ✅ Python 3.11 setup       │
│  ✅ 101 tests passing       │  ← pytest, ruff lint
│  ✅ 96% coverage            │  ← --cov-fail-under=95
└──────────────┬──────────────┘
               │  (on main only)
               ▼
┌─────────────────────────────┐
│       build-docker          │
│  ✅ Backend image builds    │
│  ✅ Frontend image builds   │
└─────────────────────────────┘
```

***

## 📁 Project Structure

```
documind-ai/
├── .github/
│   └── workflows/
│       └── ci.yml              # CI/CD pipeline (test + build)
├── docker-compose.yml          # Multi-service orchestration
├── .env                        # Environment variables (not committed)
├── README.md
│
├── backend/                    # FastAPI + RAG backend
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── main.py             # App entry point & lifespan
│       ├── core/
│       │   ├── config.py       # Pydantic settings
│       │   ├── database.py     # SQLAlchemy engine & session
│       │   ├── redis_client.py # Redis connection
│       │   └── security.py     # JWT & bcrypt utilities
│       ├── models/
│       │   └── models.py       # ORM models (User, File, Chat...)
│       ├── routers/
│       │   ├── auth.py         # /auth/* endpoints
│       │   ├── chat.py         # /chat/* endpoints (SSE streaming)
│       │   ├── upload.py       # /upload/* endpoints
│       │   └── deps.py         # Shared FastAPI dependencies
│       ├── schemas/
│       │   ├── auth.py         # Auth request/response models
│       │   ├── chat.py         # Chat request/response models
│       │   └── file.py         # File response models
│       └── services/
│           ├── audio_processor.py  # Whisper transcription
│           ├── chat_engine.py      # GPT-4 RAG + streaming
│           ├── embeddings.py       # FAISS index management
│           └── pdf_processor.py    # PyMuPDF text extraction
│
└── frontend/                   # Angular 21 SSR app
    ├── Dockerfile
    └── src/
        └── app/
            ├── core/           # Auth guard, HTTP interceptors, services
            └── pages/          # Login, Register, Dashboard, Chat
```

***

## 🔐 Security

- Passwords hashed with **bcrypt** (salted, work factor 12)
- Stateless auth via **JWT access tokens** (60-minute expiry)
- **Refresh tokens** stored in Redis with rotation on each use
- **CORS** configured for allowed origins only
- **Rate limiting** on chat endpoints (Redis-backed sliding window)
- **Magic byte validation** on all file uploads — rejects files with spoofed MIME types
- **File size limits** enforced server-side before any processing begins

***

## 📄 License

This project is licensed under the [MIT License](LICENSE).

***

<div align="center">
Built with ❤️ using FastAPI, Angular, and OpenAI
</div>
