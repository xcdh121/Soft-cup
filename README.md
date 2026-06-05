# EduAgent

EduAgent is an AI-assisted learning platform built around project documents, chat, semantic retrieval, and generated study resources.

## Current Architecture

- File storage: local filesystem under `STORAGE_ROOT`
- Document processing: local PDF/DOCX/TXT/HTML/RTF parsing
- Task execution: in-process synchronous dispatch
- Chat / generation models: OpenAI-compatible endpoints or local model servers
- Vector search: PostgreSQL + `pgvector`
- Auth / data: Supabase + PostgreSQL

## Quick Start

```bash
docker-compose up --build api db
```

Then run migrations:

```bash
set DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/postgres
alembic upgrade head
```

Start the frontend:

```bash
cd src/edu-web
npm install
npm start
```

## Backend Config

Create a root `.env` file with values like:

```env
DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/postgres
SUPABASE_URL=
SUPABASE_JWT_SECRET=
ALLOW_DEV_AUTH_BYPASS=true

STORAGE_ROOT=./.localdata

LLM_MODEL=gpt-4o-mini
LLM_API_KEY=
LLM_BASE_URL=

EMBEDDING_MODEL=text-embedding-3-large
EMBEDDING_API_KEY=
EMBEDDING_BASE_URL=
```

`LLM_BASE_URL` and `EMBEDDING_BASE_URL` can point to self-hosted OpenAI-compatible services.

## Notes

- The old Azure deployment path has been removed from the active workspace.
- The dedicated worker process is no longer required for local-first operation.
- Some secondary docs may still describe the historical Azure architecture and should be treated as legacy notes until they are rewritten.
