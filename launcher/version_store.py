"""Lectura y escritura de version.json local."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from launcher.paths import REPO_DEFAULT, version_file


def read_version(path: Path | None = None) -> dict[str, Any]:
    target = path or version_file()
    if not target.is_file():
        return {"version": "0.0.0", "commit": "local", "repo": REPO_DEFAULT}
    return json.loads(target.read_text(encoding="utf-8"))


def write_version(
    commit: str,
    *,
    version: str | None = None,
    path: Path | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    target = path or version_file()
    current = read_version(target)
    payload: dict[str, Any] = {
        "version": version or current.get("version") or "0.1.0",
        "commit": commit,
        "built_at": datetime.now(UTC).isoformat(),
        "repo": current.get("repo") or REPO_DEFAULT,
    }
    if extra:
        payload.update(extra)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload
