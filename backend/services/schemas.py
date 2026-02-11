"""Extraction schemas for Nova Act's act_get() structured output."""

from __future__ import annotations

PRODUCT_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "price": {"type": "number"},
            "rating": {"type": "number"},
            "url": {"type": "string"},
            "source": {"type": "string"},
        },
        "required": ["name"],
    },
}

GENERIC_RESULTS_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "description": {"type": "string"},
            "url": {"type": "string"},
            "source": {"type": "string"},
            "metadata": {"type": "object"},
        },
        "required": ["title"],
    },
}

SEARCH_RESULT_SCHEMA = {
    "type": "object",
    "properties": {
        "query": {"type": "string"},
        "results_count": {"type": "integer"},
        "results": GENERIC_RESULTS_SCHEMA,
    },
}


def schema_for_action(action: str) -> dict | None:
    """Return the appropriate schema for a given action, or None."""
    if action == "extract":
        return GENERIC_RESULTS_SCHEMA
    if action == "search":
        return SEARCH_RESULT_SCHEMA
    return None
