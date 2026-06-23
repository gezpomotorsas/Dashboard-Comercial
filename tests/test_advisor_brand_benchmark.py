import pytest

from app.services.deal_analytics.advisor_brand_benchmark import (
    build_advisor_brand_comparison,
    classify_vs_brand,
    find_advisor_by_name,
    summarize_comparison,
)


def _advisor(owner_id: str, name: str, **overrides):
    base = {
        "owner_id": owner_id,
        "owner_name": name,
        "performance": {
            "won_sales": {
                "units_this_month": 8,
                "units_previous_month": 6,
            },
            "leads_created": {"units_this_month": 10, "units_previous_month": 8},
            "tasks_overdue": 2,
            "tasks_completed_monthly": {"units_this_month": 12, "units_previous_month": 10},
            "tasks_managed_monthly": {"units_this_month": 15, "units_previous_month": 12},
            "calls_monthly": {"units_this_month": 20, "units_previous_month": 18},
            "whatsapp_monthly": {"units_this_month": 30, "units_previous_month": 25},
        },
        "call_coverage_rate": 70.0,
        "combined_coverage_rate": 65.0,
        "managed_30d_rate": 80.0,
    }
    base.update(overrides)
    return base


def test_classify_vs_brand_above_and_below():
    assert classify_vs_brand(12, 10, higher_is_better=True) == "above"
    assert classify_vs_brand(8, 10, higher_is_better=True) == "below"
    assert classify_vs_brand(10.5, 10, higher_is_better=True, tolerance_pct=10) == "similar"


def test_find_advisor_by_name_normalizes_accents():
    advisors = [_advisor("1", "Esperanza Mendez")]
    matched = find_advisor_by_name(advisors, "Esperanza Méndez")
    assert matched is not None
    assert matched["owner_id"] == "1"


def test_build_advisor_brand_comparison():
    advisor = _advisor("a1", "Ana")
    peers = [
        _advisor(
            "a2",
            "Beto",
            performance={
                "won_sales": {"units_this_month": 4},
                "leads_created": {"units_this_month": 5},
                "tasks_overdue": 4,
                "tasks_completed_monthly": {"units_this_month": 6},
                "tasks_managed_monthly": {"units_this_month": 7},
                "calls_monthly": {"units_this_month": 10},
                "whatsapp_monthly": {"units_this_month": 12},
            },
        ),
        _advisor(
            "a3",
            "Caro",
            performance={
                "won_sales": {"units_this_month": 6},
                "leads_created": {"units_this_month": 7},
                "tasks_overdue": 6,
                "tasks_completed_monthly": {"units_this_month": 8},
                "tasks_managed_monthly": {"units_this_month": 9},
                "calls_monthly": {"units_this_month": 14},
                "whatsapp_monthly": {"units_this_month": 16},
            },
        ),
    ]
    metrics = build_advisor_brand_comparison(advisor, peers, tolerance_pct=10)
    won = next(item for item in metrics if item["key"] == "won_sales_month")
    assert won["verdict"] == "above"
    overdue = next(item for item in metrics if item["key"] == "tasks_overdue")
    assert overdue["verdict"] == "above"


def test_summarize_comparison_actions():
    good = summarize_comparison(
        [
            {"key": "a", "label": "Ventas", "verdict": "above"},
            {"key": "b", "label": "Leads", "verdict": "similar"},
        ]
    )
    assert good["overall_status"] == "good"
    assert good["action"] == "felicitar"

    needs = summarize_comparison(
        [
            {"key": "a", "label": "Ventas", "verdict": "above"},
            {"key": "b", "label": "Tareas atrasadas", "verdict": "below"},
        ]
    )
    assert needs["overall_status"] == "needs_improvement"
    assert needs["action"] == "compromiso_mejora"
    assert "Tareas atrasadas" in needs["improvement_areas"]
