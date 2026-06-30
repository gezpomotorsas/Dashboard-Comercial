"""Endpoints del launcher (actualizaciones)."""

from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.dashboard_sync_pipeline import (
    get_dashboard_sync_state,
    run_dashboard_sync,
)
from launcher.updater import UpdateResult, UpdateStatus, apply_update, check_for_update
from launcher.version_store import read_version

router = APIRouter(prefix="/api/v1/launcher", tags=["launcher"])

RESTART_EXIT_CODE = 42


class UpdateStatusResponse(BaseModel):
    local_commit: str
    remote_commit: str
    update_available: bool
    source: str
    release_tag: str | None = None
    release_name: str | None = None
    message: str = ""
    app_version: str = ""
    built_at: str | None = None
    repo: str | None = None


class UpdateApplyResponse(BaseModel):
    ok: bool
    message: str
    previous_commit: str | None = None
    new_commit: str | None = None
    restart_required: bool = False


class HubSpotSyncPart(BaseModel):
    objects: str = ""
    associations: str = ""
    analytics: str = ""


class SupabaseSyncStatusResponse(BaseModel):
    running: bool
    started_at: str | None = None
    result: HubSpotSyncPart | None = None


class UpdateAllResponse(BaseModel):
    ok: bool
    message: str
    hubspot: HubSpotSyncPart
    github: UpdateApplyResponse
    restart_required: bool = False


def _status_payload(status: UpdateStatus) -> dict[str, Any]:
    meta = read_version()
    return UpdateStatusResponse(
        local_commit=status.local_commit,
        remote_commit=status.remote_commit,
        update_available=status.update_available,
        source=status.source,
        release_tag=status.release_tag,
        release_name=status.release_name,
        message=status.message,
        app_version=str(meta.get("version") or ""),
        built_at=meta.get("built_at"),
        repo=meta.get("repo"),
    ).model_dump()


def _apply_payload(result: UpdateResult, *, restart: bool) -> dict[str, Any]:
    return UpdateApplyResponse(
        ok=result.ok,
        message=result.message,
        previous_commit=result.previous_commit,
        new_commit=result.new_commit,
        restart_required=restart and result.ok and result.new_commit != result.previous_commit,
    ).model_dump()


class RestartRequest(BaseModel):
    delay_seconds: float = Field(default=0.5, ge=0, le=10)


@router.get("/update/status", response_model=UpdateStatusResponse)
async def update_status() -> dict[str, Any]:
    return _status_payload(check_for_update())


@router.post("/update/check", response_model=UpdateStatusResponse)
async def update_check() -> dict[str, Any]:
    return _status_payload(check_for_update())


@router.post("/update/apply", response_model=UpdateApplyResponse)
async def update_apply() -> dict[str, Any]:
    result = apply_update(prefer_git=os.getenv("UPDATE_SOURCE", "").lower() == "git")
    if not result.ok:
        raise HTTPException(status_code=400, detail=result.message)
    return _apply_payload(result, restart=True)


@router.get("/sync/status", response_model=SupabaseSyncStatusResponse)
async def supabase_sync_status() -> dict[str, Any]:
    """Estado del sync HubSpot → Supabase en curso o último resultado."""
    state = get_dashboard_sync_state()
    raw = state.get("result")
    result = HubSpotSyncPart(**raw) if isinstance(raw, dict) else None
    return SupabaseSyncStatusResponse(
        running=bool(state.get("running")),
        started_at=state.get("started_at"),
        result=result,
    ).model_dump()


def _hubspot_part_from_result(hubspot: dict[str, str]) -> HubSpotSyncPart:
    return HubSpotSyncPart(
        objects=hubspot.get("objects", ""),
        associations=hubspot.get("associations", ""),
        analytics=hubspot.get("analytics", ""),
    )


def _sync_failed(part: HubSpotSyncPart) -> bool:
    for value in (part.objects, part.associations, part.analytics):
        if value.startswith("error"):
            return True
    return False


@router.post("/update/all", response_model=UpdateAllResponse)
async def update_all() -> dict[str, Any]:
    """Sync HubSpot → Supabase + recálculo deal_analytics, luego GitHub si hay release."""
    hubspot = await run_dashboard_sync(refresh_analytics=True)
    hubspot_part = _hubspot_part_from_result(hubspot)

    status = check_for_update()
    if status.update_available:
        github_result = apply_update(prefer_git=os.getenv("UPDATE_SOURCE", "").lower() == "git")
    else:
        github_result = UpdateResult(
            ok=True,
            message=status.message or "App al día en GitHub",
            previous_commit=status.local_commit,
        )

    github_payload = _apply_payload(github_result, restart=True)
    restart_required = bool(github_payload.get("restart_required"))

    supabase_msg = (
        f"Supabase: objetos {hubspot_part.objects}. "
        f"Asociaciones: {hubspot_part.associations}. "
        f"Analítica: {hubspot_part.analytics}."
    )
    github_msg = f"GitHub: {github_result.message}"
    combined_ok = not _sync_failed(hubspot_part) and github_result.ok

    return UpdateAllResponse(
        ok=combined_ok,
        message=f"{supabase_msg} {github_msg}",
        hubspot=hubspot_part,
        github=UpdateApplyResponse(**github_payload),
        restart_required=restart_required,
    ).model_dump()


@router.post("/sync/hubspot", response_model=HubSpotSyncPart)
async def sync_hubspot_now() -> dict[str, str]:
    """Sync HubSpot → Supabase + recálculo deal_analytics (espera a que termine)."""
    hubspot = await run_dashboard_sync(refresh_analytics=True)
    return _hubspot_part_from_result(hubspot).model_dump()


@router.post("/restart")
async def restart_app(_: RestartRequest) -> dict[str, str]:
    async def _exit() -> None:
        import asyncio

        await asyncio.sleep(0.5)
        os._exit(RESTART_EXIT_CODE)

    import asyncio

    asyncio.create_task(_exit())
    return {"message": "Reiniciando aplicación…"}
