"""Montaje del frontend estático en modo launcher."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.staticfiles import StaticFiles

logger = logging.getLogger(__name__)


class SPAStaticFiles(StaticFiles):
    """Sirve archivos estáticos y devuelve index.html solo para rutas del SPA."""

    _static_extensions = {
        ".js",
        ".css",
        ".map",
        ".svg",
        ".png",
        ".jpg",
        ".jpeg",
        ".webp",
        ".ico",
        ".woff",
        ".woff2",
        ".ttf",
    }

    async def get_response(self, path: str, scope):
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code != 404 or scope["type"] != "http":
                raise
            if Path(path).suffix.lower() in self._static_extensions:
                raise
            return await super().get_response("index.html", scope)


def _dist_dir() -> Path | None:
    try:
        from launcher.paths import frontend_dist_dir

        dist = frontend_dist_dir()
        if dist.is_dir() and (dist / "index.html").is_file():
            return dist
    except ImportError:
        pass

    for relative in ("runtime/frontend/dist", "frontend/dist"):
        candidate = Path(relative)
        if candidate.is_dir() and (candidate / "index.html").is_file():
            return candidate.resolve()
    return None


def mount_frontend(app: FastAPI) -> bool:
    dist = _dist_dir()
    if dist is None:
        logger.warning("Frontend dist no encontrado; el dashboard web no estará disponible")
        return False

    logger.info("Sirviendo frontend desde %s", dist)

    @app.get("/actualizar", include_in_schema=False)
    async def update_page() -> FileResponse:
        page = Path(__file__).resolve().parent / "static" / "actualizar.html"
        return FileResponse(page)

    # Montar al final: /api, /docs y /health tienen prioridad (rutas registradas antes).
    app.mount("/", SPAStaticFiles(directory=str(dist), html=True), name="frontend")
    return True
