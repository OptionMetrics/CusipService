# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CusipService loads daily CUSIP securities data files from CUSIP Global Services into a PostgreSQL database. The loader reads pipe-delimited PIF files, strips footer records, and performs upserts via staging tables.

**Architecture**: Stonebranch orchestration downloads files via SFTP to S3/EFS, then calls this REST API to trigger file loads. Query endpoints are provided via PostgREST.

## File Types

| Suffix | Type | Description |
|--------|------|-------------|
| `R.PIP` | issuer | Issuer master data (~400K records) |
| `E.PIP` | issue | Security/issue data (~10M records) |
| `A.PIP` | issue_attr | Extended attributes per issue |

## Load Pattern

```
File → Strip Footer → COPY to Staging → Upsert to Master (single transaction)
```

Load order matters due to foreign keys: Issuer → Issue → Issue Attributes

## Development Setup

```bash
# Install dependencies including dev tools
uv sync

# Add a new dependency
uv add <package>

# Add a dev dependency
uv add --group dev <package>
```

## Common Commands

```bash
# Run the REST API locally
uv run uvicorn cusipservice.api.main:app --reload

# Run the CLI loader
uv run python -m cusipservice

# Run tests
uv run pytest

# Run a single test
uv run pytest tests/test_file.py::test_function_name

# Run tests with coverage
uv run pytest --cov

# Type checking
uv run mypy src

# Lint code
uv run ruff check .

# Format code
uv run ruff format .

# Lint and auto-fix
uv run ruff check --fix .
```

## Docker Commands

```bash
# Start full stack (PostgreSQL + FastAPI + PostgREST)
cd docker && docker-compose up -d

# View logs
cd docker && docker-compose logs -f

# Stop and clean up
cd docker && docker-compose down -v

# Rebuild after code changes
cd docker && docker-compose build api && docker-compose up -d
```

## Database Migrations (Alembic)

```bash
# Run migrations (applies all pending migrations)
uv run alembic upgrade head

# Check current migration status
uv run alembic current

# Show migration history
uv run alembic history

# Create a new migration
uv run alembic revision -m "description of change"

# Rollback one migration
uv run alembic downgrade -1

# Rollback all migrations
uv run alembic downgrade base

# Generate SQL without running (for review)
uv run alembic upgrade head --sql
```

Environment variables for migrations:
- `CUSIP_DB_HOST`, `CUSIP_DB_PORT`, `CUSIP_DB_NAME`, `CUSIP_DB_USER`, `CUSIP_DB_PASSWORD`

## API Endpoints

### Job Endpoints (FastAPI - port 8000)

All job endpoints require `Authorization: Bearer <token>` header.

```bash
# Load issuer file for today
curl -X POST http://localhost:8000/jobs/load-issuer \
  -H "Authorization: Bearer changeme" \
  -H "Content-Type: application/json" \
  -d '{}'

# Load all files for specific date
curl -X POST http://localhost:8000/jobs/load-all \
  -H "Authorization: Bearer changeme" \
  -H "Content-Type: application/json" \
  -d '{"date": "2024-01-15"}'

# Health check (no auth)
curl http://localhost:8000/health
```

### Query Endpoints (PostgREST - port 3000)

```bash
# Get securities summary with pagination
curl "http://localhost:3000/v_security_summary?limit=100&offset=0"

# Filter by issuer type
curl "http://localhost:3000/v_security?issuer_type=eq.C"

# Full-text search
curl "http://localhost:3000/rpc/search_securities?search_query=apple"

# Get reference data
curl "http://localhost:3000/ref_issuer_type"
```

## Code Style

This project follows strict Python style guidelines enforced by tooling:

- **Formatter**: Ruff (line length 88, Black-compatible)
- **Linter**: Ruff with rules for pycodestyle, Pyflakes, isort, bugbear, comprehensions, pyupgrade, unused arguments, and simplify
- **Type Checking**: mypy in strict mode - all code must be fully typed

All configuration is in `pyproject.toml`. Run `uv run ruff format . && uv run ruff check --fix . && uv run mypy src` before committing.

## Project Structure

```
sql/
  cusip_ddl.sql         # Schema: ref_*, master, stg_* tables, indexes
  cusip_ref_data.sql    # Reference data inserts
  cusip_views.sql       # v_issuer, v_issue, v_security views
src/cusipservice/
  loader.py             # Core loading logic (read, clean, COPY, upsert)
  config.py             # pydantic-settings configuration
  file_discovery.py     # Find PIF files by date pattern
  __main__.py           # CLI entry point
  api/
    main.py             # FastAPI app factory
    dependencies.py     # Auth and DB config dependencies
    models.py           # Pydantic request/response models
    routers/
      health.py         # Health check endpoints
      jobs.py           # Job endpoints (load-issuer, load-all, etc.)
docker/
  Dockerfile            # FastAPI container
  docker-compose.yml    # Full stack (db + api + postgrest)
  init/                 # DB init scripts (for local dev only)
migrations/
  versions/             # Alembic migration files
  env.py                # Alembic environment config
```

## Database Conventions

- **Master tables**: `issuer`, `issue`, `issue_attribute`
- **Staging tables**: `stg_issuer`, `stg_issue`, `stg_issue_attribute`
- **Reference tables**: `ref_*` (e.g., `ref_issuer_type`)
- **Views**: `v_*` (e.g., `v_security`, `v_security_summary`)
