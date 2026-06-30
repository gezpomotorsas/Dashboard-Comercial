"""Rutas de instalación del ejecutable."""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_DEFAULT = "gezpomotorsas/Dashboard-Comercial"
RUNTIME_DIR_NAME = "runtime"
DATA_DIR_NAME = "data"
VERSION_FILE = "version.json"
RUNTIME_ASSET = "runtime.zip"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def install_root() -> Path:
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def runtime_dir() -> Path:
    env = os.getenv("DASHBOARD_RUNTIME_DIR")
    if env:
        return Path(env).resolve()
    root = install_root()
    bundled = root / RUNTIME_DIR_NAME
    if bundled.is_dir():
        return bundled
    return root


def data_dir() -> Path:
    env = os.getenv("DASHBOARD_DATA_DIR")
    if env:
        return Path(env).resolve()
    return install_root() / DATA_DIR_NAME


def version_file() -> Path:
    local = runtime_dir() / VERSION_FILE
    if local.is_file():
        return local
    return install_root() / VERSION_FILE


def frontend_dist_dir() -> Path:
    return runtime_dir() / "frontend" / "dist"


def _env_file_is_configured(path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if stripped.startswith("SUPABASE_URL="):
                return bool(stripped.split("=", 1)[1].strip())
    except OSError:
        return False
    return False


def env_file_path() -> Path:
    custom = os.getenv("DASHBOARD_ENV_FILE")
    if custom:
        return Path(custom).resolve()

    data_env = data_dir() / ".env"
    root_env = install_root() / ".env"

    if _env_file_is_configured(data_env):
        return data_env
    if _env_file_is_configured(root_env):
        return root_env
    if data_env.is_file():
        return data_env
    if root_env.is_file():
        return root_env
    return data_env


def ensure_data_layout() -> None:
    data_dir().mkdir(parents=True, exist_ok=True)
    target = data_dir() / ".env"
    if target.is_file():
        return
    root_env = install_root() / ".env"
    example = install_root() / ".env.example"
    if _env_file_is_configured(root_env):
        target.write_text(root_env.read_text(encoding="utf-8"), encoding="utf-8")
    elif example.is_file():
        target.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")
