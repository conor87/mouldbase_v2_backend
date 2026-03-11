# Mouldbase v2 Backend - Project Overview

## Purpose
FastAPI backend for managing injection moulds, production orders, changeovers, TPM (maintenance), and scheduling. Polish-language domain.

## Tech Stack
- Python 3.11+, FastAPI, SQLAlchemy 2.0, Pydantic v2
- PostgreSQL (10.10.77.75:5432/mouldbase)
- JWT auth (python-jose), passlib[bcrypt]
- No requirements.txt

## Structure
```
backend/
├── main.py          # Entry point, router registration, CORS, static mounts
├── db/database.py   # SQLAlchemy engine, SessionLocal, Base, db_dependency
├── models/          # ORM models (one per domain)
├── schemas/         # Pydantic v2 schemas (from_attributes=True)
├── routers/         # FastAPI routers (one per domain)
├── app/images.py    # Image upload utility
media/               # Uploaded media files
```

## Key Routers
- auth (/auth), mould (/moulds), moulds_tpm (/moulds-tpm), moulds_book (/moulds-book)
- changeovers (/changeovers), changeovers_log (/changeovers-log)
- calendar (/calendar), calendar_log (/calendar-log)
- production (/production), current_sv (/current_sv)

## Auth
- JWT OAuth2 password flow, roles: user, admin, admindn, superadmin
- RoleChecker class for endpoint guards
