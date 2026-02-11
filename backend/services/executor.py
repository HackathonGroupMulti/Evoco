"""Step executor — routes to Nova Act (browser) or Nova 2 Lite (LLM).

Supports structured extraction schemas, retry with backoff,
and mock fallbacks when credentials are missing.
"""

from __future__ import annotations

import asyncio
import logging
import random
from typing import Any

from backend.config import settings
from backend.models.task import ExecutorType, TaskStep
from backend.services.cost import estimate_browser_cost
from backend.services.result_parser import parse_result
from backend.services.schemas import schema_for_action

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Nova Act integration (browser)
# ---------------------------------------------------------------------------

async def _execute_with_nova_act(step: TaskStep, pool: Any = None) -> dict[str, Any]:
    """Execute a single step using the Nova Act SDK."""
    from nova_act import NovaAct  # type: ignore[import-untyped]

    extract_actions = {"search", "extract"}
    schema = schema_for_action(step.action)

    def _run() -> dict[str, Any]:
        # Use pool session if available, otherwise create new
        if pool is not None:
            nova = pool.get_session(step.target)
            if nova is not None:
                return _run_in_session(nova, step, extract_actions, schema)

        with NovaAct(
            nova_act_api_key=settings.nova_act_api_key,
            starting_page=step.target if step.target.startswith("http") else "https://www.google.com",
            headless=settings.headless_browser,
            tty=False,
        ) as nova:
            return _run_in_session(nova, step, extract_actions, schema)

    return await asyncio.to_thread(_run)


def _run_in_session(
    nova: Any, step: TaskStep, extract_actions: set, schema: dict | None
) -> dict[str, Any]:
    """Execute a step within an existing Nova Act session."""
    if step.action in extract_actions and schema:
        result = nova.act_get(step.description, schema=schema)
        parsed = parse_result(result.response, getattr(result, "parsed_response", None))
        return {
            "success": True,
            "response": parsed,
            "url": step.target,
            "cost_usd": estimate_browser_cost(),
            "executor": "browser",
        }
    elif step.action in extract_actions:
        result = nova.act_get(step.description)
        parsed = parse_result(result.response)
        return {
            "success": True,
            "response": parsed,
            "url": step.target,
            "cost_usd": estimate_browser_cost(),
            "executor": "browser",
        }
    else:
        result = nova.act(step.description)
        return {
            "success": True,
            "url": step.target,
            "steps_taken": result.metadata.num_steps_executed,
            "cost_usd": estimate_browser_cost(),
            "executor": "browser",
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

async def execute_step(
    step: TaskStep,
    context: list[dict[str, Any]] | None = None,
    pool: Any = None,
) -> dict[str, Any]:
    """Execute a single TaskStep and return the result dict.

    Routes to browser (Nova Act) or LLM (Nova 2 Lite) based on step.executor.
    Includes retry with exponential backoff.
    """
    from backend.services.llm_executor import execute_with_llm, mock_llm_execute

    context = context or []
    last_error: Exception | None = None

    for attempt in range(step.max_retries + 1):
        try:
            if step.executor == ExecutorType.LLM:
                # LLM steps — reasoning over collected data
                if settings.has_aws_credentials:
                    result = await execute_with_llm(step, context)
                else:
                    result = await mock_llm_execute(step, context)
                logger.info("Step %s executed via LLM (attempt %d)", step.id, attempt + 1)
            else:
                # Browser steps — Nova Act
                if settings.has_nova_act_key:
                    result = await _execute_with_nova_act(step, pool=pool)
                    logger.info("Step %s executed via Nova Act (attempt %d)", step.id, attempt + 1)
                else:
                    await asyncio.sleep(random.uniform(0.3, 1.0))
                    result = _mock_result_for_step(step)
                    logger.info("Step %s executed via mock (attempt %d)", step.id, attempt + 1)

            step.retries = attempt
            step.cost_usd = result.get("cost_usd", 0.0)
            return result

        except Exception as exc:
            last_error = exc
            step.retries = attempt + 1
            if attempt < step.max_retries:
                wait = 2 ** attempt
                logger.warning(
                    "Step %s attempt %d failed (%s), retrying in %ds",
                    step.id, attempt + 1, exc, wait,
                )
                await asyncio.sleep(wait)
            else:
                logger.error("Step %s failed after %d attempts: %s", step.id, attempt + 1, exc)

    return {"success": False, "error": str(last_error)}
