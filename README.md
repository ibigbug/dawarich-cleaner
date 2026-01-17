# Dawarich Cleaner

A Python Cloudflare Worker built with **FastAPI** and **Jinja2** that automatically detects and cleans GPS outliers from your self-hosted Dawarich instance. Perfect for removing jump-back points, unrealistic speeds, and oscillating patterns reported by iOS Overland app.

## Features

- 🔍 **Intelligent Detection**: Identifies jump-backs to stay locations, unrealistic speeds, and oscillating patterns
- 🚀 **FastAPI Framework**: Modern async web framework with automatic validation
- 🎨 **Jinja2 Templates**: Clean template inheritance and components
- 🗄️ **Database Abstraction**: Clean query interface over D1
- 🌐 **Web Interface**: Review and manage flagged points with batch operations
- ⏰ **Automated Scanning**: Cron job runs daily to check for new outliers
- 🗃️ **D1 Database**: Store flagged points for review before deletion
- 🔐 **Zero Trust Ready**: Protect with Cloudflare Access

## Detection Methods

1. **Jump-backs**: Points that return to recent stay locations during movement (common iOS bug)
2. **Unrealistic speeds**: Points requiring impossible travel speeds (>200 km/h by default)
3. **Oscillating patterns**: Points creating back-and-forth movement patterns

## Setup

### 1. Install uv (if not already installed)
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Create D1 Database
```bash
# Create the database
uv run pywrangler d1 create dawarich-cleaner

# This will output a database_id - copy it and update wrangler.toml
# Replace the empty database_id in wrangler.toml with your database ID

# Initialize the schema
uv run pywrangler d1 execute dawarich-cleaner --file=./schema.sql
```

### 3. Configure Secrets
```bash
# Set your Dawarich instance URL
uv run pywrangler secret put DAWARICH_API_URL
# Enter: https://your-dawarich-instance.com

# Set your Dawarich API key
uv run pywrangler secret put DAWARICH_API_KEY
# Enter your API key from Dawarich settings
```

### 4. Login to Cloudflare
```bash
uv run pywrangler login
```

### 5. Deploy
```bash
uv run pywrangler deploy
```

## Usage

### Web Interface

After deployment, visit your worker URL (e.g., `https://dawarich-cleaner.your-account.workers.dev`)

**Dashboard**:
- View statistics (pending, deleted, total flagged)
- Configure scan parameters (date range, speed threshold, jump radius)
- Start manual scans

**Review Page**:
- See all flagged points with detection reasons
- Batch select and delete/ignore points
- View points on Google Maps

### Automated Scanning

The cron job runs daily at 2 AM UTC and automatically:
- Scans the last 7 days of GPS data
- Flags new outliers
- Stores them for your review

Edit the cron schedule in [wrangler.toml](wrangler.toml#L11):
```toml
[[triggers.crons]]
cron = "0 2 * * *"  # Daily at 2 AM UTC
```

## Protecting with Cloudflare Zero Trust

To protect your worker with Cloudflare Access:

1. **Go to Cloudflare Dashboard** → Zero Trust → Access → Applications
2. **Create Application**:
   - Name: `Dawarich Cleaner`
   - Domain: Your worker domain (e.g., `dawarich-cleaner.your-account.workers.dev`)
   - Type: Self-hosted
3. **Add Policy**:
   - Name: `Allowed Users`
   - Action: Allow
   - Include: Add your email or group
4. **Save Application**

Now your worker will require authentication via Cloudflare Access before allowing access.

Alternatively, use **Cloudflare Tunnel** if you want to keep it completely private.

## Configuration Options

### Detection Parameters

Adjust in the web UI or modify defaults:

- **Max Speed** (default: 200 km/h): Maximum realistic ground speed
- **Jump Back Radius** (default: 5 km): Distance to consider as jump-back to stay location
- **Stay Duration** (code): Minimum time at location to consider it a "stay" (5 minutes)
- **Stay Radius** (code): Maximum radius for clustering stay points (100 meters)

### Cron Schedule

Edit in [wrangler.toml](wrangler.toml#L11-L12):

```toml
[[triggers.crons]]
cron = "0 */6 * * *"  # Every 6 hours
```

Common patterns:
- `0 */1 * * *` - Every hour
- `0 2 * * *` - Daily at 2 AM
- `0 0 * * 0` - Weekly on Sunday

## Development

**Run locally:**
```bash
uv run pywrangler dev
```

**View logs:**
```bash
uv run pywrangler tail
```

**Query D1 database:**
```bash
uv run pywrangler d1 execute dawarich-cleaner --command="SELECT * FROM flagged_points LIMIT 10"
```

## Project Structure

```
dawarich-cleaner/
├── src/
│   ├── worker.py              # FastAPI app with routes
│   ├── dawarich_client.py     # Dawarich API client
│   ├── outlier_detector.py    # Detection algorithms
│   └── database.py            # Database helper/abstraction
├── templates/
│   ├── base.html              # Base Jinja2 template
│   ├── dashboard.html         # Dashboard page
│   ├── review.html            # Review page
│   └── result.html            # Result page
├── schema.sql                 # D1 database schema
├── wrangler.toml              # Cloudflare Worker configuration
├── pyproject.toml             # Python dependencies (FastAPI, Jinja2)
└── README.md
```

## Dawarich API

This worker uses the following Dawarich API endpoints:

- `GET /api/v1/points` - Fetch points by date range
- `DELETE /api/v1/points/bulk_destroy` - Delete multiple points

Authentication: `Authorization: Bearer YOUR_API_KEY`

## Troubleshooting

**"Point not found" errors during deletion**:
- The point may have already been deleted manually
- The worker will mark it as deleted in the database anyway

**No points detected**:
- Check your date range has GPS data
- Verify API credentials are correct
- Check worker logs: `uv run pywrangler tail`

**Database errors**:
- Ensure you ran the schema.sql file
- Check database_id is set in wrangler.toml

## Important Notes

- Flagged points are stored in D1 until you review and delete them
- Deletion from Dawarich is permanent - review carefully before deleting
- The cron job only flags new outliers, it doesn't auto-delete
- Free Cloudflare plan allows up to 3 cron triggers per account

## Documentation

- [Cloudflare Workers Python](https://developers.cloudflare.com/workers/runtime-apis/python/)
- [Pywrangler](https://github.com/cloudflare/workers-py)
- [D1 Database](https://developers.cloudflare.com/d1/)
- [Cron Triggers](https://developers.cloudflare.com/workers/configuration/cron-triggers/)
- [Cloudflare Zero Trust](https://developers.cloudflare.com/cloudflare-one/)
- [Dawarich GitHub](https://github.com/Freika/dawarich)

