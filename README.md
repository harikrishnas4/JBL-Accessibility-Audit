# JBL WCAG Audit Monorepo

Initial local-first monorepo scaffold for the JBL WCAG audit system.

## Repository Layout

- `apps/api` - FastAPI backend foundation
- `workers/docproc` - Python document processing worker scaffold
- `workers/browser` - Node.js + TypeScript browser worker scaffold
- `packages/contracts` - shared TypeScript contract scaffold
- `infra/docker` - local Docker infrastructure
- `docs` - project documentation
- `var/evidence` - local evidence output
- `var/reports` - local report output

## Prerequisites

- Python 3.11
- Node.js 24+
- Docker Desktop

## Start PostgreSQL

```powershell
cd "C:\Users\harikrishnam\Desktop\JBL accessibilty"
docker compose -f infra/docker/docker-compose.yml up -d postgres
```

## Run The API Locally

```powershell
cd "C:\Users\harikrishnam\Desktop\JBL accessibilty\apps\api"
C:\Users\harikrishnam\AppData\Local\Programs\Python\Python311\python.exe -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .[dev]
Copy-Item ..\..\.env.example ..\..\.env -Force
.\.venv\Scripts\python.exe -m uvicorn jbl_audit_api.main:app --app-dir src --host 127.0.0.1 --port 8000 --reload
```

Health check:

```text
GET http://127.0.0.1:8000/health
```

## Run Tests

API tests:

```powershell
cd "C:\Users\harikrishnam\Desktop\JBL accessibilty\apps\api"
.\.venv\Scripts\python.exe -m pytest -q
```

TypeScript scaffold checks:

```powershell
cd "C:\Users\harikrishnam\Desktop\JBL accessibilty"
npm.cmd install
npm.cmd run typecheck
```
