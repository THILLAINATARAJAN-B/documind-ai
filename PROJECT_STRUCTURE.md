# DocuMind AI - Project Structure

## Overview
A full-stack application with FastAPI backend, PostgreSQL database, Redis cache, and Angular frontend with Server-Side Rendering.

---

## Project Root
```
documind-ai/
├── docker-compose.yml          # Docker Compose configuration for all services
├── backend/                    # FastAPI backend application
└── frontend/                   # Angular frontend application
```

---

## Backend (`/backend`)
FastAPI-based REST API with async support, database migrations, and comprehensive testing.

```
backend/
├── Dockerfile                  # Docker image for backend service
├── requirements.txt            # Python dependencies
├── alembic.ini                 # Alembic database migration configuration
├── .env                        # Environment variables (local development)
├── .coverage                   # Coverage report file
│
├── alembic/                    # Database migrations
│   └── env.py                  # Alembic environment configuration
│
├── app/                        # Main application package
│   ├── main.py                 # FastAPI app entry point, route mounting
│   │
│   ├── core/                   # Core configuration and utilities
│   │   ├── __init__.py
│   │   ├── config.py           # Settings and configuration management
│   │   ├── database.py         # SQLAlchemy database setup
│   │   ├── redis_client.py     # Redis connection and utilities
│   │   └── security.py         # JWT, password hashing, authentication
│   │
│   ├── models/                 # SQLAlchemy ORM models
│   │   ├── __init__.py
│   │   └── models.py           # User, Chat, Document models
│   │
│   ├── routers/                # API route handlers (FastAPI routers)
│   │   ├── __init__.py
│   │   ├── auth.py             # Authentication endpoints (login, register, logout)
│   │   ├── chat.py             # Chat endpoints (message, history)
│   │   ├── upload.py           # File upload endpoints (PDF, audio)
│   │   ├── deps.py             # Dependency injection functions
│   │   └── deps.py             # Common dependencies (auth checks, DB sessions)
│   │
│   ├── schemas/                # Pydantic models for request/response validation
│   │   ├── __init__.py
│   │   ├── auth.py             # LoginRequest, RegisterRequest, TokenResponse
│   │   ├── chat.py             # ChatMessage, ChatRequest schemas
│   │   ├── file.py             # FileUpload, FileResponse schemas
│   │
│   ├── services/               # Business logic layer
│   │   ├── __init__.py
│   │   ├── auth.py             # Authentication logic (verify, issue tokens)
│   │   ├── chat_engine.py      # Chat processing and message handling
│   │   ├── embeddings.py       # Vector embeddings and RAG logic
│   │   ├── pdf_processor.py    # PDF parsing and text extraction
│   │   ├── audio_processor.py  # Audio transcription and processing
│   │
│   └── uploads/                # Directory for uploaded files (PDFs, audio)
│
├── tests/                      # Test suite
│   ├── __init__.py
│   ├── conftest.py             # Pytest configuration, fixtures
│   ├── test_auth.py            # Authentication endpoint tests
│   ├── test_chat.py            # Chat endpoint tests
│   ├── test_upload.py          # File upload tests
│   └── test_services.py        # Business logic unit tests
```

### Backend Key Features
- **Authentication**: JWT-based auth with secure password hashing
- **Database**: SQLAlchemy ORM with PostgreSQL and Alembic migrations
- **Caching**: Redis for session management and caching
- **File Processing**: PDF parsing and audio transcription
- **RAG System**: Vector embeddings for semantic search
- **Testing**: Pytest with coverage reporting
- **API Documentation**: Auto-generated Swagger/OpenAPI docs

---

## Frontend (`/frontend`)
Angular SSR (Server-Side Rendering) application with lazy-loaded routes and interceptors.

```
frontend/
├── Dockerfile                  # Docker image for frontend service
├── nginx.conf                  # Nginx configuration for production
├── package.json                # Node.js dependencies and scripts
├── tsconfig.json               # TypeScript compiler configuration
├── tsconfig.app.json           # TypeScript config for application
├── tsconfig.spec.json          # TypeScript config for tests
├── angular.json                # Angular CLI configuration
├── README.md                   # Frontend documentation
│
├── public/                     # Static assets
│
├── src/                        # Source code
│   ├── index.html              # Main HTML file
│   ├── main.ts                 # Application bootstrap (browser)
│   ├── main.server.ts          # Server-side rendering bootstrap
│   ├── server.ts               # Express server for SSR
│   ├── styles.scss             # Global application styles
│   │
│   └── app/                    # Angular application module
│       ├── app.ts              # Root component
│       ├── app.html            # Root component template
│       ├── app.scss            # Root component styles
│       ├── app.spec.ts         # Root component tests
│       ├── app.component.ts    # Main app component logic
│       ├── app.component.html  # Main app template
│       ├── app.component.scss  # Main app styles
│       ├── app.component.spec.ts # Main app tests
│       │
│       ├── app.routes.ts       # Client-side routing configuration
│       ├── app.routes.server.ts # Server-side routing configuration
│       ├── app.config.ts       # Client-side app configuration
│       ├── app.config.server.ts # Server-side app configuration
│       │
│       ├── core/               # Core services and guards
│       │   ├── guards/
│       │   │   └── auth.guard.ts      # Route protection, auth checks
│       │   │
│       │   ├── interceptors/
│       │   │   └── auth.interceptor.ts # JWT token injection, error handling
│       │   │
│       │   └── services/
│       │       ├── api.service.ts     # HTTP API communication
│       │       ├── auth.service.ts    # Authentication logic
│       │       └── sse.service.ts     # Server-Sent Events (real-time)
│       │
│       └── pages/              # Feature pages/components
│           ├── login/          # Login page
│           │   ├── login.component.ts
│           │   ├── login.component.html
│           │   └── login.component.scss
│           │
│           ├── register/       # Registration page
│           │   ├── register.component.ts
│           │   ├── register.component.html
│           │   └── register.component.scss
│           │
│           ├── chat/           # Chat page
│           │   ├── chat.component.ts
│           │   ├── chat.component.html
│           │   └── chat.component.scss
│           │
│           └── dashboard/      # Dashboard page
│               ├── dashboard.component.ts
│               ├── dashboard.component.html
│               └── dashboard.component.scss
```

### Frontend Key Features
- **Server-Side Rendering**: Pre-rendered pages for better SEO and performance
- **Standalone Components**: Modern Angular with standalone API (no modules)
- **Route Protection**: Auth guards prevent unauthorized access
- **JWT Handling**: Auth interceptor automatically attaches tokens
- **Real-time Updates**: Server-Sent Events for live message streaming
- **Responsive Design**: SCSS-based styling system
- **Lazy Loading**: Routes loaded on-demand for faster initial load

---

## Docker & Deployment

### docker-compose.yml
Orchestrates multiple services:
- **Backend**: FastAPI application on port 8000
- **Frontend**: Angular SSR application on port 4200
- **PostgreSQL**: Database (port 5432)
- **Redis**: Cache layer (port 6379)
- **Nginx**: Reverse proxy (port 80, 443)

---

## Key Technologies

### Backend Stack
- **Framework**: FastAPI (async Python web framework)
- **Database**: PostgreSQL with SQLAlchemy ORM
- **Migrations**: Alembic
- **Caching**: Redis
- **Auth**: JWT tokens, bcrypt password hashing
- **Testing**: Pytest, pytest-cov
- **File Processing**: PyPDF2, librosa, pydub
- **ML/AI**: LangChain, OpenAI API

### Frontend Stack
- **Framework**: Angular 18+ (latest)
- **Rendering**: Server-Side Rendering (Angular Universal)
- **Language**: TypeScript
- **Styling**: SCSS
- **HTTP Client**: HttpClient (built-in)
- **State Management**: Services with RxJS
- **Testing**: Jasmine/Karma
- **Build Tool**: esbuild (via Angular CLI)

---

## Development Workflow

### Backend
```bash
cd backend
pip install -r requirements.txt
python -m alembic upgrade head  # Run migrations
python -m pytest tests/ -v      # Run tests
python -m uvicorn app.main:app --reload  # Start dev server
```

### Frontend
```bash
cd frontend
npm install
npm start              # Development server
npm run build         # Production build
npm run build:ssr     # Build with SSR
npm test              # Run tests
```

### Docker
```bash
docker-compose up --build    # Start all services
docker-compose down          # Stop all services
```

---

## Environment Files

### Backend (.env)
```
DATABASE_URL=postgresql://user:password@db:5432/documind
REDIS_URL=redis://redis:6379
JWT_SECRET=your-secret-key
OPENAI_API_KEY=sk-...
```

### Frontend (environment.ts)
```typescript
export const environment = {
  apiUrl: 'http://localhost:8000',
  production: false
};
```

---

## Project Status

This is a modern, production-ready full-stack application with:
✅ Type-safe development (Python/TypeScript)
✅ Comprehensive testing (backend + frontend)
✅ Containerized deployment (Docker)
✅ Real-time capabilities (SSE, WebSockets ready)
✅ Security best practices (JWT, CORS, password hashing)
✅ Scalable architecture (microservices-ready)
