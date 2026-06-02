# EduAgent

<div align="center">

**AI-powered educational platform for creating interactive learning experiences**

[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.7+-blue.svg)](https://www.typescriptlang.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.117+-green.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-19-blue.svg)](https://react.dev/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Language: English](https://img.shields.io/badge/Language-English-blue.svg)](README.md)
[![Jazyk: Čeština](https://img.shields.io/badge/Jazyk-Čeština-lightgrey.svg)](README.cs.md)

[Features](#-features) • [Quick Start](#-quick-start) • [Documentation](#-documentation) • [Contributing](#-contributing)

</div>

---

EduAgent is a cutting-edge, AI-powered educational platform designed to transform how you learn. By combining advanced RAG (Retrieval-Augmented Generation) with proactive AI agents powered by **LangGraph**, EduAgent turns static documents into a dynamic, personalized tutor. Upload your course materials and experience a new way of studying with automatically generated quizzes, flashcards, mind maps, and a **Personalized Study Plan** that adapts to your unique learning pace using principles of **Active Recall** and **Adaptive Learning**.

## Table of Contents

- [Features](#-features)
- [Tech Stack](#-tech-stack)
- [Pilot Evaluation](#-pilot-evaluation)
- [Prerequisites](#-prerequisites)
- [Quick Start](#-quick-start)
- [Installation](#-installation)
- [Configuration](#-configuration)
- [Project Structure](#-project-structure)
- [Development](#-development)
- [API Documentation](#-api-documentation)
- [Roadmap](#-roadmap)
- [Documentation](#-documentation)
- [Contributing](#-contributing)
- [License](#-license)
- [Support](#-support)

## ✨ Features

- **📂 Project-Based Learning** - Organize courses into focused projects containing all your documents, chats, and AI-generated study aids.
- **🧠 Personalized Study Plans** - AI identifies your weak spots based on performance (focusing on topics where success is < 70%) and generates a custom tailored curriculum to help you master the material.
- **🤖 Proactive AI Tutor (LangGraph)** - Chat with an intelligent agent that uses a **ReAct pattern** to proactively generate quizzes, flashcards, and notes during your conversation.
- **📄 Smart Document Processing** - Drag-and-drop PDF, DOCX, TXT, and RTF files. Powered by **Azure Content Understanding** for robust text extraction and semantic segmentation.
- **🔍 Semantic Search & RAG** - Ask questions grounded in your specific materials. Uses **pgvector** for high-precision retrieval with source citations.
- **📝 Automated Quizzes** - Generate multiple-choice quizzes from any document. The system grades you, explains answers, and tracks your progress.
- **🎴 Flashcards** - Turn dense text into flashcards instantly. Perfect for memorizing definitions and key concepts using active recall.
- **🗺️ Interactive Mind Maps** - Visualize connections between topics with AI-generated mind maps that help you understand the bigger picture.
- **🔐 Enterprise-Grade Security** - Built with Supabase Auth, Azure Key Vault for infrastructure secret management, and Azure usage limits to keep your data safe and costs controlled.

## 🏗️ Tech Stack

### Backend

- **[FastAPI](https://fastapi.tiangolo.com/)** - Modern, fast Python web framework
- **[LangGraph](https://www.langchain.com/langgraph)** - Orchestration of autonomous AI agents with tool-calling capabilities
- **[PostgreSQL](https://www.postgresql.org/)** - Relational database with Alembic migrations and **pgvector** extension
- **[Azure OpenAI](https://azure.microsoft.com/en-us/products/ai-services/openai-service)** - LLM capabilities (GPT-4o, text-embedding-3-large)
- **[Azure Content Understanding](https://azure.microsoft.com/en-us/products/ai-services/document-intelligence)** - Document processing and text extraction
- **[Azure Blob Storage](https://azure.microsoft.com/en-us/products/storage/blobs)** - File storage
- **[Azure Key Vault](https://azure.microsoft.com/en-us/products/key-vault)** - Infrastructure secret management
- **[Supabase](https://supabase.com/)** - Authentication and authorization

### Frontend

- **[React 19](https://react.dev/)** - UI library
- **[TypeScript](https://www.typescriptlang.org/)** - Type safety
- **[Vite](https://vitejs.dev/)** - Build tool and dev server
- **[TanStack Router](https://tanstack.com/router)** - Type-safe routing
- **[Effect Atom](https://github.com/tim-smart/effect-atom)** - State management and data fetching
- **[TailwindCSS](https://tailwindcss.com/)** - Utility-first CSS framework
- **[Radix UI](https://www.radix-ui.com/)** - Accessible component primitives

## 📊 Pilot Evaluation

EduAgent has been validated through a pilot study with 15 test queries across various document types:

- **93% Retrieval Success**: High precision in finding relevant context.
- **0% Hallucinations**: Strict grounding in user-provided documents.
- **< 150ms Latency**: Efficient vector search performance in PostgreSQL.

## 📋 Prerequisites

Before you begin, ensure you have the following installed:

- **Python 3.12+** - [Download Python](https://www.python.org/downloads/)
- **Node.js 18+** - [Download Node.js](https://nodejs.org/)
- **npm** - included with Node.js
- **Docker & Docker Compose** - [Install Docker](https://docs.docker.com/get-docker/)
- **Terraform** - [Install Terraform](https://developer.hashicorp.com/terraform/install)
- **Azure and Supabase** - Provisioned via Terraform:
  - Terraform modules will set up:
    - **Azure AI Foundry**: Hub, Project, and Model Deployments (GPT-4o, text-embedding-3-small)
    - **Azure Storage**: Account with Blob containers and Tasks queue
    - **Azure Key Vault**: Secure secret management with RBAC
    - **Azure Container Registry**: Private registry for container images
    - **Azure Container Apps**: Serverless hosting for API and Worker services
    - **Azure App Service**: Linux-based hosting for the Web frontend
    - **Azure Monitor**: Log Analytics and Application Insights for observability
    - **Supabase**: Managed project with Database and Auth configured
  - See [infrastructure documentation](docs/AZURE_DEPLOYMENT.md) for setup instructions

## 🚀 Quick Start

Get EduAgent running locally using Docker for the backend and Vite for the frontend:

```bash
# Clone the repository
git clone https://github.com/StudentTraineeCenter/edu-agent.git
cd edu-agent

# Start backend stack (API, worker, Postgres, Azurite)
docker-compose up --build api worker db azurite

# In a separate terminal, run DB migrations (one-time)
# Make sure DATABASE_URL is set correctly for your local Postgres
export DATABASE_URL="postgresql+psycopg2://postgres:postgres@localhost:5432/postgres"
alembic upgrade head

# In a new terminal, start the web frontend
cd src/edu-web
npm install
npm start
```

Visit `http://localhost:3000` for the web app and `http://localhost:8000` for the API.

## 📦 Installation

### Backend Setup (API + Worker)

The Python services use a **uv workspace** with `pyproject.toml` + `uv.lock`.

```bash
cd edu-agent

# Install uv if you don't have it yet (see https://docs.astral.sh/uv/)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install all workspace dependencies (api, worker, shared)
uv sync

# Run database migrations (DATABASE_URL must be set)
export DATABASE_URL="postgresql+psycopg2://postgres:postgres@localhost:5432/postgres"
alembic upgrade head

# Start API locally (without Docker)
cd src/edu-api
uv run python main.py

# Optional: in another terminal, start the worker locally
cd src/edu-worker
uv run python main.py
```

### Frontend Setup

```bash
cd src/edu-web

# Install dependencies
npm install

# Generate TypeScript types from OpenAPI schema (optional)
npm run gen:client
```

## ⚙️ Configuration

### Backend Environment Variables

You can configure the backend either via **Azure Key Vault** (recommended for production) or via local environment variables / `.env` files (recommended for local dev).

```env
# Azure Key Vault (production)
AZURE_KEY_VAULT_URI=

# Usage Limits (optional, defaults shown)
MAX_DOCUMENT_UPLOADS_PER_DAY=5
MAX_QUIZ_GENERATIONS_PER_DAY=10
MAX_FLASHCARD_GENERATIONS_PER_DAY=10
MAX_CHAT_MESSAGES_PER_DAY=50
```

For local development, you can skip Key Vault and set individual environment variables directly:

```env
# Azure Key Vault (local)
AZURE_KEY_VAULT_URI=

# Usage Limits (optional, defaults shown)
MAX_DOCUMENT_UPLOADS_PER_DAY=5
MAX_QUIZ_GENERATIONS_PER_DAY=10
MAX_FLASHCARD_GENERATIONS_PER_DAY=10
MAX_CHAT_MESSAGES_PER_DAY=50
```

**Note:** The backend uses `python-dotenv`, so `.env` files at the project root work fine for local dev. See [Local Development Guide](./docs/LOCAL_DEVELOPMENT.md) for the full list and details.

### Frontend Environment Variables

Create a `.env` file in the `src/edu-web/` directory:

```env
VITE_SERVER_URL=http://localhost:8000
VITE_SUPABASE_URL=
VITE_SUPABASE_ANON_KEY=
```

For detailed configuration instructions, see the [Local Development Guide](./docs/LOCAL_DEVELOPMENT.md).

## 📁 Project Structure

```
edu-agent/
├── src/
│   ├── edu-api/            # FastAPI backend (public API)
│   ├── edu-worker/         # Background worker (queue/AI processing)
│   ├── edu-web/            # React frontend (Vite + TanStack)
│   ├── eduagent-vibecode/  # Vibecoded UI
│   └── shared/
│       ├── ai/             # Shared AI / agent logic and utilities
│       ├── core/           # Shared core logic (helpers, utils, error handling)
│       ├── db/             # Shared DB models, schemas, migrations
│       └── queue/          # Shared queue and message types
├── deploy/
│   └── azure/              # Azure Terraform + ACR build tooling
├── docs/                   # Documentation (features, local dev, privacy, etc.)
├── alembic.ini             # Alembic config pointing at src/shared/db/src/edu_db/alembic
├── docker-compose.yaml     # Local stack (api, worker, db, azurite)
├── pyproject.toml          # uv workspace definition
├── uv.lock                 # Locked dependency graph
└── ruff.toml               # Backend linting/formatting configuration
```

## 🔧 Development

### Backend Development

```bash
# From repo root

# Create a new database migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Run API with uv (auto-respects workspace venv)
cd src/edu-api
uv run python main.py
```

### Frontend Development

```bash
cd src/edu-web

# Start development server
npm start

# Build for production
npm run build

# Run linter
npm run lint

# Format code
npm run format

# Run type checking
npm run type-check

# Generate TypeScript types from OpenAPI schema
npm run gen:client
```

### Code Quality

Both backend and frontend use linting and formatting tools:

- **Backend**: Ruff (configured in `ruff.toml`, run via `ruff format .` and `ruff check .`)
- **Frontend**: ESLint + Prettier (configured in `src/edu-web/`)

## 📚 API Documentation

Once the backend server is running, API documentation is available at:

- **Scalar UI (OpenAPI docs)**: `http://localhost:8000/`
- **Health Check**: `http://localhost:8000/health`
- **OpenAPI Schema**: `http://localhost:8000/openapi.json`

## 🗺️ Roadmap

- [ ] **Audio/Video Support**: Automatic transcription and analysis of lectures.
- [ ] **Advanced Spaced Repetition**: Sophisticated algorithms for long-term memory retention.
- [ ] **AI-Generated Presentations**: Transform project materials into structured slides.
- [ ] **Collaborative Projects**: Study with peers in shared AI-powered environments.

## 📖 Documentation

Comprehensive documentation is available in the `docs/` directory:

- **[Features](./docs/FEATURES.md)** - Detailed overview of platform features and capabilities
- **[Local Development](./docs/LOCAL_DEVELOPMENT.md)** - Complete setup and development guide (Docker + uv workspace)
- **[Azure Deployment](./docs/AZURE_DEPLOYMENT.md)** - Production deployment instructions for Azure (using `deploy/azure`)

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Guidelines

- Follow the existing code style and conventions
- Write clear commit messages
- Add tests for new features when possible
- Update documentation as needed
- Ensure all linting checks pass

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 💬 Support

- **Documentation**: Check the [docs](./docs/) directory
- **Issues**: [GitHub Issues](https://github.com/StudentTraineeCenter/edu-agent/issues)

## 🙏 Acknowledgments

- Built with [uv](https://github.com/astral-sh/uv), [FastAPI](https://fastapi.tiangolo.com/), and [React](https://react.dev/)
- Powered by [Azure AI Services](https://azure.microsoft.com/en-us/products/ai-services)
- UI built with [Radix UI](https://www.radix-ui.com/) and [shadcn/ui](https://ui.shadcn.com/)

---

<div align="center">

Made with ❤️ for students and educators

[⬆ Back to Top](#eduagent)

</div>
