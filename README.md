
# Day Planner (20-minute blocks)

A tiny local-only day planner that divides your day into 20‑minute blocks, with a side panel for today's todos. Data is stored as one JSON file per day in `data/YYYY-MM-DD.json`.

## Features

- Set start/end of your day (e.g., 09:00–21:00). The grid regenerates accordingly.
- 20‑minute blocks; empty blocks are pale, filled blocks are greenish.
- Add/delete simple todos; click a todo to prefill a block.
- Daylight indicator: sun icon for blocks between local sunrise and sunset; moon otherwise (configurable by latitude/longitude and timezone).
- Auto Dark Mode: uses dark theme (dark greys/low‑sat blues) after local sunset and before sunrise; light theme during daytime. No pitch black backgrounds.
- All data stays local, saved under `data/`.
- Single-page UX via Flask + HTMX. No DB, no build steps.

## Run directly (no Docker)

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open http://localhost:8383 in your browser.

## Running Tests

To run the automated tests, ensure you have the dependencies installed and run:

```bash
python -m pytest tests/
```

### Configure timezone (optional but recommended)
To ensure sunrise/sunset and the selected default date use your local timezone when running in Docker or servers set to UTC, set one of:

- TIMEZONE (e.g., Europe/Amsterdam)
- TZ (alias)

Example (macOS/Linux):

```bash
export TIMEZONE=Europe/Amsterdam
python app.py
```

### Configure sunrise/sunset (optional)
Set your latitude and longitude via environment variables so the app can show sun/moon icons correctly for your location:

- LATITUDE (or LAT)
- LONGITUDE (or LON)

Examples:

macOS/Linux:

```bash
export LATITUDE=52.2777
export LONGITUDE=7.2777
python app.py
```

Windows (PowerShell):

```powershell
$env:LATITUDE = 52.2777
$env:LONGITUDE = 7.2777
python app.py
```

If not set, icons are hidden.

## Run with Docker

```bash
docker build -t dayplanner .
docker run --rm -p 8383:8383 \
  -v $(pwd)/dayplanner_data:/app/data \
  -e DATA_DIR=/app/data \
  -e LATITUDE=52.2777 -e LONGITUDE=7.2777 \
  -e TZ=Europe/Amsterdam \
  dayplanner
```

Or with docker-compose (recommended):

```bash
docker compose up --build -d
```
The container mounts a named volume (dayplanner_data) at /app/data, so your JSON files persist across rebuilds and container restarts.

### Using LATITUDE, LONGITUDE and TZ with docker-compose

Set your location and timezone so sunrise/sunset and the day selection align with your locale.

Option A — one-time run with inline env vars:

```bash
LATITUDE=52.2777 LONGITUDE=7.2777 TZ=Europe/Amsterdam docker compose up --build -d
```

Option B — edit docker-compose.yml (persistent):

1. Open docker-compose.yml and ensure under services.web.environment:
   
   ```yaml
   services:
     web:
       environment:
         - DATA_DIR=/app/data
         - LATITUDE=52.2777
         - LONGITUDE=7.2777
         - TZ=Europe/Amsterdam
   ```

2. Recreate the container to apply changes:

```bash
docker compose up -d --build
```

Option C — use an .env file next to docker-compose.yml:

1. Create a file named `.env` (no filename extensions) with:

```
LATITUDE=52.2777
LONGITUDE=7.2777
TZ=Europe/Amsterdam
```

2. Bring the stack up:

```bash
docker compose up --build -d
```

Notes:
- You can also set LAT and LON as aliases instead of LATITUDE/LONGITUDE.
- You can set TIMEZONE instead of TZ; both are supported by the app.
- Data is stored in a named volume (dayplanner_data) mounted at /app/data; you can change it, but keep DATA_DIR in the container set to /app/data unless you modify app.py accordingly.
- If the LATITUDE/LONGITUDE values are missing or invalid, the app simply hides the icons; everything else works normally.

## Data format

Example `data/2025-09-28.json`:

```json
{
  "date": "2025-09-28",
  "topic": "Quantum Computing basics",
  "start": "09:00",
  "end": "21:00",
  "todos": ["Deep work", "Groceries"],
  "blocks": [
    {"time": "09:00", "activity": "Deep work"},
    {"time": "09:20", "activity": ""}
  ]
}
```

## Notes

- Uses CDN for HTMX and PicoCSS. If you need offline, replace with local files.
- This is intentionally minimal; extend as you like: color labels, export to CSV/Markdown, keyboard shortcuts, etc.
