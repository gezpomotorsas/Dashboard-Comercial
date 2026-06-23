"""Utilidades de serialización."""

import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID


def to_json_serializable(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {str(k): to_json_serializable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [to_json_serializable(item) for item in value]
    return str(value)


def safe_json_dumps(value: Any) -> str:
    return json.dumps(to_json_serializable(value), ensure_ascii=False)


def chunk_list(items: list[str], size: int) -> list[list[str]]:
    if size <= 0:
        raise ValueError("size must be positive")
    return [items[i : i + size] for i in range(0, len(items), size)]
