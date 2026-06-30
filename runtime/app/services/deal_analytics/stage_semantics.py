"""Agrupación semántica de etapas comerciales (transversal a marcas)."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


@dataclass(frozen=True)
class CommercialStageGroup:
    key: str
    label: str
    order: int
    patterns: tuple[str, ...]


COMMERCIAL_STAGE_GROUPS: tuple[CommercialStageGroup, ...] = (
    CommercialStageGroup(
        "prospeccion",
        "Prospección e interés",
        10,
        ("cliente interesado", "visita programada", "test drive"),
    ),
    CommercialStageGroup(
        "cotizacion_financiera",
        "Cotización y financiera",
        20,
        (
            "cotizacion",
            "simulacion financiera",
            "estudio de credito",
            "estudio de crédito",
            "leasing",
            "carta de aprobacion",
            "carta de aprobación",
        ),
    ),
    CommercialStageGroup(
        "venta_pedido",
        "Venta y pedido",
        30,
        ("pedido", "separacion", "separación"),
    ),
    CommercialStageGroup(
        "operaciones",
        "Operaciones y entrega",
        40,
        (
            "faltan datos",
            "revision",
            "revisión",
            "ok de cartera",
            "facturacion",
            "facturación",
            "matricula",
            "matrícula",
            "alistamiento",
            "paz y salvo",
            "ok para entrega",
            "ok para entrga",
        ),
    ),
    CommercialStageGroup(
        "cierre_ganado",
        "Cierre ganado",
        50,
        ("cierre ganado",),
    ),
    CommercialStageGroup(
        "cierre_perdido",
        "Cierre perdido",
        60,
        ("cierre perdido",),
    ),
)

_BRAND_PIPELINE_IDS: dict[str, str] = {
    "shacman": "default",
    "voyah": "1000390393",
    "mhero": "1963395799",
}

OPERATING_BRANDS: tuple[tuple[str, str], ...] = (
    ("voyah", "Voyah"),
    ("mhero", "MHero"),
    ("shacman", "Shacman"),
)


def normalize_stage_text(value: str | None) -> str:
    if not value:
        return ""
    text = unicodedata.normalize("NFKD", str(value))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower().strip()
    return re.sub(r"\s+", " ", text)


def resolve_commercial_stage_group(stage_label: str | None) -> tuple[str, str, int]:
    normalized = normalize_stage_text(stage_label)
    if not normalized:
        return "unknown", "Sin clasificar", 999
    for group in COMMERCIAL_STAGE_GROUPS:
        for pattern in group.patterns:
            if pattern in normalized:
                return group.key, group.label, group.order
    return "otros", "Otros / administrativo", 45


def brand_pipeline_id(brand_value: str) -> str | None:
    return _BRAND_PIPELINE_IDS.get(str(brand_value).strip().lower())
