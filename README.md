
# MeenMart Backend

Backend for the MeenMart online fish ordering application.

## Technology Stack

- FastAPI
- Python
- SQLAlchemy
- PostgreSQL
- Supabase
- Alembic
- Pytest

## Setup

Create and activate a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
pip install -r requirements.txt
```

Create your environment file:

```powershell
Copy-Item .env.example .env
```

Edit `.env` and configure your Supabase PostgreSQL connection.

## Run the application

```powershell
uvicorn app.main:app --reload
```

## API Documentation

http://127.0.0.1:8000/docs

## Health Checks

- `/health`
- `/health/db`

## API Base URL

`/api/v1`

## Security

Never commit `.env` or expose database credentials.
Do not deploy unfinished or unprotected write endpoints publicly.
