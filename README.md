
# Day Planner (20-minute blocks)

A tiny local-only day planner that divides your day into 20‑minute blocks, with a side panel for today's todos. Data is stored as one JSON file per day in `data/YYYY-MM-DD.json`.

## Features

- Set start/end of your day (e.g., 09:00–21:00). The grid regenerates accordingly.
- 20‑minute blocks; empty blocks are pale, filled blocks are greenish.
- Add/delete simple todos; click a todo to prefill a block.
- Daylight indicator: sun icon for blocks between local sunrise and sunset; moon otherwise (configurable by latitude/longitude).
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
  dayplanner
```

Or with docker-compose (recommended):

```bash
docker compose up --build -d
```
The container mounts a named volume (dayplanner_data) at /app/data, so your JSON files persist across rebuilds and container restarts.

To enable sunrise/sunset in docker-compose, set LATITUDE and LONGITUDE in the service environment.

## Data format

Example `data/2025-09-28.json`:

```json
{
  "date": "2025-09-28",
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
