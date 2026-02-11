"""Step executor powered by Amazon Nova Act.

Each TaskStep is executed against a headless browser session.
Falls back to mock results when the Nova Act API key is missing.
"""

from __future__ import annotations

import asyncio
import logging
import random
from typing import Any

from backend.config import settings
from backend.models.task import TaskStep

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Nova Act integration (real)
# ---------------------------------------------------------------------------

async def _execute_with_nova_act(step: TaskStep) -> dict[str, Any]:
    """Execute a single step using the Nova Act SDK."""
    from nova_act import NovaAct  # type: ignore[import-untyped]

    async with NovaAct(
        api_key=settings.nova_act_api_key,
        starting_page=step.target if step.target.startswith("http") else "https://www.google.com",
        headless=settings.headless_browser,
    ) as act:
        result = await asyncio.to_thread(act.act, step.description)
        return {
            "success": result.response is not None,
            "response": result.response,
            "url": step.target,
        }


# ---------------------------------------------------------------------------
# Mock executor (fallback)
# ---------------------------------------------------------------------------

_MOCK_PRODUCTS = [
    {"name": "ASUS TUF Gaming A15", "price": 749.99, "rating": 4.5, "source": "amazon.com"},
    {"name": "Lenovo IdeaPad Gaming 3", "price": 699.99, "rating": 4.3, "source": "amazon.com"},
    {"name": "Acer Nitro V 15", "price": 779.99, "rating": 4.4, "source": "amazon.com"},
    {"name": "HP Victus 15", "price": 599.99, "rating": 4.2, "source": "bestbuy.com"},
    {"name": "Dell G15 Gaming", "price": 749.99, "rating": 4.3, "source": "bestbuy.com"},
    {"name": "MSI Thin 15", "price": 699.99, "rating": 4.1, "source": "bestbuy.com"},
    {"name": "ASUS TUF Gaming A16", "price": 789.99, "rating": 4.6, "source": "newegg.com"},
    {"name": "Lenovo LOQ 15", "price": 729.99, "rating": 4.4, "source": "newegg.com"},
    {"name": "Acer Aspire 5 Gaming", "price": 649.99, "rating": 4.0, "source": "newegg.com"},
]


def _mock_result_for_step(step: TaskStep) -> dict[str, Any]:
    """Return plausible mock data for any step type."""
    action = step.action

    if action == "navigate":
        return {"success": True, "url": step.target, "page_title": f"Homepage — {step.target}"}

    if action == "search":
        domain = step.target.replace("https://www.", "").rstrip("/")
        products = [p for p in _MOCK_PRODUCTS if domain in p.get("source", "")]
        if not products:
            products = random.sample(_MOCK_PRODUCTS, k=min(3, len(_MOCK_PRODUCTS)))
        return {"success": True, "results_count": len(products), "products": products}

    if action == "extract":
        domain = step.target.replace("https://www.", "").rstrip("/")
        products = [p for p in _MOCK_PRODUCTS if domain in p.get("source", "")]
        if not products:
            products = random.sample(_MOCK_PRODUCTS, k=min(3, len(_MOCK_PRODUCTS)))
        return {"success": True, "extracted": products}

    if action == "compare":
        sorted_products = sorted(_MOCK_PRODUCTS, key=lambda p: (-p["rating"], p["price"]))
        return {"success": True, "ranked": sorted_products}

    if action == "summarize":
        best = max(_MOCK_PRODUCTS, key=lambda p: p["rating"])
        cheapest = min(_MOCK_PRODUCTS, key=lambda p: p["price"])
        return {
            "success": True,
            "summary": (
                f"Best rated: {best['name']} (${best['price']}, {best['rating']} stars). "
                f"Best value: {cheapest['name']} (${cheapest['price']}, {cheapest['rating']} stars)."
            ),
            "best_rated": best,
            "best_value": cheapest,
        }

    return {"success": True, "message": f"Executed {action} on {step.target}"}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def execute_step(step: TaskStep) -> dict[str, Any]:
    """Execute a single TaskStep and return the result dict.

    Uses Nova Act when the API key is configured, otherwise returns mock data.
    """
    try:
        if settings.has_nova_act_key:
            result = await _execute_with_nova_act(step)
            logger.info("Step %s executed via Nova Act", step.id)
        else:
            # Simulate latency for realistic demo
            await asyncio.sleep(random.uniform(0.3, 1.0))
            result = _mock_result_for_step(step)
            logger.info("Step %s executed via mock fallback", step.id)
        return result
    except Exception as exc:
        logger.error("Step %s execution failed: %s", step.id, exc)
        return {"success": False, "error": str(exc)}
