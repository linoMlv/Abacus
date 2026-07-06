"""JSON serialization for MCP tool results.

Tool handlers return ordinary Python objects (SQLModel rows, dataclasses,
lists, Decimals, dates). ``to_text`` renders them as pretty JSON an assistant
can read, with money kept as exact decimal strings (never lossy floats).
"""

import json
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum


def _jsonable(obj):
    """Recursively convert ``obj`` into JSON-native types."""
    if obj is None or isinstance(obj, str | int | bool):
        return obj
    if isinstance(obj, Decimal):
        return str(obj)
    if isinstance(obj, float):
        return obj
    if isinstance(obj, datetime | date):
        return obj.isoformat()
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, list | tuple):
        return [_jsonable(v) for v in obj]
    # SQLModel / Pydantic models expose model_dump.
    dump = getattr(obj, "model_dump", None)
    if callable(dump):
        return _jsonable(dump())
    if is_dataclass(obj) and not isinstance(obj, type):
        return _jsonable(asdict(obj))
    return str(obj)


def to_text(obj) -> str:
    """Render a tool result as indented JSON text."""
    return json.dumps(_jsonable(obj), ensure_ascii=False, indent=2)
