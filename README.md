# Travel ERP

Production-oriented modular monolith for a multi-agency travel business.

## Repository layout

- `backend/`: Django and Django REST Framework API
- `frontend/`: Next.js application
- `docs/`: architecture, workflows, and decision records
- `infrastructure/`: deployment and operational configuration

## Local prerequisites

- Python 3.13
- Node.js 24 and pnpm 10
- Docker Desktop

## Start infrastructure

```powershell
Copy-Item .env.example .env
docker compose up -d db redis
```

## Start the backend

```powershell
Set-Location backend
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
.\.venv\Scripts\python manage.py migrate
.\.venv\Scripts\python manage.py bootstrap_tenant --agency-name "My Agency" --agency-slug my-agency --email owner@example.com
.\.venv\Scripts\python manage.py runserver
```

## Start the frontend

```powershell
Set-Location frontend
pnpm install
pnpm dev
```

The API health check is available at `http://localhost:8000/api/v1/health/`.
