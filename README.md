# CusipService

A REST API service for loading and querying CUSIP securities data from CUSIP Global Services. The service ingests daily PIF (Pipe-delimited) files and provides queryable REST endpoints for securities data.

## Architecture

The service consists of two API planes:

| Port | Service | Purpose |
|------|---------|---------|
| **8000** | FastAPI | Control plane - file loading jobs, health checks |
| **3000** | PostgREST | Query plane - read-only REST API for views |
| **8080** | Swagger UI | Query plane documentation |

### Data Flow

```
PIF Files → FastAPI /jobs/* → PostgreSQL → PostgREST → Consumers
```

### File Types

| Suffix | Type | Description |
|--------|------|-------------|
| `R.PIP` | issuer | Issuer master data (~400K records) |
| `E.PIP` | issue | Security/issue data (~10M records) |
| `A.PIP` | issue_attr | Extended attributes per issue |

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Python 3.11+ (for local development)
- [uv](https://github.com/astral-sh/uv) package manager

### Running with Docker Compose

```bash
cd docker

# Start all services
docker-compose up -d

# Check service health
curl http://localhost:8000/health

# View logs
docker-compose logs -f api
```

### Services

Once running, access:
- **FastAPI docs**: http://localhost:8000/docs
- **PostgREST docs**: http://localhost:8080
- **PostgREST API**: http://localhost:3000

## API Reference

### Control Plane (Port 8000)

All job endpoints require bearer token authentication.

#### Health Checks

```bash
# Health check (includes DB connectivity)
curl http://localhost:8000/health

# Kubernetes probes
curl http://localhost:8000/ready
curl http://localhost:8000/live
```

#### Load Jobs

Load files for a specific date (defaults to today):

```bash
# Load all file types (issuer → issue → issue_attr)
curl -X POST http://localhost:8000/jobs/load-all \
  -H "Authorization: Bearer ${CUSIP_API_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"date": "2024-01-15"}'

# Load individual file types
curl -X POST http://localhost:8000/jobs/load-issuer \
  -H "Authorization: Bearer ${CUSIP_API_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"date": "2024-01-15"}'

curl -X POST http://localhost:8000/jobs/load-issue \
  -H "Authorization: Bearer ${CUSIP_API_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"date": "2024-01-15"}'

curl -X POST http://localhost:8000/jobs/load-issue-attr \
  -H "Authorization: Bearer ${CUSIP_API_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"date": "2024-01-15"}'
```

**File naming convention**: Files must match pattern `CMD{mm-dd}*.PIP`:
- `CMD01-15R.PIP` - Issuer file for January 15
- `CMD01-15E.PIP` - Issue file for January 15
- `CMD01-15A.PIP` - Issue attribute file for January 15

### Query Plane (Port 3000)

PostgREST provides automatic REST endpoints for database views.

#### Available Views

| Endpoint | Description |
|----------|-------------|
| `/v_issuer` | Issuer data with decoded reference values |
| `/v_issue` | Issue/security data with decoded reference values |
| `/v_security_summary` | Combined issuer + issue summary |

#### Filtering Examples

```bash
# Case-insensitive search
curl "http://localhost:3000/v_issuer?issuer_name=ilike.*APPLE*"

# Exact match
curl "http://localhost:3000/v_issue?cusip=eq.037833100"

# Multiple conditions
curl "http://localhost:3000/v_issue?issue_status=eq.A&security_type=eq.COM"

# Pagination
curl "http://localhost:3000/v_issuer?limit=100&offset=200"

# Select specific columns
curl "http://localhost:3000/v_issuer?select=issuer_id,issuer_name,city,state"

# Order results
curl "http://localhost:3000/v_issuer?order=issuer_name.asc"
```

#### Full-Text Search

```bash
curl -X POST http://localhost:3000/rpc/search_securities \
  -H "Content-Type: application/json" \
  -d '{"search_query": "KEURIG"}'
```

#### PostgREST Operators

| Operator | Description | Example |
|----------|-------------|---------|
| `eq` | Equals | `?status=eq.active` |
| `neq` | Not equals | `?status=neq.deleted` |
| `gt`, `gte` | Greater than | `?amount=gt.100` |
| `lt`, `lte` | Less than | `?amount=lt.1000` |
| `like` | LIKE (case-sensitive) | `?name=like.*Corp*` |
| `ilike` | LIKE (case-insensitive) | `?name=ilike.*corp*` |
| `in` | In list | `?status=in.(A,B,C)` |
| `is` | IS NULL/TRUE/FALSE | `?deleted=is.null` |

## Local Development

### Setup

```bash
# Install dependencies
uv sync

# Run the API locally
uv run uvicorn cusipservice.api.main:app --reload

# Or use the CLI
uv run python -m cusipservice
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `CUSIP_DB_HOST` | PostgreSQL host | `localhost` |
| `CUSIP_DB_PORT` | PostgreSQL port | `5432` |
| `CUSIP_DB_NAME` | Database name | `cusip` |
| `CUSIP_DB_USER` | Database user | `cusip_app` |
| `CUSIP_DB_PASSWORD` | Database password | (required) |
| `CUSIP_FILE_DIR` | Directory containing PIF files | `/data/pif_files` |
| `CUSIP_API_TOKEN` | Bearer token for job endpoints | (required) |

Create a `.env` file for local development:

```bash
CUSIP_DB_HOST=localhost
CUSIP_DB_PORT=5432
CUSIP_DB_NAME=cusip
CUSIP_DB_USER=postgres
CUSIP_DB_PASSWORD=postgres
CUSIP_FILE_DIR=./pif_files
CUSIP_API_TOKEN=changeme
```

### Code Quality

```bash
# Run tests
uv run pytest

# Run tests with coverage
uv run pytest --cov

# Type checking
uv run mypy src

# Lint
uv run ruff check .

# Format
uv run ruff format .

# Fix lint issues
uv run ruff check --fix .
```

## Database Migrations

This project uses Alembic for database migrations.

### Running Migrations

```bash
# Apply all migrations
uv run alembic upgrade head

# Rollback one migration
uv run alembic downgrade -1

# View migration history
uv run alembic history

# View current revision
uv run alembic current
```

### Creating New Migrations

```bash
# Auto-generate migration from model changes
uv run alembic revision --autogenerate -m "description"

# Create empty migration
uv run alembic revision -m "description"
```

### Docker vs Migrations

- **Local Docker development**: Uses init scripts in `docker/init/` (runs on first container creation)
- **Production deployment**: Use Alembic migrations for schema management

## Production Deployment

### AWS ECS/Fargate

1. **Build and push Docker image**:
   ```bash
   docker build -t cusip-service -f docker/Dockerfile .
   docker tag cusip-service:latest <account>.dkr.ecr.<region>.amazonaws.com/cusip-service:latest
   docker push <account>.dkr.ecr.<region>.amazonaws.com/cusip-service:latest
   ```

2. **Run migrations** (from a task or CI/CD pipeline):
   ```bash
   uv run alembic upgrade head
   ```

3. **Configure environment variables** in ECS task definition:
   - Set all `CUSIP_*` variables
   - Use AWS Secrets Manager for sensitive values

4. **Configure ALB routing**:
   - `/jobs/*`, `/health`, `/ready`, `/live` → FastAPI (8000)
   - `/api/*` → PostgREST (3000)

### Health Checks

Configure your load balancer/orchestrator health checks:

| Endpoint | Purpose | Recommended Interval |
|----------|---------|---------------------|
| `/live` | Liveness probe | 10s |
| `/ready` | Readiness probe | 5s |
| `/health` | Full health check | 30s |

## Project Structure

```
CusipService/
├── pyproject.toml              # Dependencies and tool config
├── alembic.ini                 # Alembic configuration
├── migrations/                 # Database migrations
│   ├── env.py
│   └── versions/
│       └── 001_initial_schema.py
├── docker/
│   ├── Dockerfile              # FastAPI container
│   ├── docker-compose.yml      # Local development stack
│   └── init/                   # DB init scripts (dev only)
│       ├── 01-cusip_ddl.sql
│       ├── 02-cusip_ref_data.sql
│       ├── 03-cusip_views.sql
│       ├── 04-full_text_search.sql
│       └── 05-postgrest_roles.sql
├── sql/                        # Source SQL files
│   ├── cusip_ddl.sql
│   ├── cusip_ref_data.sql
│   └── cusip_views.sql
└── src/cusipservice/
    ├── __init__.py
    ├── __main__.py             # CLI entry point
    ├── config.py               # Configuration management
    ├── loader.py               # Core loading logic
    ├── file_discovery.py       # File pattern matching
    └── api/
        ├── main.py             # FastAPI application
        ├── dependencies.py     # Auth and config injection
        ├── models.py           # Pydantic models
        └── routers/
            ├── health.py       # Health check endpoints
            └── jobs.py         # Job endpoints
```

## License

Proprietary - Internal use only.
