
from __future__ import annotations
import os, json
from datetime import datetime, timedelta, timezone, date as date_cls, time as time_cls
from pathlib import Path
from flask import Flask, render_template, request, redirect, url_for, abort
import logging

from zoneinfo import ZoneInfo
from suntime import Sun, SunTimeException

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("dayplanner")

DATA_DIR = Path(os.environ.get("DATA_DIR", "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

# --- Timezone helper ---

def get_configured_tz() -> ZoneInfo:
    """Return the timezone configured via TIMEZONE or TZ env vars.
    Falls back to the system local timezone if neither is provided or invalid.
    """
    tz_name = (os.environ.get("TIMEZONE") or os.environ.get("TZ") or "").strip()
    if tz_name:
        try:
            return ZoneInfo(tz_name)
        except Exception:
            logger.warning("Invalid TIMEZONE/TZ value %r; falling back to system local timezone.", tz_name)
    # Fallback: use whatever the system considers local
    return datetime.now().astimezone().tzinfo  # type: ignore[return-value]


def date_str(d: date_cls) -> str:
    return d.strftime("%Y-%m-%d")

def plan_path(day: date_cls) -> Path:
    return DATA_DIR / f"{date_str(day)}.json"

def parse_time(hhmm: str) -> time_cls:
    return datetime.strptime(hhmm, "%H:%M").time()

def time_to_str(t: time_cls) -> str:
    return f"{t.hour:02d}:{t.minute:02d}"

def default_plan(day: date_cls) -> dict:
    # default 09:00 - 21:00
    start = parse_time("09:00")
    end = parse_time("21:00")
    return build_plan(day, start, end)

def build_plan(day: date_cls, start: time_cls, end: time_cls, existing: dict | None=None) -> dict:
    slots = []
    # generate 20-min slots inclusive of start, exclusive of end
    dt = datetime.combine(day, start)
    dt_end = datetime.combine(day, end)
    while dt < dt_end:
        slots.append({"time": dt.strftime("%H:%M"), "activity": ""})
        dt += timedelta(minutes=20)
    plan = {
        "date": date_str(day),
        "start": time_to_str(start),
        "end": time_to_str(end),
        "todos": [],
        "blocks": slots,
    }
    # if existing provided, try to keep activities where times still exist
    if existing:
        existing_acts = {b["time"]: b.get("activity","") for b in existing.get("blocks",[])}
        plan["todos"] = existing.get("todos", [])
        for b in plan["blocks"]:
            if b["time"] in existing_acts:
                b["activity"] = existing_acts[b["time"]]
    return plan

def load_plan(day: date_cls) -> dict:
    p = plan_path(day)
    if p.exists():
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    # create default if not exists
    plan = default_plan(day)
    save_plan(day, plan)
    return plan

def save_plan(day: date_cls, plan: dict) -> None:
    with open(plan_path(day), "w", encoding="utf-8") as f:
        json.dump(plan, f, indent=2, ensure_ascii=False)

# --- Sun times helper ---

def is_dark_mode(day: date_cls, sunrise: str | None, sunset: str | None) -> bool:
    """Return True if current local time is considered 'night' (use dark mode).
    Uses sunrise/sunset if available, otherwise falls back to 07:00–19:00 daytime.
    The decision is based on the current time in the configured timezone.
    """
    try:
        now_local = datetime.now(get_configured_tz()).time()
        if sunrise and sunset:
            sr = parse_time(sunrise)
            ss = parse_time(sunset)
            return not (sr <= now_local < ss)
        # Fallback window if no sun data
        sr = parse_time("07:00")
        ss = parse_time("19:00")
        return not (sr <= now_local < ss)
    except Exception:
        # Be safe: default to light if anything goes wrong
        return False

def get_sun_times(day: date_cls) -> tuple[str | None, str | None]:
    """Return (sunrise, sunset) as HH:MM local time strings for the given date.
    If LATITUDE/LONGITUDE env vars are not set or an error occurs, return (None, None).
    """
    lat_raw = os.environ.get("LATITUDE", os.environ.get("LAT", ""))
    lon_raw = os.environ.get("LONGITUDE", os.environ.get("LON", ""))
    if not lat_raw or not lon_raw:
        logger.info("Sun times disabled: LATITUDE/LONGITUDE not set (LAT=%r, LON=%r).", lat_raw, lon_raw)
        return (None, None)
    try:
        lat = float(lat_raw)
        lon = float(lon_raw)
    except (ValueError, TypeError):
        logger.warning("Invalid LATITUDE/LONGITUDE: LAT=%r LON=%r", lat_raw, lon_raw)
        return (None, None)

    try:
        sun = Sun(lat, lon)
        # Work around suntime expecting a datetime for timezone math in some versions
        at_dt = datetime.combine(day, time_cls(12, 0))  # local noon on the given date (naive)
        sr_utc = sun.get_sunrise_time(at_dt)
        ss_utc = sun.get_sunset_time(at_dt)
        if sr_utc.tzinfo is None:
            sr_utc = sr_utc.replace(tzinfo=timezone.utc)
        if ss_utc.tzinfo is None:
            ss_utc = ss_utc.replace(tzinfo=timezone.utc)
        local_tz = get_configured_tz()
        sr_local = sr_utc.astimezone(local_tz)
        ss_local = ss_utc.astimezone(local_tz)
        sunrise = sr_local.strftime("%H:%M")
        sunset = ss_local.strftime("%H:%M")
        logger.info("Sun times for %s at (%.5f, %.5f): sunrise=%s sunset=%s tz=%s", date_str(day), lat, lon, sunrise, sunset, local_tz)
        return (sunrise, sunset)
    except SunTimeException as e:
        logger.warning("SunTimeException: %s (lat=%.5f lon=%.5f) for %s", e, lat, lon, date_str(day))
        return (None, None)
    except Exception as e:
        logger.exception("Failed to compute sun times: %s", e)
        return (None, None)

@app.route("/", methods=["GET"])
def index():
    qdate = request.args.get("date")
    try:
        if qdate:
            day = datetime.strptime(qdate, "%Y-%m-%d").date()
        else:
            # Use configured timezone for "today"
            day = datetime.now(get_configured_tz()).date()
    except ValueError:
        abort(400, "Bad date format, expected YYYY-MM-DD")
    plan = load_plan(day)
    # Navigation dates
    prev_day = day - timedelta(days=1)
    next_day = day + timedelta(days=1)
    sunrise, sunset = get_sun_times(day)
    is_dark = is_dark_mode(day, sunrise, sunset)
    return render_template("index.html", plan=plan, prev_day=prev_day, next_day=next_day, sunrise=sunrise, sunset=sunset, is_dark=is_dark)

@app.route("/settings", methods=["POST"])
def update_settings():
    day = datetime.strptime(request.form.get("date"), "%Y-%m-%d").date()
    start = parse_time(request.form.get("start"))
    end = parse_time(request.form.get("end"))
    if datetime.combine(day, end) <= datetime.combine(day, start):
        abort(400, "End time must be after start time.")
    existing = load_plan(day)
    plan = build_plan(day, start, end, existing)
    save_plan(day, plan)
    # Return just the blocks fragment for HTMX to swap
    sunrise, sunset = get_sun_times(day)
    return render_template("partials/blocks.html", plan=plan, sunrise=sunrise, sunset=sunset)

@app.route("/todo", methods=["POST"])
def add_todo():
    day = datetime.strptime(request.form.get("date"), "%Y-%m-%d").date()
    plan = load_plan(day)
    txt = (request.form.get("text") or "").strip()
    minutes_raw = (request.form.get("minutes") or "").strip()
    # Append minutes as a suffix like " 15min" if provided and valid
    if minutes_raw:
        try:
            m = int(minutes_raw)
            if m > 0:
                txt = f"{txt} {m}min" if txt else f"{m}min"
        except ValueError:
            pass  # ignore invalid minutes input
    if txt:
        plan["todos"].append(txt)
        save_plan(day, plan)
    return render_template("partials/todos.html", plan=plan)

@app.route("/todo/delete", methods=["POST"])
def delete_todo():
    day = datetime.strptime(request.form.get("date"), "%Y-%m-%d").date()
    idx = int(request.form.get("index"))
    plan = load_plan(day)
    if 0 <= idx < len(plan["todos"]):
        plan["todos"].pop(idx)
        save_plan(day, plan)
    return render_template("partials/todos.html", plan=plan)

@app.route("/block", methods=["POST"])
def set_block():
    day = datetime.strptime(request.form.get("date"), "%Y-%m-%d").date()
    time_key = request.form.get("time")
    text = (request.form.get("text") or "").strip()
    plan = load_plan(day)
    for b in plan["blocks"]:
        if b["time"] == time_key:
            b["activity"] = text
            break
    save_plan(day, plan)
    # Return just this single block cell (wrapped) for swap
    sunrise, sunset = get_sun_times(day)
    return render_template("partials/block_cell.html", time_key=time_key, activity=text, plan=plan, sunrise=sunrise, sunset=sunset)

@app.route("/block/clear", methods=["POST"])
def clear_block():
    day = datetime.strptime(request.form.get("date"), "%Y-%m-%d").date()
    time_key = request.form.get("time")
    plan = load_plan(day)
    for b in plan["blocks"]:
        if b["time"] == time_key:
            b["activity"] = ""
            break
    save_plan(day, plan)
    sunrise, sunset = get_sun_times(day)
    return render_template("partials/block_cell.html", time_key=time_key, activity="", plan=plan, sunrise=sunrise, sunset=sunset)

@app.route("/debug/suntime")
def debug_suntime():
    day = datetime.now(get_configured_tz()).date()
    sunrise, sunset = get_sun_times(day)
    lat = os.environ.get("LATITUDE", os.environ.get("LAT", ""))
    lon = os.environ.get("LONGITUDE", os.environ.get("LON", ""))
    info = {
        "date": date_str(day),
        "latitude": lat,
        "longitude": lon,
        "sunrise": sunrise,
        "sunset": sunset,
        "tz": str(get_configured_tz()),
        "data_dir": str(DATA_DIR),
        "cwd": os.getcwd(),
        "inside_docker": os.path.exists("/.dockerenv"),
    }
    return app.response_class(
        response=json.dumps(info, indent=2),
        status=200,
        mimetype='application/json'
    )

if __name__ == "__main__":
    logger.info("Starting Day Planner on port 8383; DATA_DIR=%s; LAT=%r LON=%r; TZ=%s; inside_docker=%s", DATA_DIR, os.environ.get("LATITUDE", os.environ.get("LAT", "")), os.environ.get("LONGITUDE", os.environ.get("LON", "")), datetime.now().astimezone().tzinfo, os.path.exists("/.dockerenv"))
    app.run(host="0.0.0.0", port=8383, debug=True)
