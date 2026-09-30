"""Simple, transparent long-term memory stored as JSON next to the app.

Unlike the original JARVIS (which saved silently), Ultron tells you when it saves
or forgets something, and you can view or clear it any time.
"""
import json
from datetime import datetime
from pathlib import Path

_PATH = Path(__file__).resolve().parent.parent / "memory.json"
_CATS = ("identity", "preferences", "projects", "people", "notes")


def _load() -> dict:
    if not _PATH.exists():
        return {c: {} for c in _CATS}
    try:
        data = json.loads(_PATH.read_text(encoding="utf-8"))
        for c in _CATS:
            data.setdefault(c, {})
        return data
    except Exception:
        return {c: {} for c in _CATS}


def _save(data: dict):
    _PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def remember(category: str, key: str, value: str) -> str:
    cat = category if category in _CATS else "notes"
    if not key or not value:
        return "I need both a key and a value to remember."
    data = _load()
    data[cat][key.strip()] = {"value": value.strip(), "updated": datetime.now().strftime("%Y-%m-%d")}
    _save(data)
    return f"Saved to memory ({cat}): {key} = {value}"


def recall(query: str = "") -> str:
    data = _load()
    items = [(c, k, e["value"]) for c in _CATS for k, e in data[c].items()]
    if not items:
        return "I don't have anything in memory yet."
    if query:
        q = query.lower()
        items = [i for i in items if q in i[1].lower() or q in i[2].lower() or q in i[0]]
        if not items:
            return f"Nothing in memory about '{query}'."
    return "\n".join(f"[{c}] {k}: {v}" for c, k, v in items)


def forget(key: str = "", clear_all: bool = False) -> str:
    data = _load()
    if clear_all:
        _save({c: {} for c in _CATS})
        return "Cleared all of memory."
    if not key:
        return "Tell me what to forget, or set clear_all to wipe everything."
    removed = []
    for c in _CATS:
        if key in data[c]:
            del data[c][key]
            removed.append(key)
    _save(data)
    return f"Forgot: {key}" if removed else f"Nothing stored under '{key}'."


def memory_for_prompt() -> str:
    """A compact block for the system prompt so the assistant uses what it knows."""
    data = _load()
    lines = []
    for c in _CATS:
        for k, e in list(data[c].items())[:15]:
            lines.append(f"- {k}: {e['value']}")
    if not lines:
        return ""
    return "What you remember about the user (use naturally, don't recite):\n" + "\n".join(lines[:40])
