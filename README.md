# Dawarich Cleaner - Self-Hosted

A FastAPI application to detect and clean outlier GPS points from your Dawarich instance.

## Features

- 🔍 **Smart Detection**: Identifies flying points, unrealistic speeds, and GPS anomalies
- 🎯 **Confidence Scoring**: Multi-factor analysis with confidence scores
- 🗺️ **Interactive Review**: Web UI to review and manage flagged points
- 🤖 **Auto-Scan**: Background scheduler runs every 10 minutes automatically
- 🐳 **Docker Ready**: Easy deployment with Docker and docker-compose
- 🏗️ **Clean Architecture**: FastAPI best practices with modular structure

## Quick Start

### Option 1: Using uv (recommended - faster)

```bash
# Install uv if you haven't already
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create virtual environment and install dependencies
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install .

# Configure environment
cp .env.example .env
# Edit .env with your Dawarich URL and API key

# Run the application
uvicorn asgi:application
```

### Option 2: Using standard Python venv

```bash
# Create virtual environment
python -m venv .venv

# Activate virtual environment
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install project and dependencies
pip install .

# Configure environment
cp .env.example .env
# Edit .env with your Dawarich URL and API key

# Run the application
uvicorn asgi:application
```

### Option 3: Using Docker

```bash
# Configure environment
cp .env.example .env
# Edit .env with your Dawarich URL and API key

# Start with docker-compose
docker-compose up -d

# Access the app at http://localhost:8000
```

## Configuration

`.env` file:
```env
DATABASE_URL=sqlite+aiosqlite:///./data/dawarich-cleaner.db
# Or use PostgreSQL:
# DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/dbname

DAWARICH_API_URL=https://your-dawarich-instance.com
DAWARICH_API_KEY=your_api_key_here
```

## Usage

1. **Scan for Outliers**: Select date range, timezone, and detection thresholds
2. **Review Flagged Points**: View detected outliers with confidence scores
3. **Take Actions**: Delete, ignore, or restore flagged points
4. **Auto-Scan**: App automatically scans every 10 minutes for new outliers (runs in background)

## Detection Algorithms

- **Flying Points**: Sudden jumps away and back
- **Speed Violations**: Exceeds realistic speeds
- **Spike Detection**: Points far from trajectory
- **Timestamp Issues**: Duplicates or out-of-order

## API Endpoints

- `GET /` - Dashboard
- `POST /scan` - Run scan
- `GET /review` - Review points
- `POST /action/{action}` - Bulk actions
- `GET /health` - Health check (includes auto-scan status)

## Development
Activate your virtual environment first
source .venv/bin/activate

# Run with auto-reload
uvicorn asgi:application --reload

# Run on different port
uvicorn asgi:application --reload --port 3000

# Run with different host
uvicorn asgi:application --reload --host 127.0.0.1
# Or use uvicorn directly
uvicorn app.main:app --reload
```

## License

MIT
