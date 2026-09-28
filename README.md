# Vouch

Vouch is a trusted rental marketplace for high-value assets, beginning with media and
creative gear in Lagos and Abuja. The product is built around verified renter identities,
platform-controlled payments, deposits, and co-signed handover evidence.

This repository contains the production API foundation. It is intentionally a modular
FastAPI application so the marketplace domain, Paystack payments, KYC, notifications,
and future WhatsApp or Telegram clients can evolve behind stable interfaces.

## Current foundation

- Versioned FastAPI API with an application factory
- Validated, environment-prefixed configuration
- Async PostgreSQL engine lifecycle with connection health checks
- Separate liveness and readiness endpoints
- Request correlation IDs and structured completion logs (honours caller-supplied `X-Request-ID`)
- Explicit CORS policy for the future web client
- Automated lint, test, and coverage checks in CI
- Seven domain tables and initial Alembic migration (migration 0001)
- Asset listing-publication state (`draft / review / active / paused / rejected`), minimum trust
  tier, and review provenance fields (migration 0002)
- Shared API error envelope with stable machine-readable codes
- Opaque cursor-based pagination helpers
- Public Lagos asset search and detail endpoints (read-only, no authentication required)

## Architecture

```text
Web client / channel adapters
            |
        /api/v1
            |
   FastAPI modular monolith
            |
 Async SQLAlchemy + PostgreSQL
```

The modular monolith is the deliberate v1 boundary: it keeps transactions and operations
simple while leaving clean seams for payments, identity, inventory, and bookings.

## Local setup

Requirements: Python 3.11+ and PostgreSQL.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
cp .env.example .env
uvicorn app.main:app --reload --app-dir src
```

All application environment variables use the `VOUCH_` prefix. The example configuration
is safe for local development only; use managed secrets and managed PostgreSQL in deployed
environments.

## Operational endpoints

- `GET /api/v1/health/live` verifies that the API process is running.
- `GET /api/v1/health/ready` verifies that required dependencies are available.
- `GET /api/v1/assets` searches active Lagos creative-gear inventory (supports
  category, date-range, daily-rate, and limit/cursor filters).
- `GET /api/v1/assets/{asset_id}` returns the public detail of a single active Lagos listing.
- API documentation is available at `/docs` outside production.

## Quality checks

```bash
ruff format --check .
ruff check .
pytest --cov=app --cov-report=term-missing
```

## Backups

Production PostgreSQL must use encrypted automated backups, point-in-time recovery, and a
regular restore drill. Backup policy is an infrastructure responsibility and must be
validated before handling real bookings or payment records.
