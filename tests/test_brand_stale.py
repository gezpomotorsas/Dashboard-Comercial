import pytest

from app.services.deal_analytics.brand_stale import stale_threshold_days_for_brand


@pytest.mark.parametrize(
    ("brand", "expected"),
    [
        ("voyah", 21),
        ("Voyah", 21),
        ("mhero", 21),
        ("MHero", 21),
        ("shacman", 45),
        ("unknown", 45),
        (None, 45),
    ],
)
def test_stale_threshold_days_for_brand(brand: str | None, expected: int) -> None:
    assert stale_threshold_days_for_brand(brand) == expected
