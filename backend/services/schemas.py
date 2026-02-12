"""Extraction schemas for Nova Act's act_get() structured output."""

from __future__ import annotations

# Flat product list — works for both search results and extraction.
# Keeping this minimal reduces prompt size (Nova Act concatenates schema into prompt).
PRODUCT_SCHEMA: dict = {
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


def schema_for_action(action: str) -> dict | None:
    """Return the appropriate schema for a given action, or None."""
    if action in ("extract", "search"):
        return PRODUCT_SCHEMA
    return None
