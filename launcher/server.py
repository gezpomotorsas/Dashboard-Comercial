"""Proceso uvicorn y variables de entorno del launcher."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from launcher.paths import ensure_data_layout, env_file_path, frontend_dist_dir, runtime_dir


def configure_runtime_env(port: int) -> None:
    ensure_data_layout()
    runtime = runtime_dir()
    data_env = env_file_path()

    os.environ["DASHBOARD_RUNTIME_DIR"] = str(runtime)
    os.environ["DASHBOARD_DATA_DIR"] = str(data_env.parent)
    os.environ["DASHBOARD_ENV_FILE"] = str(data_env)
    os.environ["DASHBOARD_LAUNCHER_MODE"] = "1"
    os.environ["DASHBOARD_PORT"] = str(port)

    if str(runtime) not in sys.path:
        sys.path.insert(0, str(runtime))
    root = runtime.parent if runtime.name == "runtime" else runtime
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))


def has_frontend_bundle() -> bool:
    dist = frontend_dist_dir()
    return dist.is_dir() and (dist / "index.html").is_file()


def run_server(port: int) -> None:
    configure_runtime_env(port)
    # Importar la app después de configurar variables (launcher + runtime paths).
    import uvicorn

    uvicorn.run(
        "app.main:create_app",
        factory=True,
        host="127.0.0.1",
        port=port,
        log_level=os.getenv("LOG_LEVEL", "info"),
    )


def spawn_server_subprocess(port: int) -> subprocess.Popen[str]:
    configure_runtime_env(port)
    cmd = [sys.executable, "-m", "launcher.main", "--serve", "--port", str(port)]
    if getattr(sys, "frozen", False):
        cmd = [sys.executable, "--serve", "--port", str(port)]
    return subprocess.Popen(cmd, cwd=str(runtime_dir().parent if runtime_dir().name == "runtime" else runtime_dir()))
