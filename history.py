"""Historial persistente de descargas."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

MAX_ENTRIES = 200
HISTORY_DIR = Path.home() / ".lion_yt_downloader"
HISTORY_FILE = HISTORY_DIR / "history.json"


def _ensure_dir() -> None:
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)


def load_history() -> list[dict]:
    _ensure_dir()
    if not HISTORY_FILE.is_file():
        return []
    try:
        data = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def save_history(entries: list[dict]) -> None:
    _ensure_dir()
    HISTORY_FILE.write_text(
        json.dumps(entries[:MAX_ENTRIES], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def add_entry(
    url: str,
    title: str,
    status: str,
    download_dir: str,
    format_type: str,
    codec_type: str,
) -> None:
    entries = load_history()
    entry = {
        "url": url,
        "title": title or url,
        "status": status,
        "download_dir": download_dir,
        "format": format_type,
        "codec": codec_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    entries = [e for e in entries if e.get("url") != url]
    entries.insert(0, entry)
    save_history(entries)


def clear_history() -> None:
    save_history([])
