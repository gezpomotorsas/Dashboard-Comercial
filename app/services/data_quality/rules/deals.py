"""Reglas de calidad para negocios."""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

from app.config import get_settings
from app.services.hubspot_configuration import get_hubspot_config
from app.services.hubspot_configuration.store import HubSpotConfigStore


def evaluate_deals(
    rows: list[dict[str, Any]],
    *,
    deal_contact_map: dict[str, bool],
    deal_activity_map: dict[str, bool],
    pipeline_stages: dict[str, set[str]],
    config: HubSpotConfigStore | None = None,
) -> Iterator[dict[str, Any]]:
    store = config or get_hubspot_config()
    known_pipelines = store.known_pipeline_ids
    stale_days = get_settings().data_quality_stale_deal_days
    stale_threshold = datetime.now(UTC) - timedelta(days=stale_days)

    for row in rows:
        hid = str(row.get("hubspot_id"))
        props = row.get("properties") or {}
        pipeline_id = row.get("pipeline_id") or props.get("pipeline")
        stage_id = row.get("dealstage_id") or props.get("dealstage")

        if not props.get("hubspot_owner_id"):
            yield _finding("DEAL_WITHOUT_OWNER", hid, "warning", "missing_owner", "Sin propietario")
        if not deal_contact_map.get(hid):
            yield _finding("DEAL_WITHOUT_CONTACT", hid, "critical", "no_contact", "Sin contacto asociado")
        if not pipeline_id:
            yield _finding("DEAL_WITHOUT_PIPELINE", hid, "critical", "missing_pipeline", "Sin pipeline")
        if not stage_id:
            yield _finding("DEAL_WITHOUT_STAGE", hid, "warning", "missing_stage", "Sin etapa")
        if not store.get_property_value(row, "deals", "deal_amount"):
            yield _finding("DEAL_WITHOUT_AMOUNT", hid, "info", "missing_amount", "Sin monto")
        if pipeline_id and str(pipeline_id) not in known_pipelines:
            yield _finding(
                "DEAL_WITH_UNKNOWN_PIPELINE",
                hid,
                "warning",
                f"unknown_pipeline:{pipeline_id}",
                f"Pipeline desconocido: {pipeline_id}",
                {"pipeline_id": str(pipeline_id)},
            )
        if pipeline_id and stage_id:
            valid_stages = pipeline_stages.get(str(pipeline_id), set())
            if valid_stages and str(stage_id) not in valid_stages:
                yield _finding(
                    "DEAL_WITH_INVALID_STAGE",
                    hid,
                    "warning",
                    f"invalid_stage:{stage_id}",
                    "Etapa no válida para el pipeline",
                )
        if not deal_activity_map.get(hid):
            yield _finding(
                "DEAL_WITHOUT_ACTIVITY",
                hid,
                "info",
                "no_activity",
                "Sin actividades asociadas",
            )
            yield _finding(
                "DEAL_WITHOUT_ACTIVITY_ASSOCIATION",
                hid,
                "info",
                "no_activity_assoc",
                "Sin asociación a actividades",
            )

        updated = row.get("updated_at_hubspot")
        if updated:
            try:
                updated_dt = datetime.fromisoformat(str(updated).replace("Z", "+00:00"))
                if updated_dt.tzinfo is None:
                    updated_dt = updated_dt.replace(tzinfo=UTC)
                if updated_dt < stale_threshold:
                    yield _finding(
                        "DEAL_STALE",
                        hid,
                        "warning",
                        "stale",
                        f"Sin actualización en {stale_days} días",
                    )
            except ValueError:
                pass

        stage_status, _ = store.classify_stage(
            str(pipeline_id) if pipeline_id else None,
            str(stage_id) if stage_id else None,
        )
        if stage_status in ("won", "lost") and not store.get_property_value(row, "deals", "deal_close_date"):
            yield _finding(
                "DEAL_CLOSED_WITHOUT_CLOSE_DATE",
                hid,
                "warning",
                "missing_closedate",
                "Cerrado sin closedate",
            )
        if store.is_deal_won(row) and not store.get_property_value(row, "deals", "deal_amount"):
            yield _finding(
                "DEAL_WON_WITHOUT_AMOUNT",
                hid,
                "critical",
                "won_no_amount",
                "Ganado sin monto",
            )


def _finding(
    code: str,
    hubspot_id: str,
    severity: str,
    issue_key: str,
    message: str,
    details: dict | None = None,
) -> dict[str, Any]:
    return {
        "rule_code": code,
        "object_type": "deals",
        "hubspot_id": hubspot_id,
        "severity": severity,
        "issue_key": issue_key,
        "message": message,
        "details": details or {},
    }
