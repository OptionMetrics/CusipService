# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CusipService loads daily CUSIP securities data files from CUSIP Global Services into a PostgreSQL database. The loader reads pipe-delimited PIP files, strips footer records, and performs upserts via staging tables.

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

## Configuration

All configuration is via environment variables with `CUSIP_` prefix.

### Database Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `CUSIP_DB_HOST` | `localhost` | PostgreSQL host |
| `CUSIP_DB_PORT` | `5432` | PostgreSQL port |
| `CUSIP_DB_NAME` | `cusip` | Database name |
| `CUSIP_DB_USER` | `cusip_app` | Database user |
| `CUSIP_DB_PASSWORD` | (required) | Database password |

### File Source Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `CUSIP_FILE_SOURCE` | `local` | File source: `local` or `s3` |
| `CUSIP_FILE_DIR` | `/data/pip_files` | Local directory for PIP files (when `file_source=local`) |
| `CUSIP_S3_BUCKET` | (required for S3) | S3 bucket name |
| `CUSIP_S3_PREFIX` | `pip/` | S3 prefix/path (include trailing slash) |
| `CUSIP_S3_REGION` | (optional) | AWS region for S3 bucket |

### API Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `CUSIP_API_TOKEN` | (required) | Bearer token for job endpoint auth |

### Local Development with S3

To use S3 files with local PostgreSQL (requires AWS SSO login):

```bash
# Login to AWS SSO
aws sso login --profile your-profile

# Run with S3 + local DB
AWS_PROFILE=your-profile \
CUSIP_FILE_SOURCE=s3 \
CUSIP_S3_BUCKET=cusip-pip-files-shared \
CUSIP_DB_HOST=localhost \
uv run uvicorn cusipservice.api.main:app --reload
```

See `docs/AWS_MULTI_ACCOUNT_SETUP.md` for full multi-account deployment guide.

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
  file_source.py        # File source abstraction (local + S3)
  file_discovery.py     # Find PIP files by date pattern (legacy compat)
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
docs/
  AWS_MULTI_ACCOUNT_SETUP.md  # Multi-account S3 deployment guide
```

## Database Conventions

- **Master tables**: `issuer`, `issue`, `issue_attribute`
- **Staging tables**: `stg_issuer`, `stg_issue`, `stg_issue_attribute`
- **Reference tables**: `ref_*` (e.g., `ref_issuer_type`)
- **Views**: `v_*` (e.g., `v_security`, `v_security_summary`)
