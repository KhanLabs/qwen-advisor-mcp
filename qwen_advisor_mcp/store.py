"""Per-project persistence of Qwen consultation history.

Each project's history lives at ~/.qwen-advisor/sessions/<slug>.json as a
plain list of {"role", "content"} messages (no system prompt — that's added
fresh each call). Capped to MAX_EXCHANGES user/assistant pairs so a
long-running project doesn't quietly balloon token usage.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

MAX_EXCHANGES = 12

_SESSIONS_DIR = Path.home() / ".qwen-advisor" / "sessions"
_SLUG_RE = re.compile(r"[^A-Za-z0-9_-]+")


def _session_path(project_id: str) -> Path:
    project_id = project_id.strip() or "default"
    slug = _SLUG_RE.sub("_", project_id)[:80]
    digest = hashlib.sha1(project_id.encode("utf-8")).hexdigest()[:8]
    _SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    return _SESSIONS_DIR / f"{slug}-{digest}.json"


def load_history(project_id: str) -> list[dict[str, str]]:
    """Return the saved message history for *project_id*, or [] if none/corrupt."""
    path = _session_path(project_id)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    if not isinstance(data, list):
        return []
    return [m for m in data if isinstance(m, dict) and "role" in m and "content" in m]


def append_exchange(
    project_id: str, user_content: str, assistant_content: str
) -> list[dict[str, str]]:
    """Append a user/assistant turn, trim to MAX_EXCHANGES pairs, and save.

    Returns the trimmed history that was saved.
    """
    history = load_history(project_id)
    history.append({"role": "user", "content": user_content})
    history.append({"role": "assistant", "content": assistant_content})

    max_messages = MAX_EXCHANGES * 2
    if len(history) > max_messages:
        history = history[-max_messages:]

    path = _session_path(project_id)
    path.write_text(json.dumps(history, indent=2), encoding="utf-8")
    return history


__all__ = ["MAX_EXCHANGES", "append_exchange", "load_history"]
