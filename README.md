# NanoTest - AI-Driven Mobile Automation Testing Platform

An enterprise-grade mobile automation testing platform with AI-powered analysis, visual regression detection, and intelligent test orchestration.

## 🚀 Features

- **Test Case DSL**: Define test cases using a simple, declarative DSL
- **Visual Flow Builder**: Design test flows with drag-and-drop DAG editor
- **AI-Powered Analysis**: Automatic screenshot analysis for anomaly detection
- **Multi-Platform Support**: iOS and Android testing via Appium
- **Risk Scoring**: AI-calculated risk scores for test runs
- **Run Comparison**: Visual diff between test runs
- **Multi-Tenant**: Full tenant isolation with RBAC

## 📋 Prerequisites

- Python 3.11+
- Node.js 18+
- Docker & Docker Compose
- PostgreSQL 15+
- Redis 7+
- Aliyun OSS (object storage)

## 🛠️ Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/your-org/nanotest.git
cd nanotest
```

### 2. Start Infrastructure with Docker Compose

```bash
docker-compose up -d postgres redis
```

### 3. Backend Setup

```bash
cd apps/backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env
# Edit .env with your configuration

# Run database migrations
alembic upgrade head

# Start the backend
uvicorn app.main:app --reload
```

### 4. Frontend Setup

```bash
cd apps/web

# Install dependencies
npm install

# Start development server
npm run dev
```

### 5. Start Celery Workers

```bash
cd apps/backend

# Execution worker
celery -A app.tasks.celery_app worker -Q execution -l info

# Analysis worker (in another terminal)
celery -A app.tasks.celery_app worker -Q analysis -l info
```

## 🐳 Full Docker Deployment

```bash
docker-compose up -d
```

This starts all services:
- Backend API: http://localhost:8000
- Frontend: http://localhost:3000
- PostgreSQL: localhost:5432
- Redis: localhost:6379

## 📖 API Documentation

Once the backend is running, access the API docs at:
- Swagger UI: http://localhost:8000/api/v1/docs
- ReDoc: http://localhost:8000/api/v1/redoc

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Frontend (React)                      │
│                   Vite + TailwindCSS + ReactFlow            │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     Backend API (FastAPI)                    │
│              REST API + WebSocket + JWT Auth                │
└─────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│  PostgreSQL   │    │     Redis     │    │  Aliyun OSS   │
│   (Data)      │    │ (Cache/Queue) │    │  (Storage)    │
└───────────────┘    └───────────────┘    └───────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Celery Workers                            │
│         Execution Queue │ Analysis Queue                    │
└─────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│ Appium Server │    │   OpenAI API  │    │ Device Farm   │
│   (Mobile)    │    │    (AI/LLM)   │    │  (Devices)    │
└───────────────┘    └───────────────┘    └───────────────┘
```

## 📁 Project Structure

```
nanotest/
├── apps/
│   ├── backend/          # FastAPI backend
│   │   ├── app/
│   │   │   ├── api/      # API endpoints
│   │   │   ├── core/     # Config, DB, Security
│   │   │   ├── domain/   # SQLAlchemy models
│   │   │   ├── integrations/  # External services
│   │   │   ├── schemas/  # Pydantic schemas
│   │   │   └── tasks/    # Celery tasks
│   │   └── migrations/   # Alembic migrations
│   ├── web/              # React frontend
│   └── worker/           # Worker utilities
├── packages/             # Shared packages
│   ├── dsl-engine/       # DSL parser/executor
│   ├── flow-compiler/    # Flow graph compiler
│   └── ai-adapter-sdk/   # AI integration SDK
├── deploy/
│   ├── k8s/              # Kubernetes manifests
│   └── observability/    # Monitoring configs
└── docs/                 # Documentation
```

## 🔧 Configuration

Key environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | - |
| `REDIS_URL` | Redis connection string | - |
| `SECRET_KEY` | JWT signing key | - |
| `OPENAI_API_KEY` | OpenAI API key for AI analysis | - |
| `OSS_STS_TOKEN_URL` | Aliyun OSS STS token endpoint | - |
| `APPIUM_SERVER_URL` | Appium server URL | http://localhost:4723 |

## 📝 Test Case DSL Example

```yaml
name: Login Flow Test
steps:
  - action: launch_app
    params:
      app_id: com.example.app
  - action: input
    target: accessibility_id:username_field
    value: testuser@example.com
  - action: input
    target: accessibility_id:password_field
    value: password123
  - action: tap
    target: accessibility_id:login_button
  - action: assert
    target: accessibility_id:welcome_message
    params:
      condition: exists
      timeout: 10
```

## 🧪 Running Tests

```bash
cd apps/backend
pytest --cov=app tests/
```

## 📄 License

MIT License - see LICENSE file for details.
