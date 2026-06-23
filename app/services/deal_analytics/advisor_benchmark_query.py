"""Consulta de benchmark asesor vs promedio de marca."""

from __future__ import annotations

from typing import Any

from app.services.deal_analytics.advisor_brand_benchmark import (
    BRAND_LABELS,
    build_advisor_brand_comparison,
    find_advisor_by_name,
    load_advisor_assignments,
    summarize_comparison,
)
from app.config import get_settings
from app.repositories.dashboard_repository import DashboardRepository
from app.services.deal_analytics.query import DealAnalyticsQueryService
from app.services.hubspot_configuration import get_hubspot_config
from app.utils.dates import utc_now


ALLOWED_BRANDS = frozenset({"voyah", "mhero", "shacman"})


def _owner_directory() -> dict[str, dict[str, Any]]:
    """Índice hubspot_id -> owner con email (desde Supabase, fuente confiable para n8n)."""
    directory: dict[str, dict[str, Any]] = {}
    for owner in DashboardRepository().fetch_owners():
        if owner.get("archived"):
            continue
        hubspot_id = str(owner.get("hubspot_id") or "").strip()
        if hubspot_id:
            directory[hubspot_id] = owner
    return directory


def _resolve_owner_contact(
    owner_id: str,
    *,
    owners: dict[str, dict[str, Any]],
    config_owners: dict[str, Any],
    assignment_email: str | None = None,
) -> dict[str, Any]:
    owner = owners.get(owner_id) or config_owners.get(owner_id) or {}
    email = (owner.get("email") or assignment_email or "").strip() or None
    first_name = owner.get("first_name")
    last_name = owner.get("last_name")
    return {
        "email": email,
        "first_name": first_name,
        "last_name": last_name,
        "email_status": "available" if email else "missing",
    }


class AdvisorBrandBenchmarkService:
    def __init__(self, query_service: DealAnalyticsQueryService | None = None) -> None:
        self._query = query_service or DealAnalyticsQueryService()

    def benchmark(
        self,
        *,
        brand_value: str | None = None,
        only_registered: bool = True,
        tolerance_pct: float = 10.0,
    ) -> dict[str, Any]:
        brands = [brand_value.strip().lower()] if brand_value else sorted(ALLOWED_BRANDS)
        for brand in brands:
            if brand not in ALLOWED_BRANDS:
                raise ValueError(f"Marca no soportada: {brand}")

        config = get_hubspot_config()
        owners = _owner_directory()
        assignments = load_advisor_assignments() if only_registered else []
        results: list[dict[str, Any]] = []
        unmatched: list[dict[str, Any]] = []
        missing_email: list[dict[str, Any]] = []

        for brand in brands:
            envelope = self._query.brand_operating(brand)
            operating = envelope.get("data") or {}
            advisors = operating.get("advisors") or []
            peers_by_owner = {
                str(row.get("owner_id") or "unassigned"): row
                for row in advisors
                if str(row.get("owner_id") or "unassigned") != "unassigned"
            }

            targets: list[dict[str, Any]]
            if only_registered:
                targets = [
                    assignment
                    for assignment in assignments
                    if assignment.get("brand") == brand
                ]
            else:
                targets = [
                    {
                        "name": row.get("owner_name") or "",
                        "brand": brand,
                        "location": "",
                        "owner_id": row.get("owner_id"),
                    }
                    for row in advisors
                    if row.get("owner_id")
                ]

            for target in targets:
                advisor = (
                    peers_by_owner.get(str(target.get("owner_id")))
                    if target.get("owner_id")
                    else find_advisor_by_name(advisors, str(target.get("name") or ""))
                )
                if not advisor:
                    unmatched.append(
                        {
                            "registered_name": target.get("name"),
                            "brand_value": brand,
                            "brand_label": BRAND_LABELS.get(brand, brand.title()),
                            "location": target.get("location"),
                            "match_status": "not_found_in_hubspot",
                        }
                    )
                    continue

                owner_id = str(advisor.get("owner_id") or "")
                peers = [
                    row
                    for oid, row in peers_by_owner.items()
                    if oid != owner_id
                ]
                metrics = build_advisor_brand_comparison(
                    advisor,
                    peers,
                    tolerance_pct=tolerance_pct,
                )
                summary = summarize_comparison(metrics)
                contact = _resolve_owner_contact(
                    owner_id,
                    owners=owners,
                    config_owners=config.owners,
                    assignment_email=str(target.get("email") or "").strip() or None,
                )

                row = {
                    "owner_id": owner_id,
                    "owner_name": advisor.get("owner_name"),
                    "registered_name": target.get("name") or advisor.get("owner_name"),
                    **contact,
                    "brand_value": brand,
                    "brand_label": operating.get("brand_label") or BRAND_LABELS.get(brand, brand.title()),
                    "location": target.get("location") or "",
                    "match_status": "matched",
                    "peer_count": len(peers),
                    "open_deals": advisor.get("open_deals"),
                    **summary,
                    "metrics": metrics,
                }
                results.append(row)
                if contact["email_status"] == "missing":
                    missing_email.append(
                        {
                            "owner_id": owner_id,
                            "owner_name": row["owner_name"],
                            "registered_name": row["registered_name"],
                            "brand_value": brand,
                            "brand_label": row["brand_label"],
                            "location": row["location"],
                        }
                    )

        results.sort(key=lambda row: (row["brand_value"], row.get("owner_name") or ""))

        return {
            "generated_at": utc_now().isoformat(),
            "timezone": get_settings().business_timezone,
            "tolerance_pct": tolerance_pct,
            "only_registered": only_registered,
            "brands": brands,
            "advisors": results,
            "unmatched_registrations": unmatched,
            "advisors_missing_email": missing_email,
            "summary": {
                "total_advisors": len(results),
                "good_count": sum(1 for row in results if row["overall_status"] == "good"),
                "needs_improvement_count": sum(
                    1 for row in results if row["overall_status"] == "needs_improvement"
                ),
                "insufficient_data_count": sum(
                    1 for row in results if row["overall_status"] == "insufficient_data"
                ),
                "unmatched_count": len(unmatched),
                "missing_email_count": len(missing_email),
            },
        }
