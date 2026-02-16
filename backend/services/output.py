"""Output formatter — converts aggregated step results into JSON, CSV, or summary."""

from __future__ import annotations

import csv
import io
from typing import Any

from backend.models.task import OutputFormat, TaskPlan


def _is_product(item: Any) -> bool:
    """Check if a dict looks like a product entry (has at least a name)."""
    return isinstance(item, dict) and "name" in item


def _add_products(
    items: list[dict], products: list[dict[str, Any]], seen: set[str],
) -> None:
    """Dedupe and append product dicts."""
    for item in items:
        if not _is_product(item):
            continue
        ident = f"{item.get('name', '')}-{item.get('source', '')}"
        if ident not in seen:
            seen.add(ident)
            products.append(item)


def _collect_products(plan: TaskPlan) -> list[dict[str, Any]]:
    """Pull all product dicts from step results.

    Handles three result shapes:
      - Top-level keys: data["extracted"], data["products"], data["ranked"]
      - data["response"] is a list of products (browser extract steps)
      - data["response"] is a dict with nested "ranked"/"products"/"extracted"
    """
    products: list[dict[str, Any]] = []
    seen: set[str] = set()

    for step in plan.steps:
        if step.result is None or not isinstance(step.result, dict):
            continue
        data = step.result

        # Check top-level keys
        for key in ("extracted", "products", "ranked"):
            items = data.get(key)
            if isinstance(items, list):
                _add_products(items, products, seen)

        # Check inside "response" — browser steps put parsed data here,
        # LLM steps put a dict with nested keys here
        response = data.get("response")
        if isinstance(response, list):
            _add_products(response, products, seen)
        elif isinstance(response, dict):
            for key in ("extracted", "products", "ranked"):
                items = response.get(key)
                if isinstance(items, list):
                    _add_products(items, products, seen)

    return products


def _get_summary_text(plan: TaskPlan) -> str | None:
    """Extract summary text from the last summarize step (single reverse scan).

    Handles:
      - step.result["summary"] (top-level)
      - step.result["response"]["summary"] (LLM executor nesting)
      - step.result["response"] as a string
    """
    for s in reversed(plan.steps):
        if s.action != "summarize" or not s.result or not isinstance(s.result, dict):
            continue

        # Direct top-level summary
        text = s.result.get("summary")
        if text:
            return _stringify(text)

        # Nested inside "response" (LLM executor pattern)
        response = s.result.get("response")
        if isinstance(response, dict):
            text = response.get("summary")
            if text:
                return _stringify(text)
            # Fallback: recommendation field
            text = response.get("recommendation")
            if text:
                return _stringify(text)
        elif isinstance(response, str):
            return response.strip('"')
        elif isinstance(response, list):
            # List of sentences
            return " ".join(str(s) for s in response)

    return None


def _stringify(val: Any) -> str:
    """Convert a value to a clean display string."""
    if isinstance(val, str):
        return val.strip('"')
    if isinstance(val, list):
        return " ".join(str(s) for s in val)
    return str(val)


def _product_sort_key(p: dict) -> tuple:
    return (-p.get("rating", 0), p.get("price", 0))


def format_output(plan: TaskPlan, fmt: OutputFormat) -> Any:
    """Return the final formatted output for the task."""
    products = _collect_products(plan)
    summary = _get_summary_text(plan)

    # Sort once — O(n log n) — reused by all formatters
    sorted_products = sorted(products, key=_product_sort_key) if products else []

    if fmt == OutputFormat.JSON:
        return _as_json(plan, sorted_products, summary)
    if fmt == OutputFormat.CSV:
        return _as_csv(sorted_products)
    return _as_summary(plan, sorted_products, summary)


def _as_json(
    plan: TaskPlan, products: list[dict], summary: str | None,
) -> dict[str, Any]:
    return {
        "command": plan.original_command,
        "total_results": len(products),
        "results": products,
        "summary": summary,
    }


def _as_csv(products: list[dict]) -> str:
    if not products:
        return "No results found."
    buf = io.StringIO()
    writer = csv.DictWriter(
        buf, fieldnames=["name", "price", "rating", "source"], extrasaction="ignore",
    )
    writer.writeheader()
    writer.writerows(products)
    return buf.getvalue()


def _as_summary(
    plan: TaskPlan, products: list[dict], summary: str | None,
) -> str:
    lines: list[str] = [f"Results for: {plan.original_command}", ""]

    if products:
        for i, p in enumerate(products[:10], 1):
            price = p.get("price")
            rating = p.get("rating")
            price_str = f"${price}" if price else "N/A"
            rating_str = f"{rating} stars" if rating else "unrated"
            lines.append(
                f"{i}. {p.get('name', 'Unknown')} — {price_str} "
                f"({rating_str}) from {p.get('source', 'unknown')}"
            )
    elif summary:
        pass  # summary-only output below
    else:
        return "No results were found for your query."

    if summary:
        lines.append("")
        lines.append(summary)

    return "\n".join(lines)
