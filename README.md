# Dawarich Cleaner

Automated GPS outlier detection and cleaning for your Dawarich instance.

## Features

- 🔍 **Smart Detection**: Distance jumps, unrealistic speeds, and GPS anomalies
- 🎯 **Confidence Scoring**: Multi-factor analysis with confidence ratings
- 🗺️ **Interactive Review**: Web UI to review and manage flagged points
- 🤖 **Auto-Scan**: Background scheduler runs every 10 minutes
- 🐳 **Docker Ready**: One-command deployment with Docker
- 💾 **SQLite or PostgreSQL**: Flexible database options

## Quick Start

### Using Docker (Recommended)

```bash
docker run -d \
  -p 8000:8000 \
  -e DAWARICH_API_URL=https://your-dawarich.com \
  -e DAWARICH_API_KEY=your_api_key \
  -v dawarich-cleaner-data:/app/data \
  ghcr.io/yourusername/dawarich-cleaner:latest
```

Access at: http://localhost:8000

### Using Docker Compose

```yaml
version: '3.8'
services:
  dawarich-cleaner:
    image: ghcr.io/yourusername/dawarich-cleaner:latest
    ports:
      - "8000:8000"
    environment:
      DAWARICH_API_URL: https://your-dawarich.com
      DAWARICH_API_KEY: your_api_key
      DATABASE_URL: sqlite+aiosqlite:///./data/cleaner.db
    volumes:
      - ./data:/app/data
    restart: unless-stopped
```

### Local Development

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"

# Configure
cp .env.example .env
# Edit .env with your settings

# Install pre-commit hooks
pre-commit install

# Run
uvicorn app.main:app --reload
```

### Code Quality

```bash
# Run all pre-commit checks
pre-commit run --all-files

# Run tests
pytest

# Run tests with coverage
pytest --cov=app --cov-report=html
# Open htmlcov/index.html to view coverage report

# Individual tools
ruff check --fix .        # Lint and auto-fix
ruff format .             # Format code
```

## CI/CD

The project includes GitHub Actions workflows:

- **Pre-commit Checks**: Runs on all PRs and pushes to main
- **Tests & Coverage**: Runs tests and uploads coverage to Codecov
- **Docker Build**: Builds and publishes Docker images to GHCR

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|----------|
| `DAWARICH_API_URL` | Your Dawarich instance URL | Required |
| `DAWARICH_API_KEY` | Dawarich API key | Required |
| `DATABASE_URL` | Database connection string | `sqlite+aiosqlite:///./data/cleaner.db` |

### Database Options

**SQLite (default):**
```bash
DATABASE_URL=sqlite+aiosqlite:///./data/cleaner.db
```

**PostgreSQL:**
```bash
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/dawarich_cleaner
```

## How It Works

1. **Manual Scan**: Select date range and thresholds via web UI
2. **Auto-Scan**: Runs every 10 minutes automatically (scans last 24h on first run, then incremental)
3. **Review**: Check flagged points with detection reasons and confidence scores
4. **Action**: Delete, ignore, or restore points in bulk

### Detection Methods

- **Jump Outliers**: Large distance jumps and spike patterns (sudden jumps away from trajectory and back)
- **Speed Violations**: Movement exceeding 30 m/s (108 km/h) default
- **Distance Spikes**: Points > 500m from expected trajectory
- **Timestamp Issues**: Duplicate or out-of-order timestamps

## API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Dashboard and scan form |
| `/scan` | POST | Trigger manual scan |
| `/review` | GET | Review flagged points |
| `/action/{action}` | POST | Bulk actions (delete/ignore/restore) |
| `/health` | GET | Health check with auto-scan status |

## License

MIT
