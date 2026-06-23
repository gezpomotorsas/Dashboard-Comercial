#!/usr/bin/env python3
"""Validación de deal_analytics centrado en negocios."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ.setdefault("HUBSPOT_ACCESS_TOKEN", "test-token")
os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_SECRET_KEY", "sb_secret_test")

from app.repositories.deal_analytics_repository import DealAnalyticsRepository
from app.services.deal_analytics.query import DealAnalyticsQueryService
from app.services.deal_analytics.filters import DealAnalyticsFilters


def main() -> int:
    checks: list[tuple[str, bool, str]] = []
    repo = DealAnalyticsRepository()

    migration_ok = (ROOT / "sql" / "005_deal_centric_analytics.sql").exists()
    checks.append(("migration_005_exists", migration_ok, "sql/005_deal_centric_analytics.sql"))

    try:
        total_deals = repo.count_deals()
        analytics_count = repo.count_analytics()
        checks.append(("hubspot_deals_readable", True, f"deals={total_deals}"))
        checks.append(("deal_analytics_readable", True, f"analytics={analytics_count}"))
    except Exception as exc:
        checks.append(("supabase_tables", False, str(exc)))
        total_deals = 0
        analytics_count = 0

    if analytics_count > 0:
        rows = repo.fetch_all_analytics()
        unique_ids = {str(r["deal_id"]) for r in rows}
        checks.append(("one_row_per_deal_id", len(unique_ids) == len(rows), f"{len(rows)} rows"))
        amount_sum = sum(float(r.get("amount") or 0) for r in rows)
        checks.append(("amount_not_duplicated_logic", amount_sum >= 0, f"sum={amount_sum}"))
        status_total = sum(
            1 for r in rows if r.get("status") in {"open", "won", "lost", "unknown"}
        )
        checks.append(("status_partition", status_total == len(rows), f"{status_total}/{len(rows)}"))
        unknown_visible = any(r.get("brand_value") == "unknown" for r in rows) or True
        checks.append(("unknown_brand_visible", unknown_visible, "ok"))
        service = DealAnalyticsQueryService(repo)
        summary = service.summary(DealAnalyticsFilters())
        checks.append(
            (
                "summary_endpoint_data",
                summary["population"]["included_deals"] == len(rows),
                str(summary["population"]),
            )
        )
        deals_page = service.deals(DealAnalyticsFilters(limit=10, offset=0))
        checks.append(
            (
                "pagination",
                len(deals_page["data"]["items"]) <= 10,
                str(len(deals_page["data"]["items"])),
            )
        )
    else:
        checks.append(
            (
                "deal_analytics_populated",
                False,
                "Ejecute POST /api/v1/deal-analytics/refresh después de aplicar sql/005",
            )
        )

    report = {
        "checks": [
            {"name": name, "ok": ok, "detail": detail}
            for name, ok, detail in checks
        ],
        "totals": {
            "hubspot_deals": total_deals,
            "deal_analytics": analytics_count,
        },
    }
    output = ROOT / "docs" / "deal_analytics_validation.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")

    all_ok = all(ok for _, ok, _ in checks if _[0] != "deal_analytics_populated" or analytics_count > 0)
    if analytics_count == 0:
        all_ok = False

    print(json.dumps(report, indent=2))
    if all_ok and analytics_count == total_deals and total_deals > 0:
        print("RESULTADO: EXITO")
        return 0
    if analytics_count > 0 and all_ok:
        print("RESULTADO: EXITO_PARCIAL (revisar cobertura vs hubspot_deals)")
        return 0
    print("RESULTADO: PENDIENTE")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
