"""Umbrales de negocios estancados por marca."""

from __future__ import annotations

DEFAULT_STALE_DAYS = 45

STALE_DAYS_BY_BRAND: dict[str, int] = {
    "voyah": 21,
    "mhero": 21,
    "shacman": 45,
}


def stale_threshold_days_for_brand(brand_value: str | None) -> int:
    if not brand_value:
        return DEFAULT_STALE_DAYS
    return STALE_DAYS_BY_BRAND.get(str(brand_value).strip().lower(), DEFAULT_STALE_DAYS)
