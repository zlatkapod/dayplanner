
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
TOOLS_PATH = DATA_DIR / "tools.json"
QNA_PATH = DATA_DIR / "qna.json"
SUBSCRIPTIONS_PATH = DATA_DIR / "subscriptions.json"
TOPICS_PATH = DATA_DIR / "topics.json"

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
        slots.append({"time": dt.strftime("%H:%M"), "activity": "", "important": False})
        dt += timedelta(minutes=20)
    plan = {
        "date": date_str(day),
        "start": time_to_str(start),
        "end": time_to_str(end),
        "todos": [],
        "blocks": slots,
        "note": "",
        "reflection": "",
    }
    # if existing provided, try to keep activities where times still exist
    if existing:
        existing_acts = {b["time"]: b.get("activity", "") for b in existing.get("blocks", [])}
        existing_imp = {b["time"]: bool(b.get("important", False)) for b in existing.get("blocks", [])}
        plan["todos"] = existing.get("todos", [])
        plan["note"] = existing.get("note", existing.get("notes", ""))
        plan["reflection"] = existing.get("reflection", "")
        plan["topic"] = existing.get("topic", "")
        for b in plan["blocks"]:
            t = b["time"]
            if t in existing_acts:
                b["activity"] = existing_acts[t]
            if t in existing_imp:
                b["important"] = existing_imp[t]
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

# --- Tools data helpers ---

import secrets, re

def _new_id(prefix: str = "t") -> str:
    return f"{prefix}_{secrets.token_hex(4)}"

# --- Topics data helpers ---

def default_topics() -> dict:
    return {
        "topics": [
            # {"id": _new_id("tp"), "text": "Read about deep work", "category": "Productivity", "created": "2026-01-01"}
        ]
    }


def load_topics() -> dict:
    if TOPICS_PATH.exists():
        try:
            with open(TOPICS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = default_topics()
    else:
        data = default_topics()
    data.setdefault("topics", [])
    # normalize: ensure fields exist
    for t in data["topics"]:
        t.setdefault("id", _new_id("tp"))
        t.setdefault("text", "")
        t.setdefault("category", "Unsorted")
        t.setdefault("created", datetime.now(get_configured_tz()).date().strftime("%Y-%m-%d"))
    return data


def save_topics(data: dict) -> None:
    with open(TOPICS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# --- Q&A data helpers ---

def default_qna() -> dict:
    return {
        "questions": [
            # {"id": _new_id("q"), "text": "Example: Research gardening soil pH"}
        ],
        "links": [
            # {"id": _new_id("lnk"), "name": "ChatGPT thread about fasting", "url": "https://chat.openai.com/..."}
        ],
    }

def load_qna() -> dict:
    if QNA_PATH.exists():
        try:
            with open(QNA_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = default_qna()
    else:
        data = default_qna()
    # normalize
    data.setdefault("questions", [])
    data.setdefault("links", [])
    return data

def save_qna(data: dict) -> None:
    with open(QNA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def default_tools() -> dict:
    return {
        "categories": [
            {
                "id": _new_id("cat"),
                "name": "Languages",
                "items": [
                    {"id": _new_id("itm"), "name": "Duolingo", "url": "https://www.duolingo.com/", "keywords": ["dutch", "repetition", "fun"], "color": ""},
                    {"id": _new_id("itm"), "name": "DeepL", "url": "https://www.deepl.com/", "keywords": ["translate", "writing", "clarity"], "color": ""}
                ]
            },
            {
                "id": _new_id("cat"),
                "name": "Organization",
                "items": [
                    {"id": _new_id("itm"), "name": "Notion", "url": "https://www.notion.so/", "keywords": ["personal", "business", "robotics"], "color": ""},
                    {"id": _new_id("itm"), "name": "Trello", "url": "https://trello.com/", "keywords": ["kanban", "projects", "teams"], "color": ""}
                ]
            },
            {
                "id": _new_id("cat"),
                "name": "Development",
                "items": [
                    {"id": _new_id("itm"), "name": "GitHub", "url": "https://github.com/", "keywords": ["code", "repos", "issues"], "color": ""},
                    {"id": _new_id("itm"), "name": "Stack Overflow", "url": "https://stackoverflow.com/", "keywords": ["questions", "answers", "snippets"], "color": ""}
                ]
            }
        ]
    }

DEFAULT_TOOL_COLOR = "#9ca3af"  # neutral gray fallback

HEX_COLOR_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")

def _validate_hex_color(raw: str | None) -> str:
    s = (raw or "").strip()
    if not s:
        return DEFAULT_TOOL_COLOR
    if HEX_COLOR_RE.match(s):
        # normalize to 6-char if 3 provided
        if len(s) == 4:
            r, g, b = s[1], s[2], s[3]
            s = f"#{r}{r}{g}{g}{b}{b}"
        return s.lower()
    raise ValueError("Invalid color hex; expected #RGB or #RRGGBB")


def _migrate_tool_ids(data: dict) -> dict:
    changed = False
    cats = data.get("categories") or []
    for c in cats:
        if "id" not in c:
            c["id"] = _new_id("cat"); changed = True
        items = c.get("items") or []
        for it in items:
            if "id" not in it:
                it["id"] = _new_id("itm"); changed = True
            # normalize fields
            it.setdefault("keywords", [])
            it.setdefault("url", "")
            it.setdefault("name", "")
            # remove legacy logo field if present
            if "logo" in it:
                it.pop("logo", None); changed = True
            # ensure color exists
            if not it.get("color") or not isinstance(it.get("color"), str):
                it["color"] = DEFAULT_TOOL_COLOR; changed = True
            else:
                # validate existing color, fallback if invalid
                try:
                    it["color"] = _validate_hex_color(it.get("color"))
                except Exception:
                    it["color"] = DEFAULT_TOOL_COLOR; changed = True
    if changed:
        save_tools(data)
    return data

def load_tools() -> dict:
    if TOOLS_PATH.exists():
        try:
            with open(TOOLS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return _migrate_tool_ids(data)
                else:
                    logger.warning("tools.json root is not a dict; reinitializing")
        except Exception as e:
            logger.warning("Failed to read tools.json, reinitializing with defaults: %s", e)
    data = default_tools()
    save_tools(data)
    return data

def save_tools(data: dict) -> None:
    with open(TOOLS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# --- Subscriptions data helpers ---

def default_subscriptions() -> dict:
    return {"subscriptions": []}


def load_subscriptions() -> dict:
    if SUBSCRIPTIONS_PATH.exists():
        try:
            with open(SUBSCRIPTIONS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                if not isinstance(data, dict):
                    data = default_subscriptions()
        except Exception:
            data = default_subscriptions()
    else:
        data = default_subscriptions()
    # normalize
    subs = data.setdefault("subscriptions", [])
    for s in subs:
        s.setdefault("id", _new_id("sub"))
        s.setdefault("name", "")
        s.setdefault("url", "")
        s.setdefault("renewal_date", "")  # YYYY-MM-DD
        s.setdefault("is_active", True)
        s.setdefault("category", "Personal")
        # price stored as float
        try:
            s["price"] = float(s.get("price", 0) or 0)
        except Exception:
            s["price"] = 0.0
    return data


def save_subscriptions(data: dict) -> None:
    with open(SUBSCRIPTIONS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

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
        todos = plan.get("todos", [])
        # Find the first index of a "done" todo
        insert_idx = len(todos)
        for i, todo in enumerate(todos):
            if isinstance(todo, str) and todo.startswith("✓ "):
                insert_idx = i
                break
        todos.insert(insert_idx, txt)
        plan["todos"] = todos
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

@app.route("/todo/move_next", methods=["POST"])
def move_todo_next_day():
    """Move a todo item from the given day to the next day's todo list.
    Expects form fields: date (YYYY-MM-DD), index (0-based).
    Returns the updated todos partial for the current day.
    """
    try:
        day = datetime.strptime(request.form.get("date"), "%Y-%m-%d").date()
    except Exception:
        abort(400, "Bad date format, expected YYYY-MM-DD")
    try:
        idx = int(request.form.get("index"))
    except Exception:
        abort(400, "Bad index")

    plan_today = load_plan(day)
    if 0 <= idx < len(plan_today.get("todos", [])):
        # Remove from today
        todos_today = plan_today["todos"]
        todo_text = todos_today.pop(idx)
        save_plan(day, plan_today)
        
        # Add to next day
        next_day = day + timedelta(days=1)
        plan_tomorrow = load_plan(next_day)
        todos_tomorrow = plan_tomorrow.setdefault("todos", [])
        
        # Insert at the correct position (before first done)
        insert_idx = len(todos_tomorrow)
        for i, t in enumerate(todos_tomorrow):
            if isinstance(t, str) and t.startswith("✓ "):
                insert_idx = i
                break
        todos_tomorrow.insert(insert_idx, todo_text)
        save_plan(next_day, plan_tomorrow)
    # Always return updated today's todos
    return render_template("partials/todos.html", plan=plan_today)

@app.route("/todo/done", methods=["POST"])
def mark_todo_done():
    try:
        day = datetime.strptime(request.form.get("date"), "%Y-%m-%d").date()
    except Exception:
        abort(400, "Bad date format, expected YYYY-MM-DD")
    try:
        idx = int(request.form.get("index"))
    except Exception:
        abort(400, "Bad index")

    plan = load_plan(day)
    todos = plan.get("todos", [])
    if 0 <= idx < len(todos):
        item = todos.pop(idx)
        # If not already marked, prefix with a check mark and a space
        if not (isinstance(item, str) and item.startswith("✓ ")):
            item = f"✓ {item}".strip()
        # Append to end
        todos.append(item)
        plan["todos"] = todos
        save_plan(day, plan)
    return render_template("partials/todos.html", plan=plan)

@app.route("/todo/reorder_all", methods=["POST"])
def reorder_all_todos():
    """Replace the entire order of the todo list for a given day.
    Expects form fields: date (YYYY-MM-DD), order (JSON array of strings).
    Returns the updated todos partial (for HTMX swap).
    """
    try:
        day = datetime.strptime(request.form.get("date"), "%Y-%m-%d").date()
    except Exception:
        abort(400, "Bad date format, expected YYYY-MM-DD")

    order_raw = request.form.get("order") or "[]"
    try:
        new_order = json.loads(order_raw)
        if not isinstance(new_order, list):
            raise ValueError("order is not a list")
        # Coerce all entries to strings (defensive)
        new_order = [str(x) for x in new_order]
    except Exception:
        abort(400, "Bad order payload")

    plan = load_plan(day)
    plan["todos"] = new_order
    save_plan(day, plan)
    return render_template("partials/todos.html", plan=plan)

@app.route("/note", methods=["POST"])
def save_note():
    """Autosave the day-level note field from the sidebar textarea.
    Expects form fields: date (YYYY-MM-DD), text (string).
    Returns 204 No Content for HTMX with hx-swap="none".
    """
    try:
        day = datetime.strptime(request.form.get("date"), "%Y-%m-%d").date()
    except Exception:
        abort(400, "Bad date format, expected YYYY-MM-DD")
    text = (request.form.get("text") or "")
    plan = load_plan(day)
    plan["note"] = text
    save_plan(day, plan)
    return ("", 204)

@app.route("/reflection", methods=["POST"])
def save_reflection():
    """Autosave the 'What I liked about today?' reflection field.
    Expects form fields: date (YYYY-MM-DD), text (string).
    Returns 204 No Content for HTMX with hx-swap="none".
    """
    try:
        day = datetime.strptime(request.form.get("date"), "%Y-%m-%d").date()
    except Exception:
        abort(400, "Bad date format, expected YYYY-MM-DD")
    text = (request.form.get("text") or "")
    plan = load_plan(day)
    plan["reflection"] = text
    save_plan(day, plan)
    return ("", 204)

@app.route("/topic", methods=["POST"])
def save_topic():
    """Autosave the 'Topic of the Day' field.
    Expects form fields: date (YYYY-MM-DD), topic (string).
    Returns 204 No Content for HTMX.
    """
    try:
        day = datetime.strptime(request.form.get("date"), "%Y-%m-%d").date()
    except Exception:
        abort(400, "Bad date format, expected YYYY-MM-DD")
    topic = (request.form.get("topic") or "").strip()
    plan = load_plan(day)
    plan["topic"] = topic
    save_plan(day, plan)
    return render_template("partials/topic_input.html", plan=plan)

@app.route("/topic/toggle_lock", methods=["POST"])
def toggle_topic_lock():
    try:
        day = datetime.strptime(request.form.get("date"), "%Y-%m-%d").date()
    except Exception:
        abort(400, "Bad date format")
    plan = load_plan(day)
    plan["topic_locked"] = not bool(plan.get("topic_locked", False))
    save_plan(day, plan)
    return render_template("partials/topic_input.html", plan=plan)

@app.route("/block", methods=["POST"])
def set_block():
    day = datetime.strptime(request.form.get("date"), "%Y-%m-%d").date()
    time_key = request.form.get("time")
    text = (request.form.get("text") or "").strip()
    plan = load_plan(day)
    important = False
    for b in plan["blocks"]:
        if b["time"] == time_key:
            b["activity"] = text
            important = bool(b.get("important", False))
            break
    save_plan(day, plan)
    # Return just this single block cell (wrapped) for swap
    sunrise, sunset = get_sun_times(day)
    return render_template("partials/block_cell.html", time_key=time_key, activity=text, important=important, plan=plan, sunrise=sunrise, sunset=sunset)

@app.route("/block/toggle_important", methods=["POST"])
def toggle_important():
    day = datetime.strptime(request.form.get("date"), "%Y-%m-%d").date()
    time_key = request.form.get("time")
    plan = load_plan(day)
    activity = ""
    important = False
    for b in plan["blocks"]:
        if b["time"] == time_key:
            # flip
            b["important"] = not bool(b.get("important", False))
            important = b["important"]
            activity = b.get("activity", "")
            break
    save_plan(day, plan)
    sunrise, sunset = get_sun_times(day)
    return render_template("partials/block_cell.html", time_key=time_key, activity=activity, important=important, plan=plan, sunrise=sunrise, sunset=sunset)

@app.route("/tools", methods=["GET"])
def tools_page():
    # Use today's date for theme context only
    today = datetime.now(get_configured_tz()).date()
    sunrise, sunset = get_sun_times(today)
    is_dark = is_dark_mode(today, sunrise, sunset)
    tools = load_tools()
    return render_template("tools.html", tools=tools, is_dark=is_dark)

# --- Topics routes ---

@app.route("/topics", methods=["GET"])
def topics_page():
    tz = get_configured_tz()
    today = datetime.now(tz).date()
    sunrise, sunset = get_sun_times(today)
    is_dark = is_dark_mode(today, sunrise, sunset)
    data = load_topics()
    items = data.get("topics", [])
    # group by category
    grouped = {}
    for t in items:
        cat = (t.get("category") or "Unsorted").strip() or "Unsorted"
        grouped.setdefault(cat, []).append(t)
    # sort categories alphabetically, items by created desc then text
    for cat, arr in grouped.items():
        arr.sort(key=lambda x: (x.get("created", ""), x.get("text", "")))
        arr.reverse()
    categories = sorted(grouped.keys(), key=lambda s: s.lower())
    return render_template("topics.html", grouped=grouped, categories=categories, is_dark=is_dark, today=date_str(today))

@app.route("/topics/add", methods=["POST"]) 
def topics_add():
    text = (request.form.get("text") or "").strip()
    category = (request.form.get("category") or "Unsorted").strip() or "Unsorted"
    if not text:
        return ("Missing topic text", 400)
    tz = get_configured_tz()
    created = datetime.now(tz).date().strftime("%Y-%m-%d")
    data = load_topics()
    data.setdefault("topics", []).append({
        "id": _new_id("tp"),
        "text": text,
        "category": category,
        "created": created,
    })
    save_topics(data)
    resp = app.response_class("", status=204)
    resp.headers["HX-Redirect"] = url_for("topics_page")
    return resp

@app.route("/topics/delete", methods=["POST"]) 
def topics_delete():
    tid = (request.form.get("id") or "").strip()
    if not tid:
        return ("Missing id", 400)
    data = load_topics()
    arr = data.get("topics", [])
    new_arr = [t for t in arr if t.get("id") != tid]
    if len(new_arr) == len(arr):
        return ("Not found", 404)
    data["topics"] = new_arr
    save_topics(data)
    resp = app.response_class("", status=204)
    resp.headers["HX-Redirect"] = url_for("topics_page")
    return resp

# --- WordCount routes ---

@app.route("/wordcount", methods=["GET"])
def wordcount_page():
    tz = get_configured_tz()
    today = datetime.now(tz).date()
    sunrise, sunset = get_sun_times(today)
    is_dark = is_dark_mode(today, sunrise, sunset)
    return render_template("wordcount.html", is_dark=is_dark)

# --- Subscriptions routes ---

@app.route("/subscriptions", methods=["GET"])
def subscriptions_page():
    tz = get_configured_tz()
    today = datetime.now(tz).date()
    sunrise, sunset = get_sun_times(today)
    is_dark = is_dark_mode(today, sunrise, sunset)
    data = load_subscriptions()
    subs = data.get("subscriptions", [])

    def parse_date(s: str) -> date_cls | None:
        try:
            return datetime.strptime((s or "").strip(), "%Y-%m-%d").date()
        except Exception:
            return None

    # annotate with delta info for sorting/rendering
    annotated = []
    for s in subs:
        d = parse_date(s.get("renewal_date", ""))
        if d is None:
            delta = 10**9  # push unknowns to the end
            future = True
            days_abs = delta
        else:
            delta = (d - today).days
            future = delta >= 0
            days_abs = abs(delta)
        annotated.append({**s, "_delta": delta, "_future": future, "_days_abs": days_abs})

    # Sorting helper: group future first; then by delta/abs(delta); then name
    def sort_key(s: dict):
        future_group = 0 if s.get("_future", True) else 1
        primary = s.get("_delta", 10**9) if future_group == 0 else s.get("_days_abs", 10**9)
        return (future_group, primary, s.get("name", ""))

    active_subs = [s for s in annotated if s.get("is_active", True)]
    inactive_subs = [s for s in annotated if not s.get("is_active", True)]
    active_subs.sort(key=sort_key)
    inactive_subs.sort(key=sort_key)

    return render_template("subscriptions.html", subs_active=active_subs, subs_inactive=inactive_subs, is_dark=is_dark, today=date_str(today))

@app.route("/subscriptions/toggle", methods=["POST"]) 
def subscriptions_toggle():
    sid = (request.form.get("id") or "").strip()
    is_active_raw = request.form.get("is_active")
    data = load_subscriptions()
    subs = data.get("subscriptions", [])
    target = None
    for s in subs:
        if s.get("id") == sid:
            target = s
            break
    if not target:
        return ("Subscription not found", 404)

    if is_active_raw is None:
        target["is_active"] = not bool(target.get("is_active", True))
    else:
        val = str(is_active_raw).strip().lower()
        target["is_active"] = val in ("1", "true", "on", "yes")

    save_subscriptions(data)

    resp = app.response_class("", status=204)
    resp.headers["HX-Redirect"] = url_for("subscriptions_page")
    return resp

@app.route("/subscriptions/delete", methods=["POST"])
def subscriptions_delete():
    sid = (request.form.get("id") or "").strip()
    data = load_subscriptions()
    subs = data.get("subscriptions", [])
    new_subs = [s for s in subs if s.get("id") != sid]
    if len(new_subs) == len(subs):
        return ("Subscription not found", 404)
    data["subscriptions"] = new_subs
    save_subscriptions(data)
    resp = app.response_class("", status=204)
    resp.headers["HX-Redirect"] = url_for("subscriptions_page")
    return resp

@app.route("/subscriptions/update", methods=["POST"])
def subscriptions_update():
    sid = (request.form.get("id") or "").strip()
    name = (request.form.get("name") or "").strip()
    url_val = (request.form.get("url") or "").strip()
    renewal_date = (request.form.get("renewal_date") or "").strip()
    price_raw = (request.form.get("price") or "").strip()
    is_active_raw = request.form.get("is_active")
    category = (request.form.get("category") or "Personal").strip()

    if not name:
        return ("Missing name", 400)
    try:
        datetime.strptime(renewal_date, "%Y-%m-%d")
    except Exception:
        return ("Bad renewal date; expected YYYY-MM-DD", 400)
    try:
        price = float(price_raw) if price_raw != "" else 0.0
    except Exception:
        return ("Price must be a number", 400)

    data = load_subscriptions()
    subs = data.get("subscriptions", [])
    target = None
    for s in subs:
        if s.get("id") == sid:
            target = s
            break
    if not target:
        return ("Subscription not found", 404)

    target["name"] = name
    target["url"] = url_val
    target["renewal_date"] = renewal_date
    target["price"] = price
    target["category"] = category
    if is_active_raw is not None:
        val = str(is_active_raw).strip().lower()
        target["is_active"] = val in ("1", "true", "on", "yes")

    save_subscriptions(data)
    resp = app.response_class("", status=204)
    resp.headers["HX-Redirect"] = url_for("subscriptions_page")
    return resp

@app.route("/subscriptions/add", methods=["POST"])
def subscriptions_add():
    name = (request.form.get("name") or "").strip()
    url_val = (request.form.get("url") or "").strip()
    renewal_date = (request.form.get("renewal_date") or "").strip()
    is_active_raw = request.form.get("is_active")
    price_raw = (request.form.get("price") or "").strip()
    category = (request.form.get("category") or "Personal").strip()

    if not name:
        return ("Missing name", 400)
    # renewal date required
    try:
        datetime.strptime(renewal_date, "%Y-%m-%d")
    except Exception:
        return ("Bad renewal date; expected YYYY-MM-DD", 400)

    if url_val and not (url_val.startswith("http://") or url_val.startswith("https://")):
        return ("URL must start with http:// or https://", 400)

    try:
        price = float(price_raw) if price_raw != "" else 0.0
    except Exception:
        return ("Price must be a number", 400)

    is_active = bool(is_active_raw)

    data = load_subscriptions()
    data.setdefault("subscriptions", []).append({
        "id": _new_id("sub"),
        "name": name,
        "url": url_val,
        "renewal_date": renewal_date,
        "is_active": is_active,
        "price": price,
        "category": category,
    })
    save_subscriptions(data)

    resp = app.response_class("", status=204)
    resp.headers["HX-Redirect"] = url_for("subscriptions_page")
    return resp

# --- Q&A routes ---

@app.route("/qna", methods=["GET"])
def qna_page():
    # Theme context uses today
    today = datetime.now(get_configured_tz()).date()
    sunrise, sunset = get_sun_times(today)
    is_dark = is_dark_mode(today, sunrise, sunset)
    qna = load_qna()
    return render_template("qna.html", qna=qna, is_dark=is_dark)

@app.route("/qna/question/add", methods=["POST"])
def qna_add_question():
    text = (request.form.get("text") or "").strip()
    if not text:
        return ("Missing text", 400)
    data = load_qna()
    # prepend
    data.setdefault("questions", []).insert(0, {"id": _new_id("q"), "text": text})
    save_qna(data)
    return render_template("partials/qna_questions.html", qna=data)

@app.route("/qna/question/delete", methods=["POST"])
def qna_delete_question():
    qid = (request.form.get("id") or "").strip()
    data = load_qna()
    qs = data.setdefault("questions", [])
    idx = next((i for i, q in enumerate(qs) if q.get("id") == qid), -1)
    if idx >= 0:
        qs.pop(idx)
        save_qna(data)
    return render_template("partials/qna_questions.html", qna=data)

@app.route("/qna/link/add", methods=["POST"])
def qna_add_link():
    name = (request.form.get("name") or "").strip()
    url_val = (request.form.get("url") or "").strip()
    if not name or not url_val:
        return ("Missing name or url", 400)
    if not (url_val.startswith("http://") or url_val.startswith("https://")):
        return ("URL must start with http:// or https://", 400)
    data = load_qna()
    data.setdefault("links", []).insert(0, {"id": _new_id("lnk"), "name": name, "url": url_val})
    save_qna(data)
    return render_template("partials/qna_links.html", qna=data)

@app.route("/qna/link/delete", methods=["POST"])
def qna_delete_link():
    lid = (request.form.get("id") or "").strip()
    data = load_qna()
    ls = data.setdefault("links", [])
    idx = next((i for i, l in enumerate(ls) if l.get("id") == lid), -1)
    if idx >= 0:
        ls.pop(idx)
        save_qna(data)
    return render_template("partials/qna_links.html", qna=data)

@app.route("/tools/category/add", methods=["POST"])
def tools_add_category():
    name = (request.form.get("name") or "").strip()
    if not name:
        return ("Missing category name", 400)
    data = load_tools()
    # Avoid duplicate names (case-insensitive)
    existing = next((c for c in data.get("categories", []) if c.get("name", "").strip().lower() == name.lower()), None)
    if existing is None:
        data.setdefault("categories", []).append({"id": _new_id("cat"), "name": name, "items": []})
        save_tools(data)
    resp = app.response_class("", status=204)
    resp.headers["HX-Redirect"] = url_for("tools_page")
    return resp


def _find_category(data: dict, cat_id: str) -> dict | None:
    return next((c for c in data.get("categories", []) if c.get("id") == cat_id), None)


def _parse_tags(raw: str) -> list[str]:
    parts = [p.strip() for p in (raw or "").split(",")]
    return [p for p in parts if p]




@app.route("/tools/item/add", methods=["POST"])
def tools_item_add():
    name = (request.form.get("name") or "").strip()
    url_val = (request.form.get("url") or "").strip()
    cat_id = (request.form.get("category_id") or "").strip()
    tags_raw = (request.form.get("tags") or "").strip()
    color_raw = (request.form.get("color") or "").strip()
    if not name or not url_val or not cat_id:
        return ("Missing required fields", 400)
    if not (url_val.startswith("http://") or url_val.startswith("https://")):
        return ("URL must start with http:// or https://", 400)
    try:
        color = _validate_hex_color(color_raw)
    except ValueError as e:
        return (str(e), 400)
    data = load_tools()
    cat = _find_category(data, cat_id)
    if cat is None:
        return ("Category not found", 400)
    item = {
        "id": _new_id("itm"),
        "name": name,
        "url": url_val,
        "keywords": _parse_tags(tags_raw),
        "color": color,
    }
    cat.setdefault("items", []).append(item)
    save_tools(data)
    resp = app.response_class("", status=204)
    resp.headers["HX-Redirect"] = url_for("tools_page")
    return resp


@app.route("/tools/item/edit", methods=["GET"])
def tools_item_edit():
    item_id = (request.args.get("item_id") or "").strip()
    cat_id = (request.args.get("category_id") or "").strip()
    if not item_id or not cat_id:
        return ("Missing item or category id", 400)
    data = load_tools()
    cat = _find_category(data, cat_id)
    if cat is None:
        return ("Category not found", 400)
    item = next((it for it in cat.get("items", []) if it.get("id") == item_id), None)
    if item is None:
        # try find across categories in case moved
        for c in data.get("categories", []):
            item = next((it for it in c.get("items", []) if it.get("id") == item_id), None)
            if item is not None:
                cat = c
                break
    if item is None:
        return ("Item not found", 404)
    return render_template(
        "partials/tool_item_edit.html",
        item=item,
        current_category_id=cat.get("id"),
        categories=data.get("categories", []),
    )


@app.route("/tools/item/update", methods=["POST"])
def tools_item_update():
    item_id = (request.form.get("item_id") or "").strip()
    from_cat_id = (request.form.get("from_category_id") or "").strip()
    to_cat_id = (request.form.get("category_id") or from_cat_id).strip()
    name = (request.form.get("name") or "").strip()
    url_val = (request.form.get("url") or "").strip()
    tags_raw = (request.form.get("tags") or "").strip()
    color_raw = (request.form.get("color") or "").strip()
    if not item_id or not from_cat_id:
        return ("Missing item or category id", 400)
    if not name or not url_val:
        return ("Missing name or url", 400)
    if not (url_val.startswith("http://") or url_val.startswith("https://")):
        return ("URL must start with http:// or https://", 400)
    try:
        color = _validate_hex_color(color_raw)
    except ValueError as e:
        return (str(e), 400)
    data = load_tools()
    from_cat = _find_category(data, from_cat_id)
    if from_cat is None:
        return ("Source category not found", 400)
    # locate item
    items = from_cat.get("items", [])
    idx = next((i for i, it in enumerate(items) if it.get("id") == item_id), -1)
    if idx == -1:
        return ("Item not found", 404)
    it = items[idx]
    # If category changes, move it
    if to_cat_id != from_cat_id:
        to_cat = _find_category(data, to_cat_id)
        if to_cat is None:
            return ("Destination category not found", 400)
        # remove from old
        items.pop(idx)
        it = {**it}
        to_cat.setdefault("items", []).append(it)
        from_cat = to_cat  # for response consistency
    # update fields
    it["name"] = name
    it["url"] = url_val
    it["keywords"] = _parse_tags(tags_raw)
    it["color"] = color
    save_tools(data)
    resp = app.response_class("", status=204)
    resp.headers["HX-Redirect"] = url_for("tools_page")
    return resp


@app.route("/tools/item/delete", methods=["POST"])
def tools_item_delete():
    item_id = (request.form.get("item_id") or "").strip()
    cat_id = (request.form.get("category_id") or "").strip()
    if not item_id or not cat_id:
        return ("Missing item or category id", 400)
    data = load_tools()
    cat = _find_category(data, cat_id)
    if cat is None:
        return ("Category not found", 400)
    items = cat.get("items", [])
    new_items = [it for it in items if it.get("id") != item_id]
    cat["items"] = new_items
    save_tools(data)
    resp = app.response_class("", status=204)
    resp.headers["HX-Redirect"] = url_for("tools_page")
    return resp

@app.route("/tools/category/delete", methods=["POST"])
def tools_category_delete():
    cat_id = (request.form.get("category_id") or "").strip()
    if not cat_id:
        return ("Missing category id", 400)
    data = load_tools()
    cat = _find_category(data, cat_id)
    if cat is None:
        return ("Category not found", 404)
    # Prevent deletion if category contains items
    items = cat.get("items") or []
    if len(items) > 0:
        return ("Category not empty", 400)
    # Delete the category
    data["categories"] = [c for c in data.get("categories", []) if c.get("id") != cat_id]
    save_tools(data)
    resp = app.response_class("", status=204)
    resp.headers["HX-Redirect"] = url_for("tools_page")
    return resp

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
