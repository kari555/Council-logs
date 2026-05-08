"""Simple JSON file-based cache for WCL data."""

import json
import time
from pathlib import Path

CACHE_DIR = Path("cache")


def _path(key: str) -> Path:
    return CACHE_DIR / f"{key}.json"


def get(key: str, ttl_seconds: int = None):
    """Read cached value. Returns None if missing or expired."""
    p = _path(key)
    if not p.exists():
        return None
    if ttl_seconds is not None:
        if time.time() - p.stat().st_mtime > ttl_seconds:
            return None
    return json.loads(p.read_text(encoding="utf-8"))


def set(key: str, data) -> None:
    """Write value to cache (atomic write via temp file)."""
    CACHE_DIR.mkdir(exist_ok=True)
    tmp = _path(key).with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(_path(key))


def exists(key: str) -> bool:
    return _path(key).exists()


def fight_key(report_code: str, fight_id: int) -> str:
    return f"fight_{report_code}_{fight_id}"


def load_index() -> list:
    """Load reports index. Returns [] if not found."""
    return get("reports_index") or []


def save_index(index: list) -> None:
    set("reports_index", index)


def load_parses_index() -> list:
    """Load flat parses index (one row per player per fight). Returns [] if not found."""
    return get("parses_index") or []


def save_parses_index(rows: list) -> None:
    set("parses_index", rows)


def load_attendance() -> list:
    """Load guild attendance rows. Returns [] if not found."""
    return get("attendance") or []


def save_attendance(rows: list) -> None:
    set("attendance", rows)


def load_guild_members() -> list:
    """Load guild member roster. Returns [] if not found."""
    return get("guild_members") or []


def save_guild_members(members: list) -> None:
    set("guild_members", members)
