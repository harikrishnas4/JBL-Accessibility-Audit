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

## Prepare Browser Worker Dependencies

```powershell
cd "C:\Users\harikrishnam\Desktop\JBL accessibilty"
npm.cmd install
npx playwright install chromium
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
npm.cmd run typecheck
```

Browser worker tests:

```powershell
cd "C:\Users\harikrishnam\Desktop\JBL accessibilty"
npm.cmd run test --workspace @jbl/browser-worker
```

## Run Lint And Quality Checks

TypeScript lint:

```powershell
cd "C:\Users\harikrishnam\Desktop\JBL accessibilty"
npm.cmd run lint
```

TypeScript typecheck:

```powershell
cd "C:\Users\harikrishnam\Desktop\JBL accessibilty"
npm.cmd run typecheck
```

API lint:

```powershell
cd "C:\Users\harikrishnam\Desktop\JBL accessibilty\apps\api"
.\.venv\Scripts\python.exe -m ruff check src tests
```

Docproc lint and tests:

```powershell
cd "C:\Users\harikrishnam\Desktop\JBL accessibilty\workers\docproc"
.\.venv\Scripts\python.exe -m pip install -e .[dev]
.\.venv\Scripts\python.exe -m ruff check src tests
.\.venv\Scripts\python.exe -m pytest -q tests
```

GitHub Actions CI runs on every push to `main` and every pull request. It enforces:

- TypeScript lint
- TypeScript typecheck
- browser worker tests
- docproc lint and tests
- API lint and tests
- Playwright Chromium install for the API real-browser smoke path

Real browser worker smoke test:

```powershell
cd "C:\Users\harikrishnam\Desktop\JBL accessibilty"
npm.cmd run build --workspace @jbl/browser-worker
npx playwright install chromium

cd "C:\Users\harikrishnam\Desktop\JBL accessibilty\apps\api"
.\.venv\Scripts\python.exe -m pytest -q tests/test_real_browser_smoke.py
```

Authenticated-session browser smoke test:

```powershell
cd "C:\Users\harikrishnam\Desktop\JBL accessibilty"
npm.cmd run build --workspace @jbl/browser-worker
npx playwright install chromium

cd "C:\Users\harikrishnam\Desktop\JBL accessibilty\apps\api"
.\.venv\Scripts\python.exe -m pytest -q tests/test_real_browser_smoke.py -k authenticated_session
```
