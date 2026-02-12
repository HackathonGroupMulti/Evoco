"""Step executor — routes to Nova Act (browser) or Nova 2 Lite (LLM).

Supports structured extraction schemas, retry with backoff,
and mock fallbacks when credentials are missing.
"""

from __future__ import annotations

import asyncio
import logging
import random
from typing import Any
from urllib.parse import quote_plus

from backend.config import settings
from backend.models.task import ExecutorType, TaskStep
from backend.services.cost import estimate_browser_cost
from backend.services.result_parser import parse_result
from backend.services.schemas import schema_for_action

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Nova Act integration (browser)
# ---------------------------------------------------------------------------

# Direct search URL patterns for known sites — bypasses popups, overlays,
# and bot detection that block Nova Act from using the site search UI.
_SEARCH_URL_PATTERNS: dict[str, str] = {
    "amazon.com": "https://www.amazon.com/s?k={q}",
    "bestbuy.com": "https://www.bestbuy.com/site/searchpage.jsp?st={q}",
    "newegg.com": "https://www.newegg.com/p/pl?d={q}",
    "walmart.com": "https://www.walmart.com/search?q={q}",
    "ebay.com": "https://www.ebay.com/sch/i.html?_nkw={q}",
    "target.com": "https://www.target.com/s?searchTerm={q}",
}


def _extract_search_query(step: TaskStep) -> str:
    """Pull the raw search terms out of the planner description."""
    desc = step.description
    target = step.target.replace("https://www.", "").replace("http://www.", "").rstrip("/")
    # Remove common planner wrappers
    for prefix in ("Search for ", "Search "):
        if desc.startswith(prefix):
            desc = desc[len(prefix):]
            break
    for suffix in (f" on {target}", f" on {step.target}"):
        if desc.lower().endswith(suffix.lower()):
            desc = desc[: -len(suffix)]
            break
    return desc.strip()


def _search_url_for(target: str, query: str) -> str | None:
    """Return a direct search URL if the site is known, else None."""
    domain = target.replace("https://www.", "").replace("http://www.", "").rstrip("/")
    pattern = _SEARCH_URL_PATTERNS.get(domain)
    if pattern:
        return pattern.format(q=quote_plus(query))
    return None


def _build_browser_prompt(step: TaskStep) -> str:
    """Build a short, focused prompt for the Nova Act browser agent.

    For search actions on known e-commerce sites, we navigate directly to the
    search results URL — this is far more reliable than having the browser
    agent fight through popups and overlays to find the search bar.
    """
    action = step.action

    if action == "navigate":
        return f"Go to {step.target}"
    if action == "search":
        query = _extract_search_query(step)
        url = _search_url_for(step.target, query)
        if url:
            # Skip the UI entirely — go straight to results
            return f"Go to {url}"
        # Unknown site — fall back to using the site search
        return f"Use the site search to find: {query}"
    if action == "extract":
        return "Extract the product names, prices, and ratings visible on this page"
    # Generic fallback
    return step.description


# Errors that should NOT be retried (they will fail again the same way)
_NO_RETRY_PATTERNS = ("ExceededMaxSteps", "ActExceededMaxSteps")


async def _execute_with_nova_act(step: TaskStep, pool: Any = None) -> dict[str, Any]:
    """Execute a single step using the Nova Act SDK."""
    from nova_act import NovaAct  # type: ignore[import-untyped]

    schema = schema_for_action(step.action)
    prompt = _build_browser_prompt(step)

    logger.info("Nova Act prompt for step %s: %s", step.id, prompt)

    def _run() -> dict[str, Any]:
        # Use pool session if available, otherwise create new
        if pool is not None:
            nova = pool.get_session(step.target)
            if nova is not None:
                return _run_in_session(nova, step, prompt, schema)

        with NovaAct(
            nova_act_api_key=settings.nova_act_api_key,
            starting_page=step.target if step.target.startswith("http") else "https://www.google.com",
            headless=settings.headless_browser,
            tty=False,
        ) as nova:
            return _run_in_session(nova, step, prompt, schema)

    return await asyncio.to_thread(_run)


_EXTRACT_ACTIONS = frozenset({"extract"})


def _run_in_session(
    nova: Any, step: TaskStep, prompt: str, schema: dict | None,
) -> dict[str, Any]:
    """Execute a step within an existing Nova Act session."""
    out: dict[str, Any] = {"success": True, "url": step.target,
                           "cost_usd": estimate_browser_cost(), "executor": "browser"}

    if step.action in _EXTRACT_ACTIONS:
        result = nova.act_get(prompt, schema=schema) if schema else nova.act_get(prompt)
        out["response"] = parse_result(result.response, getattr(result, "parsed_response", None))
    else:
        result = nova.act(prompt)
        out["steps_taken"] = result.metadata.num_steps_executed

    return out


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

# Pre-indexed by domain for O(1) lookup instead of O(n) filter per call
_MOCK_BY_DOMAIN: dict[str, list[dict[str, Any]]] = {}
for _p in _MOCK_PRODUCTS:
    _MOCK_BY_DOMAIN.setdefault(_p["source"], []).append(_p)

# Pre-computed sorted/aggregated results (avoid re-sorting on every call)
_MOCK_SORTED = sorted(_MOCK_PRODUCTS, key=lambda p: (-p["rating"], p["price"]))
_MOCK_BEST = max(_MOCK_PRODUCTS, key=lambda p: p["rating"])
_MOCK_CHEAPEST = min(_MOCK_PRODUCTS, key=lambda p: p["price"])


def _mock_result_for_step(step: TaskStep) -> dict[str, Any]:
    """Return plausible mock data for any step type."""
    action = step.action

    if action == "navigate":
        return {"success": True, "url": step.target, "page_title": f"Homepage — {step.target}"}

    if action in ("search", "extract"):
        domain = step.target.replace("https://www.", "").rstrip("/")
        products = _MOCK_BY_DOMAIN.get(domain)
        if not products:
            products = random.sample(_MOCK_PRODUCTS, k=min(3, len(_MOCK_PRODUCTS)))
        key = "products" if action == "search" else "extracted"
        result: dict[str, Any] = {"success": True, key: products}
        if action == "search":
            result["results_count"] = len(products)
        return result

    if action == "compare":
        return {"success": True, "ranked": _MOCK_SORTED}

    if action == "summarize":
        return {
            "success": True,
            "summary": (
                f"Best rated: {_MOCK_BEST['name']} (${_MOCK_BEST['price']}, {_MOCK_BEST['rating']} stars). "
                f"Best value: {_MOCK_CHEAPEST['name']} (${_MOCK_CHEAPEST['price']}, {_MOCK_CHEAPEST['rating']} stars)."
            ),
            "best_rated": _MOCK_BEST,
            "best_value": _MOCK_CHEAPEST,
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

            # Some errors are deterministic — retrying won't help
            exc_name = type(exc).__name__
            no_retry = any(pat in exc_name for pat in _NO_RETRY_PATTERNS)

            if no_retry:
                logger.error(
                    "Step %s (%s → %s) FAILED (non-retryable %s): %s",
                    step.id, step.action, step.target, exc_name, exc,
                )
                break

            if attempt < step.max_retries:
                wait = 2 ** attempt
                logger.warning(
                    "Step %s attempt %d failed (%s), retrying in %ds",
                    step.id, attempt + 1, exc, wait,
                )
                await asyncio.sleep(wait)
            else:
                logger.error(
                    "Step %s (%s → %s) FAILED after %d attempts: %s: %s",
                    step.id, step.action, step.target,
                    attempt + 1, type(exc).__name__, exc,
                    exc_info=True,
                )

    return {"success": False, "error": f"{type(last_error).__name__}: {last_error}"}
