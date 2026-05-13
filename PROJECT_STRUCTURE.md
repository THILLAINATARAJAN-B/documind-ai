# DocuMind AI - Complete Project Structure & Analysis

## 🎯 What is DocuMind AI?

**DocuMind AI** is an **AI-powered Document & Multimedia Q&A System** that enables users to upload PDFs, audio, and video files, then ask intelligent questions about their content. The system uses advanced Retrieval-Augmented Generation (RAG) with OpenAI's GPT-4 to provide accurate, context-aware answers with real-time streaming responses.

### Key Capabilities
- 📄 **PDF Processing**: Extract and index text from PDF documents
- 🎵 **Audio/Video Transcription**: Convert audio/video to searchable text with timestamps
- 🧠 **AI Q&A with RAG**: Ask questions and get answers grounded in uploaded content
- ⏱️ **Timestamp References**: Audio/video answers include exact timestamps to referenced moments
- 💬 **Chat Sessions**: Multi-turn conversations with persistent chat history
- 🔐 **Secure Authentication**: User accounts with JWT-based auth
- ⚡ **Real-time Streaming**: Live response streaming via Server-Sent Events (SSE)
- 📊 **Vector Search**: FAISS-based semantic search for relevant content chunks

---

## 📁 Project Root Structure

```
documind-ai/
├── docker-compose.yml              # 🐳 Multi-service orchestration
├── PROJECT_STRUCTURE.md            # This file
├── .env                            # Environment variables
├── backend/                        # 🐍 FastAPI REST API
└── frontend/                       # 🅰️ Angular 21 with SSR
```

---

## 🐍 Backend (`/backend`) - FastAPI + RAG System

### Complete Structure

```
backend/
├── Dockerfile                      # Production-ready image
├── requirements.txt                # Python dependencies (40+ packages)
├── alembic.ini                     # Database migration config
├── .env                            # Credentials & API keys
├── .coverage                       # Test coverage report
│
├── alembic/                        # Database migrations
│   └── env.py                      # Alembic environment setup
│
├── app/                            # Main application
│   ├── main.py                     # 🚀 FastAPI app entry point
│   │                                  # - CORS middleware
│   │                                  # - Database table creation
│   │                                  # - Router mounting
│   │                                  # - Health check endpoint
│   │
│   ├── core/                       # Core infrastructure
│   │   ├── __init__.py
│   │   ├── config.py               # ⚙️ Settings management (Pydantic)
│   │   ├── database.py             # 🗄️ SQLAlchemy engine & session
│   │   ├── redis_client.py         # 💾 Redis connection manager
│   │   └── security.py             # 🔐 JWT, password hashing
│   │
│   ├── models/                     # Database ORM models
│   │   ├── __init__.py
│   │   └── models.py               # 📊 Schema definitions:
│   │                                  # - User (email, hashed_password)
│   │                                  # - File (pdf/audio/video, file_path)
│   │                                  # - TranscriptSegment (text, timestamps)
│   │                                  # - ChatSession (user sessions)
│   │                                  # - ChatMessage (conversation history)
│   │
│   ├── routers/                    # 🛣️ API endpoints
│   │   ├── __init__.py
│   │   ├── auth.py                 # 🔑 POST /auth/register, /auth/login
│   │   ├── upload.py               # 📤 POST /upload/pdf, /audio
│   │   ├── chat.py                 # 💬 POST /chat/ask (streaming SSE)
│   │   └── deps.py                 # 🔌 Dependency injection
│   │                                  # - get_current_user_dep (JWT validation)
│   │                                  # - get_db (DB session)
│   │
│   ├── schemas/                    # Pydantic validation models
│   │   ├── __init__.py
│   │   ├── auth.py                 # RegisterRequest, LoginRequest, Token
│   │   ├── chat.py                 # AskRequest, ChatMessageResponse
│   │   └── file.py                 # FileUpload, FileResponse
│   │
│   ├── services/                   # 🧠 Business logic layer
│   │   ├── __init__.py
│   │   ├── chat_engine.py          # 🤖 stream_answer() - RAG query processor
│   │   │                              # - Semantic search via embeddings
│   │   │                              # - GPT-4 prompt + streaming
│   │   │                              # - Timestamp extraction for audio/video
│   │   ├── embeddings.py           # 🔍 FAISS vector store manager
│   │   │                              # - search_chunks() - semantic search
│   │   │                              # - add_chunks() - index documents
│   │   ├── pdf_processor.py        # 📄 PDF extraction & chunking
│   │   │                              # - Text extraction with PyMuPDF
│   │   │                              # - Document splitting (overlapping chunks)
│   │   └── audio_processor.py      # 🎵 Audio transcription & segmentation
│   │                                  # - Whisper transcription
│   │                                  # - Segment alignment with timestamps
│   │
│   └── uploads/                    # 📂 Uploaded files directory
│       ├── *.pdf                   # PDF files
│       ├── *.wav / *.mp3           # Audio files
│       └── faiss_store/            # Vector embeddings (FAISS index)
│
├── tests/                          # ✅ Test suite
│   ├── __init__.py
│   ├── conftest.py                 # Pytest fixtures & config
│   ├── test_auth.py                # Authentication tests
│   ├── test_chat.py                # Chat streaming tests
│   ├── test_upload.py              # File upload tests
│   └── test_services.py            # Service layer tests
```

### Backend Key Technologies

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Framework** | FastAPI 0.136 | Async REST API, auto-docs |
| **Database** | PostgreSQL 15 | User, file, chat persistence |
| **ORM** | SQLAlchemy 2.0 | Type-safe queries |
| **Migrations** | Alembic 1.18 | Schema versioning |
| **Cache** | Redis 7 | Rate limiting, session cache |
| **Auth** | JWT + bcrypt | Secure token-based auth |
| **Embeddings** | FAISS 1.13 | Vector similarity search |
| **LLM** | OpenAI GPT-4 | Response generation |
| **PDF** | PyMuPDF 1.27 | Document parsing |
| **Text Split** | LangChain | Smart chunking |
| **Testing** | Pytest + coverage | Unit & integration tests |

---

## 🅰️ Frontend (`/frontend`) - Angular 21 with SSR

### Complete Structure

```
frontend/
├── Dockerfile                      # SSR-ready image
├── nginx.conf                      # Production web server config
├── package.json                    # Dependencies: Angular 21
├── tsconfig.json                   # TypeScript base config
├── tsconfig.app.json               # App-specific TypeScript config
├── tsconfig.spec.json              # Test TypeScript config
├── angular.json                    # Angular CLI config
├── README.md                       # Documentation
│
├── public/                         # 📦 Static assets
│
└── src/                            # 💻 Source code
    ├── index.html                  # Entry HTML
    ├── main.ts                     # 🌐 Browser bootstrap
    ├── main.server.ts              # 🖥️ SSR server bootstrap
    ├── server.ts                   # Express.js SSR server
    ├── styles.scss                 # 🎨 Global styles
    │
    └── app/                        # Angular application root
        ├── app.ts                  # Root component
        ├── app.html                # Root template
        ├── app.scss                # Root styles
        ├── app.component.ts        # Main component logic
        ├── app.component.html      # Main template
        ├── app.component.scss      # Main styles
        ├── app.spec.ts             # Root component tests
        │
        ├── app.routes.ts           # 🛣️ Client-side routing
        │                              # - /login (public)
        │                              # - /register (public)
        │                              # - /dashboard (protected)
        │                              # - /chat/:fileId (protected)
        ├── app.routes.server.ts    # 🖥️ Server-side routing
        ├── app.config.ts           # 🌐 Client config
        ├── app.config.server.ts    # 🖥️ Server config
        │
        ├── core/                   # 🔧 Core services & guards
        │   ├── guards/
        │   │   └── auth.guard.ts   # 🔐 Route protection
        │   │                          # - Redirects to /login if not authenticated
        │   │
        │   ├── interceptors/
        │   │   └── auth.interceptor.ts # 🔑 JWT injection
        │   │                           # - Adds Authorization header
        │   │                           # - Handles 401 errors
        │   │
        │   └── services/
        │       ├── api.service.ts  # 📡 HTTP API client
        │       │                      # - uploadPdf()
        │       │                      # - uploadAudio()
        │       │                      # - getFiles()
        │       │                      # - deleteFile()
        │       │                      # - askQuestion()
        │       ├── auth.service.ts # 🔑 Authentication
        │       │                      # - login()
        │       │                      # - register()
        │       │                      # - logout()
        │       │                      # - isAuthenticated$
        │       └── sse.service.ts  # 🌊 Server-Sent Events
        │                              # - connectStream()
        │                              # - Real-time message streaming
        │
        └── pages/                  # 📄 Feature pages (lazy-loaded)
            ├── login/              # 🔓 Login page
            │   ├── login.component.ts
            │   ├── login.component.html
            │   └── login.component.scss
            │
            ├── register/           # 📝 Registration page
            │   ├── register.component.ts
            │   ├── register.component.html
            │   └── register.component.scss
            │
            ├── dashboard/          # 📊 File management
            │   ├── dashboard.component.ts
            │   ├── dashboard.component.html
            │   └── dashboard.component.scss
            │
            └── chat/               # 💬 Q&A interface
                ├── chat.component.ts
                ├── chat.component.html
                └── chat.component.scss
```

### Frontend Key Technologies

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Framework** | Angular 21.2 | SSR-ready, standalone components |
| **Language** | TypeScript 5.9 | Type-safe development |
| **SSR** | Angular Universal | Server-side rendering |
| **HTTP** | HttpClient | API communication |
| **Async** | RxJS 7.8 | Reactive streams |
| **Forms** | Reactive Forms | Form handling & validation |
| **UI** | Angular Material 21 | Material Design components |
| **Files** | ngx-dropzone | Drag-drop file upload |
| **Web Server** | Express.js 5 | SSR server runtime |
| **Styling** | SCSS | Componentized styles |
| **Testing** | Vitest + Jasmine | Unit tests |

---

## 🐳 Docker Architecture

### Services in docker-compose.yml

```yaml
Services:
├── backend (port 8001)          FastAPI on port 8000 → mapped to 8001
├── postgres (port 5432)         PostgreSQL 15 Alpine
├── redis (port 6380)            Redis 7 Alpine
└── (Optional frontend service)
```

### Volumes & Persistence
```
Volumes:
├── postgres_data/               Database storage
├── uploads_data/                Uploaded PDF/audio files
└── faiss_data/                  Vector embeddings store
```

### Network
```
documind_net (bridge)            All services communicate internally
```

---

## 🔴 CRITICAL PROBLEMS TO SOLVE

### 1. **Vector Store Not Persistent** ⚠️ HIGH PRIORITY
- **Problem**: FAISS index stored in memory; lost on container restart
- **Impact**: All vector embeddings disappear; RAG breaks
- **Solution**: 
  - Serialize FAISS index to `/app/faiss_store/` volume
  - Load on startup
  - Save after each document upload

### 2. **File Deletion Doesn't Clean Embeddings** ⚠️ HIGH PRIORITY
- **Problem**: Deleting a file leaves orphaned embeddings in FAISS
- **Impact**: Garbage data in vector store; irrelevant search results
- **Solution**: 
  - Track which embeddings belong to which file_id
  - Remove embeddings when file is deleted
  - Implement embedding garbage collection

### 3. **Hardcoded API URL in Frontend** ⚠️ MEDIUM PRIORITY
- **Problem**: Frontend API URL hardcoded to `localhost:8001`
- **Impact**: Can't deploy to production/different environments
- **Solution**:
  - Use environment-based configuration
  - Support docker network URLs
  - Provide environment config at build time

### 4. **No JWT Refresh Token Mechanism** ⚠️ MEDIUM PRIORITY
- **Problem**: JWT tokens don't refresh; users stuck with one token
- **Impact**: Long sessions fail; security risk
- **Solution**:
  - Add refresh token endpoint
  - Store refresh tokens in Redis
  - Rotate tokens on expiration

### 5. **Basic Rate Limiting** ⚠️ MEDIUM PRIORITY
- **Problem**: Rate limit is 20 requests/minute; hardcoded
- **Impact**: Unfair for legitimate users; easy to abuse
- **Solution**:
  - Make configurable via environment
  - Use different limits for different endpoints
  - Implement sliding window rate limiting

### 6. **SSR CORS Issues** ⚠️ MEDIUM PRIORITY
- **Problem**: Server-side rendering makes HTTP calls to `localhost:8001`
- **Impact**: SSR fails; API calls only work in browser
- **Solution**:
  - Use internal docker network URL for SSR
  - Proxy API calls from frontend server
  - Different URLs for client vs server

### 7. **No Pagination for File Lists** ⚠️ LOW PRIORITY
- **Problem**: Returns all files at once; doesn't scale
- **Impact**: Performance degrades with hundreds of files
- **Solution**:
  - Add `limit` & `offset` parameters
  - Implement cursor-based pagination
  - Sort by `uploaded_at DESC`

### 8. **Large File Upload Handling** ⚠️ MEDIUM PRIORITY
- **Problem**: No file size validation; no progress tracking
- **Impact**: Server crashes on huge files; poor UX
- **Solution**:
  - Add max file size configuration
  - Implement chunked upload
  - Add progress callbacks to frontend

### 9. **No Data Validation for Uploads** ⚠️ MEDIUM PRIORITY
- **Problem**: Accepts any file; doesn't validate content
- **Impact**: Processing fails; creates orphaned DB records
- **Solution**:
  - Validate MIME types
  - Scan for malware
  - Check file integrity

### 10. **Missing Error Handling in Chat Streaming** ⚠️ MEDIUM PRIORITY
- **Problem**: OpenAI API errors not properly caught; incomplete streams
- **Impact**: Frozen UI; confusing error messages
- **Solution**:
  - Add try-catch in `stream_answer()`
  - Send error events in SSE stream
  - Display user-friendly error messages

### 11. **No Audit Logging** ⚠️ LOW PRIORITY
- **Problem**: No tracking of who accessed what and when
- **Impact**: Security blind spot; can't investigate issues
- **Solution**:
  - Log all file uploads/deletions
  - Log chat queries
  - Store in database with timestamps

### 12. **Session Management Not Implemented** ⚠️ LOW PRIORITY
- **Problem**: Chat sessions created but not cleaned up
- **Impact**: Database grows unbounded
- **Solution**:
  - Add session expiration logic
  - Archive/delete old sessions
  - Implement session cleanup job

### 13. **No Input Validation in Chat Questions** ⚠️ MEDIUM PRIORITY
- **Problem**: Accepts any string; no length limits
- **Impact**: Prompt injection attacks; excessive API costs
- **Solution**:
  - Validate question length (max 2000 chars)
  - Sanitize inputs
  - Rate-limit by query length

### 14. **Vector Search Index Not Optimized** ⚠️ LOW PRIORITY
- **Problem**: Basic FAISS CPU index; no re-ranking
- **Impact**: Slow searches; irrelevant results
- **Solution**:
  - Use `IndexFlatL2` for accuracy
  - Or `IVFFlat` for speed/scale
  - Add BM25 re-ranking

### 15. **Missing Database Transactions** ⚠️ MEDIUM PRIORITY
- **Problem**: No transactions for multi-step operations
- **Impact**: Partial uploads/deletions; data inconsistency
- **Solution**:
  - Wrap operations in database transactions
  - Rollback on failure
  - Atomic file + embedding creation

---

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose
- Python 3.10+ (for local development)
- Node.js 20+ (for local development)
- OpenAI API key

### Setup

#### Using Docker (Recommended)
```bash
cd documind-ai
docker-compose up --build
```
- Backend: http://localhost:8001
- Frontend: http://localhost:4200
- API Docs: http://localhost:8001/docs

#### Local Development (Backend)
```bash
cd backend
pip install -r requirements.txt
export DATABASE_URL=postgresql://documind:documind123@localhost:5432/documinddb
export REDIS_URL=redis://localhost:6380/0
export OPENAI_API_KEY=sk-...
python -m uvicorn app.main:app --reload
```

#### Local Development (Frontend)
```bash
cd frontend
npm install
npm start
```

---

## 📊 Database Schema

```
users
├── id (PK)
├── email (UNIQUE)
├── hashed_password
└── created_at

files
├── id (PK)
├── user_id (FK → users)
├── filename
├── file_type (pdf|audio|video)
├── file_path
└── uploaded_at

transcript_segments (for audio/video)
├── id (PK)
├── file_id (FK → files)
├── text
├── start_seconds
├── end_seconds
└── segment_index

chat_sessions
├── id (PK)
├── user_id (FK → users)
└── created_at

chat_messages
├── id (PK)
├── session_id (FK → chat_sessions)
├── file_id (FK → files)
├── role (user|assistant)
├── content
├── timestamp_ref (for audio)
└── created_at
```

---

## 🔐 Security Checklist

- ✅ JWT authentication
- ✅ Password hashing (bcrypt)
- ✅ CORS configured
- ⚠️ TODO: SQL injection prevention (SQLAlchemy handles this)
- ⚠️ TODO: Rate limiting (basic version exists)
- ⚠️ TODO: File upload validation
- ⚠️ TODO: HTTPS enforcement
- ⚠️ TODO: Secrets management (use Azure Key Vault in production)
- ⚠️ TODO: API key rotation

---

## 📈 Performance Metrics

| Metric | Target | Current |
|--------|--------|---------|
| **Chat response latency** | <3s | ~5-10s* |
| **File upload** | <10s | Depends on size |
| **Vector search** | <200ms | Depends on index size |
| **API throughput** | 100 req/s | ~10 req/s (needs testing) |

*Includes OpenAI API latency

---

## 🎯 Next Steps (Priority Order)

1. Fix vector store persistence
2. Implement file deletion + embedding cleanup
3. Fix SSR API URL configuration
4. Add JWT refresh token mechanism
5. Implement proper error handling
6. Add audit logging
7. Optimize vector search
8. Scale to production deployment
