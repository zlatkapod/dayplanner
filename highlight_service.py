from __future__ import annotations

import json
import os
from datetime import date as date_cls, datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Day Planner Highlight Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_DIR = Path(os.environ.get("DATA_DIR", "data"))


class Highlight(BaseModel):
    text: str
    source_url: str
    timestamp: Optional[str] = None


def _plan_path(day: date_cls) -> Path:
    return DATA_DIR / f"{day.strftime('%Y-%m-%d')}.json"


def _load_plan(day: date_cls) -> dict:
    p = _plan_path(day)
    if p.exists():
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return {
        "date": day.strftime("%Y-%m-%d"),
        "start": "09:00",
        "end": "21:00",
        "todos": [],
        "love_todos": [],
        "notes": [],
        "blocks": [],
        "note": "",
        "reflection": "",
        "dislike": "",
    }


def _save_plan(day: date_cls, plan: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(_plan_path(day), "w", encoding="utf-8") as f:
        json.dump(plan, f, indent=2, ensure_ascii=False)


@app.post("/capture")
async def capture(highlight: Highlight):
    if not highlight.text.strip():
        raise HTTPException(status_code=400, detail="text cannot be empty")

    today = date_cls.today()
    plan = _load_plan(today)

    ts = highlight.timestamp or datetime.now().strftime("%H:%M")
    note_md = f"[{highlight.text.strip()}]({highlight.source_url}) — {ts}"

    if not isinstance(plan.get("notes"), list):
        plan["notes"] = []
    plan["notes"].append(note_md)

    _save_plan(today, plan)
    return {"status": "ok", "date": str(today), "note": note_md}


@app.get("/health")
async def health():
    return {"status": "ok"}
