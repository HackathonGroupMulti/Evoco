"""Extraction schemas for Nova Act's act_get() structured output."""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Schema definitions
# ---------------------------------------------------------------------------

# Flat product list — works for e-commerce search/extract (Amazon, Best Buy…)
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

# Review / opinion aggregation (Yelp, Google Reviews, TripAdvisor…)
REVIEW_SCHEMA: dict = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "reviewer": {"type": "string"},
            "rating": {"type": "number"},
            "date": {"type": "string"},
            "text": {"type": "string"},
            "helpful_count": {"type": "number"},
        },
        "required": ["text"],
    },
}

# Real-estate listing (Zillow, Realtor.com, Redfin…)
LISTING_SCHEMA: dict = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "address": {"type": "string"},
            "price": {"type": "number"},
            "beds": {"type": "number"},
            "baths": {"type": "number"},
            "sqft": {"type": "number"},
            "url": {"type": "string"},
            "days_on_market": {"type": "number"},
        },
        "required": ["address"],
    },
}

# Restaurant / food discovery (Yelp, OpenTable, DoorDash…)
RESTAURANT_SCHEMA: dict = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "cuisine": {"type": "string"},
            "rating": {"type": "number"},
            "price_range": {"type": "string"},
            "address": {"type": "string"},
            "url": {"type": "string"},
        },
        "required": ["name"],
    },
}

# Job postings (LinkedIn, Indeed, Glassdoor…)
JOB_SCHEMA: dict = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "company": {"type": "string"},
            "location": {"type": "string"},
            "salary": {"type": "string"},
            "posted_date": {"type": "string"},
            "url": {"type": "string"},
        },
        "required": ["title", "company"],
    },
}

# ---------------------------------------------------------------------------
# Domain-to-schema mapping  (checked via substring match on target URL)
# ---------------------------------------------------------------------------

_DOMAIN_MAP: list[tuple[tuple[str, ...], dict]] = [
    # Real estate
    (("zillow", "realtor.com", "redfin", "trulia"), LISTING_SCHEMA),
    # Jobs
    (("linkedin.com/jobs", "indeed", "glassdoor", "monster.com"), JOB_SCHEMA),
    # Restaurants / food
    (("yelp", "opentable", "doordash", "grubhub", "tripadvisor"), RESTAURANT_SCHEMA),
]

# Keywords in the step description that hint at review-style extraction
_REVIEW_KEYWORDS = ("review", "opinion", "feedback", "rating", "testimonial")


def schema_for_action(
    action: str,
    target: str = "",
    description: str = "",
) -> dict | None:
    """Return the appropriate extraction schema for a step.

    Selection priority:
      1. Non-extract/search actions → None
      2. URL domain match           → domain-specific schema
      3. Description keyword match  → REVIEW_SCHEMA when review-like
      4. Default                    → PRODUCT_SCHEMA
    """
    if action not in ("extract", "search"):
        return None

    target_lower = target.lower()
    desc_lower = description.lower()

    # 1. Domain-based selection
    for domains, schema in _DOMAIN_MAP:
        if any(d in target_lower for d in domains):
            return schema

    # 2. Description-based heuristic for reviews
    if any(kw in desc_lower for kw in _REVIEW_KEYWORDS):
        return REVIEW_SCHEMA

    # 3. Default — generic product schema
    return PRODUCT_SCHEMA
