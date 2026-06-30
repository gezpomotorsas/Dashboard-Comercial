"""Refresh asíncrono de deal_analytics."""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict
from typing import Any

from app.config import get_settings
from app.repositories.deal_analytics_repository import DealAnalyticsRepository
from app.services.deal_analytics.builder import build_deal_analytics_row
from app.services.hubspot_configuration import get_hubspot_config, invalidate_hubspot_config
from app.utils.dates import utc_now

logger = logging.getLogger(__name__)

_running_refresh: set[str] = set()
_refresh_lock = asyncio.Lock()

ACTIVITY_TYPES = frozenset({"calls", "communications", "meetings", "tasks", "notes"})


class DealAnalyticsRefreshAlreadyRunningError(Exception):
    pass


class DealAnalyticsRefreshService:
    def __init__(self, repository: DealAnalyticsRepository | None = None) -> None:
        self._repo = repository or DealAnalyticsRepository()
        self._settings = get_settings()

    async def start_refresh(self) -> dict[str, Any]:
        async with _refresh_lock:
            if "deal_analytics" in _running_refresh:
                raise DealAnalyticsRefreshAlreadyRunningError("Refresh de deal_analytics ya en ejecución")
            _running_refresh.add("deal_analytics")
        run = self._repo.create_run()
        asyncio.create_task(self._run_safe(str(run["id"])))
        return {"run_id": str(run["id"]), "status": "started"}

    async def _run_safe(self, run_id: str) -> None:
        try:
            await asyncio.to_thread(self._execute_refresh, run_id)
        finally:
            async with _refresh_lock:
                _running_refresh.discard("deal_analytics")

    def _execute_refresh(self, run_id: str) -> None:
        started = time.perf_counter()
        self._repo.update_run(run_id, {"status": "running"})
        invalidate_hubspot_config()
        config = get_hubspot_config(refresh=True)
        config.validate_field_mappings()

        associations = self._repo.fetch_all_associations()
        deal_contacts, deal_activities = _build_deal_relation_maps(associations)
        activity_index = self._repo.fetch_activities_index()

        batch_size = self._settings.deal_analytics_batch_size
        processed = inserted = updated = failed = 0
        errors: list[dict[str, str]] = []

        offset = 0
        while True:
            deals = self._repo.fetch_deals_page(offset=offset, limit=batch_size)
            if not deals:
                break
            deal_ids = [str(d["hubspot_id"]) for d in deals]
            history_map = self._repo.fetch_stage_history_by_deals(deal_ids)
            contact_ids_batch: set[str] = set()
            for deal in deals:
                contact_ids_batch.update(deal_contacts.get(str(deal["hubspot_id"]), set()))
            contacts_map = self._repo.fetch_contacts_by_ids(list(contact_ids_batch))
            rows: list[dict[str, Any]] = []

            for deal in deals:
                deal_id = str(deal["hubspot_id"])
                try:
                    activities = _resolve_deal_activities(
                        deal_id,
                        deal_activities.get(deal_id, set()),
                        activity_index,
                    )
                    linked_contacts = [
                        contacts_map[cid]
                        for cid in deal_contacts.get(deal_id, set())
                        if cid in contacts_map
                    ]
                    row = build_deal_analytics_row(
                        deal,
                        config=config,
                        contact_ids=deal_contacts.get(deal_id, set()),
                        contacts=linked_contacts,
                        activities=activities,
                        stage_history=history_map.get(deal_id, []),
                    )
                    rows.append(row)
                    processed += 1
                except Exception as exc:
                    failed += 1
                    if len(errors) < 50:
                        errors.append({"deal_id": deal_id, "error": str(exc)})
                    logger.exception("Error calculando deal_analytics para %s", deal_id)

            if rows:
                existing_before = self._repo.count_analytics()
                self._repo.upsert_deal_analytics(rows)
                existing_after = self._repo.count_analytics()
                delta = max(0, existing_after - existing_before)
                inserted += min(delta, len(rows))
                updated += max(0, len(rows) - delta)

            offset += batch_size
            if len(deals) < batch_size:
                break

        duration = round(time.perf_counter() - started, 2)
        status = "completed_with_errors" if failed else "completed"
        self._repo.update_run(
            run_id,
            {
                "status": status,
                "finished_at": utc_now().isoformat(),
                "deals_processed": processed,
                "deals_inserted": inserted,
                "deals_updated": updated,
                "deals_failed": failed,
                "metadata_version": config.metadata_version,
                "field_mapping_version": config.field_mapping_version,
                "dimension_mapping_version": config.dimension_mapping_version,
                "duration_seconds": duration,
                "errors": errors,
            },
        )

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        return self._repo.get_run(run_id)


def _build_deal_relation_maps(
    associations: list[dict[str, Any]],
) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    deal_contacts: dict[str, set[str]] = defaultdict(set)
    deal_activities: dict[str, set[str]] = defaultdict(set)

    for row in associations:
        if not row.get("is_active", True):
            continue
        f_type = row.get("from_object_type")
        t_type = row.get("to_object_type")
        f_id = str(row["from_hubspot_id"])
        t_id = str(row["to_hubspot_id"])

        if f_type == "deals" and t_type == "contacts":
            deal_contacts[f_id].add(t_id)
        elif f_type == "contacts" and t_type == "deals":
            deal_contacts[t_id].add(f_id)
        elif f_type == "deals" and t_type in ACTIVITY_TYPES:
            deal_activities[f_id].add(t_id)
        elif f_type in ACTIVITY_TYPES and t_type == "deals":
            deal_activities[t_id].add(f_id)

    return deal_contacts, deal_activities


def _resolve_deal_activities(
    deal_id: str,
    activity_ids: set[str],
    activity_index: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        {"deal_id": deal_id, **activity_index[aid]}
        for aid in activity_ids
        if aid in activity_index
    ]
