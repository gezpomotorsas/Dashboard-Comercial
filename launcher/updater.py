"""Descarga de actualizaciones desde GitHub Releases o git."""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from launcher.paths import REPO_DEFAULT, RUNTIME_ASSET, runtime_dir
from launcher.version_store import read_version, write_version

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"


@dataclass
class UpdateStatus:
    local_commit: str
    remote_commit: str
    update_available: bool
    source: str
    release_tag: str | None = None
    release_name: str | None = None
    message: str = ""


@dataclass
class UpdateResult:
    ok: bool
    message: str
    previous_commit: str | None = None
    new_commit: str | None = None


def _repo_slug() -> str:
    return os.getenv("GITHUB_REPO", read_version().get("repo") or REPO_DEFAULT)


def _auth_headers() -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "DashboardComercial-Updater",
    }
    token = os.getenv("GITHUB_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _http_json(url: str) -> Any:
    request = Request(url, headers=_auth_headers())
    with urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def _download(url: str, destination: Path, *, api_asset: bool = False) -> None:
    headers = _auth_headers()
    if api_asset:
        headers["Accept"] = "application/octet-stream"
    request = Request(url, headers=headers)
    with urlopen(request, timeout=300) as response, destination.open("wb") as handle:
        shutil.copyfileobj(response, handle)


def _github_error_hint(exc: HTTPError) -> str:
    if exc.code != 404:
        return str(exc)
    if os.getenv("GITHUB_TOKEN", "").strip():
        return (
            f"{exc} — el repo existe pero no hay release con runtime.zip en main, "
            "o el token no tiene permiso de lectura."
        )
    return (
        f"{exc} — el repo gezpomotorsas/Dashboard-Comercial es privado. "
        "Añade GITHUB_TOKEN en data\\.env (permiso read:packages o contents:read)."
    )


def fetch_remote_main_commit() -> str:
    repo = _repo_slug()
    payload = _http_json(f"{GITHUB_API}/repos/{repo}/commits/main")
    return str(payload["sha"])


def fetch_latest_release() -> dict[str, Any] | None:
    repo = _repo_slug()
    try:
        return _http_json(f"{GITHUB_API}/repos/{repo}/releases/latest")
    except HTTPError as exc:
        if exc.code == 404:
            return None
        raise


def _release_commit(release: dict[str, Any]) -> str | None:
    body = release.get("body") or ""
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("commit:"):
            return stripped.split(":", 1)[1].strip()
    tag = release.get("tag_name")
    if isinstance(tag, str) and tag.startswith("build-"):
        return tag.removeprefix("build-")
    return None


def _runtime_asset(release: dict[str, Any]) -> tuple[str, bool] | None:
    """URL de descarga y si requiere Accept application/octet-stream (API asset)."""
    for asset in release.get("assets") or []:
        if asset.get("name") != RUNTIME_ASSET:
            continue
        api_url = asset.get("url")
        if isinstance(api_url, str) and api_url:
            return api_url, True
        browser_url = asset.get("browser_download_url")
        if isinstance(browser_url, str) and browser_url:
            return browser_url, False
    return None


def _runtime_asset_url(release: dict[str, Any]) -> str | None:
    found = _runtime_asset(release)
    return found[0] if found else None


def check_for_update() -> UpdateStatus:
    local = read_version()
    local_commit = str(local.get("commit") or "local")

    try:
        remote_commit = fetch_remote_main_commit()
    except HTTPError as exc:
        return UpdateStatus(
            local_commit=local_commit,
            remote_commit=local_commit,
            update_available=False,
            source="error",
            message=f"No se pudo consultar GitHub: {_github_error_hint(exc)}",
        )
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        return UpdateStatus(
            local_commit=local_commit,
            remote_commit=local_commit,
            update_available=False,
            source="error",
            message=f"No se pudo consultar GitHub: {exc}",
        )

    release = fetch_latest_release()
    release_commit = _release_commit(release) if release else None
    asset_url = _runtime_asset_url(release) if release else None

    if release_commit and asset_url:
        update_available = release_commit != local_commit or local_commit == "local"
        tag = str(release.get("tag_name") or "")
        return UpdateStatus(
            local_commit=local_commit,
            remote_commit=release_commit,
            update_available=update_available,
            source="release",
            release_tag=tag,
            release_name=str(release.get("name") or tag),
            message="Hay release con runtime.zip" if update_available else "Ya tienes la última release",
        )

    update_available = remote_commit != local_commit and local_commit != "local"
    return UpdateStatus(
        local_commit=local_commit,
        remote_commit=remote_commit,
        update_available=update_available,
        source="commit",
        message=(
            "Hay cambios en GitHub pero falta release con runtime.zip"
            if update_available
            else "Sin cambios en main"
        ),
    )


def _copy_tree(source: Path, destination: Path) -> None:
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)


def _apply_runtime_zip(zip_path: Path, target_runtime: Path) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        temp_root = Path(tmp)
        with zipfile.ZipFile(zip_path, "r") as archive:
            archive.extractall(temp_root)

        extracted_dirs = [path for path in temp_root.iterdir() if path.is_dir()]
        if len(extracted_dirs) == 1 and (extracted_dirs[0] / "app").is_dir():
            payload_root = extracted_dirs[0]
        elif (temp_root / "app").is_dir():
            payload_root = temp_root
        else:
            raise RuntimeError("El zip de runtime no tiene la estructura esperada (app/, frontend/dist/)")

        for name in ("app", "frontend", "pyproject.toml", "version.json"):
            src = payload_root / name
            if not src.exists():
                continue
            dst = target_runtime / name
            if src.is_dir():
                _copy_tree(src, dst)
            else:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)


def apply_update_from_release() -> UpdateResult:
    status = check_for_update()
    previous = status.local_commit

    if not status.update_available:
        return UpdateResult(ok=True, message=status.message or "No hay actualizaciones", previous_commit=previous)

    release = fetch_latest_release()
    if not release:
        return UpdateResult(ok=False, message="No hay releases publicadas en GitHub", previous_commit=previous)

    asset = _runtime_asset(release)
    release_commit = _release_commit(release)
    if not asset or not release_commit:
        return UpdateResult(
            ok=False,
            message="La última release no incluye runtime.zip o commit en la descripción",
            previous_commit=previous,
        )

    asset_url, api_asset = asset
    target = runtime_dir()
    target.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        zip_path = Path(tmp) / RUNTIME_ASSET
        logger.info("Descargando %s", asset_url)
        _download(asset_url, zip_path, api_asset=api_asset)
        _apply_runtime_zip(zip_path, target)

    write_version(
        release_commit,
        version=str(release.get("tag_name") or read_version().get("version") or "0.1.0"),
        path=target / "version.json",
    )
    return UpdateResult(
        ok=True,
        message=f"Actualizado a {release.get('tag_name')} ({release_commit[:7]})",
        previous_commit=previous,
        new_commit=release_commit,
    )


def apply_update_with_git() -> UpdateResult:
    root = runtime_dir().parent if (runtime_dir().name == "runtime") else runtime_dir()
    if not (root / ".git").is_dir():
        return UpdateResult(ok=False, message="Git no está disponible en esta carpeta")

    previous = read_version().get("commit", "local")
    branch = os.getenv("UPDATE_BRANCH", "main")
    commands = [
        ["git", "fetch", "origin", branch],
        ["git", "checkout", branch],
        ["git", "pull", "--ff-only", "origin", branch],
    ]
    for cmd in commands:
        completed = subprocess.run(cmd, cwd=root, capture_output=True, text=True, check=False)
        if completed.returncode != 0:
            return UpdateResult(
                ok=False,
                message=f"Falló {' '.join(cmd)}: {completed.stderr or completed.stdout}",
                previous_commit=str(previous),
            )

    try:
        new_commit = fetch_remote_main_commit()
    except (HTTPError, URLError, TimeoutError):
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        )
        new_commit = completed.stdout.strip()

    write_version(new_commit, path=runtime_dir() / "version.json")
    return UpdateResult(
        ok=True,
        message=f"Actualizado con git pull ({new_commit[:7]})",
        previous_commit=str(previous),
        new_commit=new_commit,
    )


def apply_update(prefer_git: bool = False) -> UpdateResult:
    if prefer_git or os.getenv("UPDATE_SOURCE", "").lower() == "git":
        git_result = apply_update_with_git()
        if git_result.ok:
            return git_result
    return apply_update_from_release()
