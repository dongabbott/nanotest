# NanoTest - AI-Driven Mobile Automation Testing Platform

An enterprise-grade mobile automation testing platform with AI-powered analysis, visual regression detection, and intelligent test orchestration.

## 🚀 Features

- **Test Case DSL**: Define test cases using a simple, declarative DSL
- **Visual Flow Builder**: Design test flows with drag-and-drop DAG editor (ReactFlow)
- **AI-Powered Analysis**: Automatic screenshot analysis for anomaly detection (Doubao / OpenAI)
- **Multi-Platform Support**: iOS and Android testing via Appium (W3C WebDriver)
- **App Package Management**: Upload APK/IPA with auto-parsing of metadata
- **Device & Session Management**: Local device scanning, remote Appium servers, Redis-backed sessions
- **Risk Scoring**: AI-calculated risk scores for test runs
- **Run Comparison**: Visual diff between test runs
- **Real-time Updates**: WebSocket push for run status changes
- **Multi-Tenant**: Full tenant isolation with RBAC

## 📋 Prerequisites

| Software | Version | Required |
|----------|---------|----------|
| Python | 3.11+ | ✅ |
| Node.js | 18+ | ✅ |
| Redis | 7+ | ⚠️ Optional for basic dev (needed for Celery / Sessions / WebSocket) |
| PostgreSQL | 15+ | ❌ Dev uses SQLite by default |

## 🛠️ Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/your-org/nanotest.git
cd nanotest
```

### 2. Backend Setup

```bash
cd apps/backend

# Create and activate virtual environment
python -m venv .venv
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# Linux/macOS:
# source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure Environment (Optional)

Create `apps/backend/.env` — all settings have sensible defaults for local dev:

```env
# SQLite is used by default — no database setup needed
# Uncomment to use PostgreSQL in production:
# DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/nanotest

# Redis (required for Celery workers, Session store, WebSocket events)
REDIS_URL=redis://localhost:6379/0

# AI/LLM — Volcengine Ark (Doubao) by default
LLM_PROVIDER=doubao
ARK_API_KEY=your-ark-api-key
ARK_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
ARK_MODEL=doubao-seed-2-0-pro-260215

# Or use OpenAI:
# LLM_PROVIDER=openai
# OPENAI_API_KEY=sk-xxx
```

### 4. Start the Backend

**Windows (recommended):**

```powershell
cd apps/backend
.\start.ps1
```

The script automatically cleans port 8000 → runs Alembic migrations → starts uvicorn with hot-reload.

**Manual:**

```bash
cd apps/backend
python -m alembic upgrade head
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir app
```

> On first launch with SQLite, the backend auto-creates all tables and a dev user: **admin@example.com / admin123**

### 5. Frontend Setup

```bash
cd apps/web
npm install
npm run dev
```

Frontend runs at http://localhost:5173.

### 6. Start Celery Workers (Optional)

Only needed for test execution and AI analysis:

```bash
cd apps/backend
celery -A app.tasks.celery_app worker -Q execution -l info

# In another terminal:
celery -A app.tasks.celery_app worker -Q analysis -l info
```

## 🔗 Access Points

| Service | URL |
|---------|-----|
| Frontend | http://localhost:5173 |
| Backend API | http://localhost:8000 |
| Swagger UI | http://localhost:8000/api/v1/docs |
| ReDoc | http://localhost:8000/api/v1/redoc |
| Health Check | http://localhost:8000/health |

## 📖 Default Credentials

| Email | Password | Role |
|-------|----------|------|
| admin@example.com | admin123 | admin |

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Frontend (React + Vite)                  │
│          TailwindCSS · ReactFlow · Monaco Editor · Zustand  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   Backend API (FastAPI)                      │
│           REST + WebSocket + JWT Auth + Pydantic v2         │
└─────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│ SQLite / PG   │    │     Redis     │    │  Aliyun OSS   │
│  (Database)   │    │(Sessions/Queue│    │  (Storage)    │
│               │    │  /Events)     │    │               │
└───────────────┘    └───────────────┘    └───────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Celery Workers                            │
│            execution queue · analysis queue                  │
└─────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│ Appium Server │    │ Doubao/OpenAI │    │ Mobile Devices│
│  (W3C WD)     │    │   (AI/LLM)    │    │ (Android/iOS) │
└───────────────┘    └───────────────┘    └───────────────┘
```

## 📁 Project Structure

```
nanotest/
├── apps/
│   ├── backend/              # FastAPI backend
│   │   ├── app/
│   │   │   ├── api/v1/       # Endpoints: auth, cases, devices, flows,
│   │   │   │                 #   packages, projects, reports, runs, websocket
│   │   │   ├── core/         # Config, database, events, security
│   │   │   ├── domain/       # SQLAlchemy models
│   │   │   ├── integrations/ # Aliyun OSS, Appium, LLM clients
│   │   │   ├── schemas/      # Pydantic request/response schemas
│   │   │   ├── services/     # Business logic layer
│   │   │   └── tasks/        # Celery tasks (execution, analysis, reports)
│   │   ├── migrations/       # Alembic database migrations
│   │   ├── scripts/          # Utility scripts (seed.py)
│   │   ├── storage/          # Local file storage (app packages)
│   │   ├── start.ps1         # Windows dev startup script
│   │   └── requirements.txt  # Python dependencies
│   ├── web/                  # React frontend (Vite + TailwindCSS)
│   │   └── src/
│   │       ├── components/   # UI components (Layout, ElementInspector, …)
│   │       ├── pages/        # Page components
│   │       ├── services/     # API client (api.ts)
│   │       └── store/        # Zustand state management
│   └── worker/               # Worker runners
│       └── runners/          # Execution engines (base, flow_runner, appium_runner)
├── packages/                 # Shared TypeScript packages
│   ├── dsl-engine/           # DSL parser/executor
│   ├── flow-compiler/        # Flow graph compiler
│   ├── ai-adapter-sdk/       # AI integration SDK
│   └── shared-types/         # Shared type definitions
├── deploy/
│   ├── k8s/                  # Kubernetes manifests
│   └── observability/        # Monitoring configs
└── docs/                     # Documentation
```

## 🔧 Configuration

Key environment variables (all have defaults for local dev):

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | Database connection string | PostgreSQL (falls back to SQLite in dev) |
| `REDIS_URL` | Redis connection string | redis://localhost:6379/0 |
| `SECRET_KEY` | JWT signing key | Dev default (**change in production**) |
| `LLM_PROVIDER` | AI provider: `openai` / `doubao` / `ark` | openai |
| `ARK_API_KEY` | Volcengine Ark (Doubao) API key | — |
| `ARK_BASE_URL` | Ark API endpoint | https://ark.cn-beijing.volces.com/api/v3 |
| `ARK_MODEL` | Ark model name | doubao-seed-2-0-pro-260215 |
| `OPENAI_API_KEY` | OpenAI API key | — |
| `APPIUM_SERVER_URL` | Appium server URL | http://localhost:4723 |
| `APP_PACKAGE_STORAGE_DIR` | Local package storage path | storage/app_packages |

> See [`USER_MANUAL.md`](USER_MANUAL.md) for the complete configuration reference.

## 📝 Test Case DSL Example

```json
{
  "name": "Login Flow Test",
  "steps": [
    {
      "action": "launch_app",
      "params": { "app_id": "com.example.app" }
    },
    {
      "action": "input",
      "target": "id=username_field",
      "locator_type": "id",
      "value": "testuser@example.com"
    },
    {
      "action": "input",
      "target": "id=password_field",
      "locator_type": "id",
      "value": "password123"
    },
    {
      "action": "tap",
      "target": "id=login_button",
      "locator_type": "id"
    },
    {
      "action": "assert",
      "target": "id=welcome_message",
      "locator_type": "id",
      "timeout": 10
    }
  ]
}
```

## 🧪 Running Tests

```bash
cd apps/backend
pytest --cov=app tests/
```

## 📄 License

MIT License — see LICENSE file for details.
