"""Punto de entrada del ejecutable Dashboard Comercial."""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
import webbrowser
from pathlib import Path

from launcher.env import load_launcher_env
from launcher.paths import ensure_data_layout, install_root, is_frozen
from launcher.server import configure_runtime_env, has_frontend_bundle, run_server, spawn_server_subprocess
from launcher.updater import apply_update, check_for_update

logger = logging.getLogger(__name__)

RESTART_EXIT_CODE = 42
DEFAULT_PORT = 8765


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )


def _auto_update_on_start() -> None:
    if os.getenv("AUTO_UPDATE_ON_START", "true").lower() in {"0", "false", "no"}:
        return
    status = check_for_update()
    if not status.update_available:
        logger.info("Actualización: %s", status.message)
        return
    if status.source == "commit" and status.message.startswith("Hay cambios"):
        logger.warning(status.message)
        return
    logger.info("Actualización disponible (%s). Descargando…", status.release_tag or status.remote_commit[:7])
    result = apply_update()
    if result.ok:
        logger.info(result.message)
    else:
        logger.error(result.message)


def _open_browser(port: int) -> None:
    if os.getenv("OPEN_BROWSER", "true").lower() in {"0", "false", "no"}:
        return
    url = f"http://127.0.0.1:{port}/"
    time.sleep(1.2)
    webbrowser.open(url)


def run_launcher(port: int) -> int:
    _setup_logging()
    load_launcher_env()
    logger.info("Dashboard Comercial — carpeta: %s", install_root())
    _auto_update_on_start()

    if not has_frontend_bundle() and not (install_root() / "app").is_dir() and not (install_root() / "runtime" / "app").is_dir():
        logger.error("No se encontró runtime/app ni frontend/dist. Reinstala o actualiza desde GitHub.")
        return 1

    while True:
        logger.info("Iniciando servidor en http://127.0.0.1:%s", port)
        process = spawn_server_subprocess(port)
        _open_browser(port)
        code = process.wait()
        if code == RESTART_EXIT_CODE:
            logger.info("Reiniciando tras actualización…")
            continue
        return code


def run_serve(port: int) -> None:
    _setup_logging()
    configure_runtime_env(port)
    run_server(port)


def main() -> None:
    parser = argparse.ArgumentParser(description="Dashboard Comercial Gezpomotor")
    parser.add_argument("--serve", action="store_true", help="Modo interno: solo API/web")
    parser.add_argument("--port", type=int, default=int(os.getenv("DASHBOARD_PORT", DEFAULT_PORT)))
    parser.add_argument("--check-update", action="store_true", help="Comprobar actualizaciones y salir")
    parser.add_argument("--apply-update", action="store_true", help="Descargar actualización y salir")
    args = parser.parse_args()

    if not args.serve:
        load_launcher_env()

    if args.check_update:
        status = check_for_update()
        print(status.message)
        print(f"local={status.local_commit[:7]} remote={status.remote_commit[:7]} available={status.update_available}")
        raise SystemExit(0 if not status.update_available else 2)

    if args.apply_update:
        result = apply_update()
        print(result.message)
        raise SystemExit(0 if result.ok else 1)

    if args.serve:
        run_serve(args.port)
        return

    raise SystemExit(run_launcher(args.port))


if __name__ == "__main__":
    main()
