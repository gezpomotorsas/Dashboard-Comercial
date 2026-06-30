"""Carga variables de data/.env antes del updater y del servidor."""

from __future__ import annotations

import os
from pathlib import Path

from launcher.paths import REPO_DEFAULT, data_dir, ensure_data_layout, env_file_path, runtime_dir


def load_launcher_env() -> Path:
    """Lee data/.env en el proceso del launcher (actualizaciones, CLI)."""
    ensure_data_layout()
    env_path = env_file_path()

    if env_path.is_file():
        from dotenv import load_dotenv

        load_dotenv(env_path, override=False)

    os.environ.setdefault("DASHBOARD_DATA_DIR", str(data_dir()))
    os.environ.setdefault("DASHBOARD_ENV_FILE", str(env_path))
    os.environ.setdefault("DASHBOARD_RUNTIME_DIR", str(runtime_dir()))
    if not os.getenv("GITHUB_REPO", "").strip():
        os.environ.setdefault("GITHUB_REPO", REPO_DEFAULT)

    return env_path
