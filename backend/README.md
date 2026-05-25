# Government Person Intelligence Platform — Backend

## Stack

FastAPI, SQLAlchemy, **SQLite**, JWT, Pandas, Uvicorn

## Structure

```
backend/
├── app/
│   ├── api/          # Route handlers
│   ├── auth/         # JWT & password utilities
│   ├── core/         # Config & exceptions
│   ├── database/     # Engine, session, init
│   ├── models/       # User, Upload, Citizen
│   ├── schemas/      # Pydantic models
│   ├── services/     # Business logic
│   ├── utils/        # Shared dependencies
│   └── main.py
├── data/             # SQLite database (upis.db)
└── uploads/          # Saved CSV files
```

## Setup

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

On startup, tables are created automatically and a default officer account is seeded if missing.

**Default login:** `officer` / `officer123`

Override via environment variables: `DEFAULT_OFFICER_USERNAME`, `DEFAULT_OFFICER_PASSWORD`, `DEFAULT_OFFICER_ROLE`.

Database file: `backend/data/upis.db` (override with `DATABASE_URL`).

Manual init:

```bash
python -m app.database.init_db
```

API docs: http://127.0.0.1:8000/docs

## Endpoints

| Method | Path | Auth |
|--------|------|------|
| POST | /create-user | No |
| POST | /login | No |
| GET | /api/dashboard | Bearer JWT |
| POST | /api/upload-file | Bearer JWT |
| GET | /api/citizens | Bearer JWT |
| GET | /api/health | No |
| GET | /api/db-check | No |

### Citizens query params

`name`, `mobile`, `district`, `page`, `page_size`, `sort_by`, `sort_order`

CSV upload expects columns: `full_name`, `mobile`, `district`, `village`, `dob`.

Duplicate mobile numbers are skipped (not inserted twice).
