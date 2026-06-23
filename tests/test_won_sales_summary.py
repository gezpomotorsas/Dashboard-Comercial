"""Pruebas de resumen de unidades vendidas."""

from __future__ import annotations

from datetime import UTC, datetime

from app.services.deal_analytics.query import _won_sales_units_summary


def _won_row(closed_at: datetime) -> dict:
    return {"is_won": True, "closed_at": closed_at}


def test_won_sales_units_summary_counts_by_calendar_month(monkeypatch):
    class FakeDatetime:
        @classmethod
        def now(cls, tz):
            return datetime(2026, 6, 20, 12, 0, tzinfo=tz)

    monkeypatch.setattr("app.services.deal_analytics.query.datetime", FakeDatetime)

    rows = [
        _won_row(datetime(2026, 6, 5, 10, 0, tzinfo=UTC)),
        _won_row(datetime(2026, 6, 18, 10, 0, tzinfo=UTC)),
        _won_row(datetime(2026, 5, 28, 10, 0, tzinfo=UTC)),
        _won_row(datetime(2026, 5, 10, 10, 0, tzinfo=UTC)),
        _won_row(datetime(2025, 12, 1, 10, 0, tzinfo=UTC)),
        {"is_won": False, "closed_at": datetime(2026, 6, 1, 10, 0, tzinfo=UTC)},
    ]

    summary = _won_sales_units_summary(rows, timezone="America/Bogota")

    assert summary["total_units"] == 5
    assert summary["units_this_month"] == 2
    assert summary["units_previous_month"] == 2
    assert summary["month_over_month_change_pct"] == 0.0
    assert summary["this_month_key"] == "2026-06"
    assert summary["previous_month_key"] == "2026-05"
