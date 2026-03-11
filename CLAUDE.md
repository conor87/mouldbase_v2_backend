# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Mouldbase v2 Backend — a FastAPI application for managing injection moulds, production orders, changeovers, TPM (maintenance), and scheduling. Polish-language domain (enum names, comments, some variable names).

## Running the Application

```bash
cd backend
python main.py
# OR
uvicorn main:app --host 0.0.0.0 --port 8000
```

No `requirements.txt` exists. Key dependencies: fastapi, uvicorn, sqlalchemy>=2.0, psycopg2-binary, pydantic>=2.0, python-jose[cryptography], passlib[bcrypt], python-multipart.

## Architecture

Layered FastAPI structure under `backend/`:

- **`main.py`** — Entry point. Registers routers, CORS, mounts static media, creates DB tables on startup.
- **`db/database.py`** — SQLAlchemy engine, `SessionLocal`, `Base`, and `db_dependency` (FastAPI dependency injection for DB sessions). PostgreSQL on `10.10.77.75:5432/mouldbase`.
- **`models/`** — SQLAlchemy ORM models (one file per domain entity).
- **`schemas/`** — Pydantic v2 schemas (`ConfigDict(from_attributes=True)`) for request/response validation.
- **`routers/`** — FastAPI routers, one per domain. Each router uses `db_dependency` and auth dependencies.
- **`app/images.py`** — Image upload utility. Stores files at `../media/YYYY/MM/DD/<uuid>.<ext>`.

## Key Routers & Prefixes

| Router | Prefix | Domain |
|---|---|---|
| `auth.py` | `/auth` | JWT auth (OAuth2 password flow) |
| `mould.py` | `/moulds` | Mould CRUD + photo uploads |
| `moulds_tpm.py` | `/moulds-tpm` | TPM maintenance records |
| `moulds_book.py` | `/moulds-book` | Mould documentation |
| `changeovers.py` | `/changeovers` | Mould changeover operations |
| `changeovers_log.py` | `/changeovers-log` | Changeover history |
| `calendar.py` | `/calendar` | Scheduling |
| `calendar_log.py` | `/calendar-log` | Calendar history |
| `production.py` | `/production` | Orders, tasks, operations, logs |
| `current_sv.py` | `/current_sv` | Raw SQL query for current SV data |

## Authentication & Authorization

- JWT tokens via `python-jose`, passwords hashed with `passlib[bcrypt]`.
- `SECRET_KEY` and `ALGORITHM` defined in `routers/auth.py`.
- User roles: `user`, `admin`, `admindn`, `superadmin`.
- `RoleChecker` class for endpoint-level role guards (used as FastAPI dependencies).
- See `backend/README_AUTH.md` for auth endpoint documentation.

## Domain Enums (Polish)

- **PobytFormy** (mould location): PRODUKCJA, NARZEDZIOWNIA, KOOPERACJA, MAGAZYN_FORM
- **StanFormy** (mould status): PRODUKCYJNA, TPM, AWARIA, MODYFIKACJA, PRZEZBRAJANA, W_PRZEGLADZIE
- **Statusy** (TPM status): OTWARTY, W_TRAKCIE_REALIZACJI, ZAMKNIĘTY, ODRZUCONY

## Conventions

- Each domain has a matching trio: `models/<name>.py`, `schemas/<name>.py`, `routers/<name>.py`.
- Database tables are auto-created via `Base.metadata.create_all(bind=engine)` at startup.
- Media files served as static mounts at `/media`.
- CORS configured for localhost (3000, 4173, 5173) and internal network `10.10.77.75`.
