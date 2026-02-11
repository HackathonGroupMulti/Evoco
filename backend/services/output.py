"""Output formatter — converts aggregated step results into JSON, CSV, or summary."""

from __future__ import annotations

import csv
import io
import json
from typing import Any

from backend.models.task import OutputFormat, TaskPlan


def _collect_products(plan: TaskPlan) -> list[dict[str, Any]]:
    """Pull all product dicts from extract / compare / search step results."""
    products: list[dict[str, Any]] = []
    seen: set[str] = set()

    for step in plan.steps:
        if step.result is None:
            continue
        data = step.result if isinstance(step.result, dict) else {}

        for key in ("extracted", "products", "ranked"):
            for item in data.get(key, []):
                ident = f"{item.get('name', '')}-{item.get('source', '')}"
                if ident not in seen:
                    seen.add(ident)
                    products.append(item)

    return products


def format_output(plan: TaskPlan, fmt: OutputFormat) -> Any:
    """Return the final formatted output for the task."""
    products = _collect_products(plan)

    if fmt == OutputFormat.JSON:
        return _as_json(plan, products)
    if fmt == OutputFormat.CSV:
        return _as_csv(products)
    return _as_summary(plan, products)


def _as_json(plan: TaskPlan, products: list[dict]) -> dict[str, Any]:
    sorted_products = sorted(products, key=lambda p: (-p.get("rating", 0), p.get("price", 0)))
    summary_step = next((s for s in reversed(plan.steps) if s.action == "summarize"), None)
    return {
        "command": plan.original_command,
        "total_results": len(sorted_products),
        "results": sorted_products,
        "summary": summary_step.result.get("summary") if summary_step and summary_step.result else None,
    }


def _as_csv(products: list[dict]) -> str:
    if not products:
        return "No results found."
    buf = io.StringIO()
    fields = ["name", "price", "rating", "source"]
    writer = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for p in sorted(products, key=lambda p: (-p.get("rating", 0), p.get("price", 0))):
        writer.writerow(p)
    return buf.getvalue()


def _as_summary(plan: TaskPlan, products: list[dict]) -> str:
    if not products:
        return "No results were found for your query."

    lines: list[str] = [f"Results for: {plan.original_command}", ""]

    sorted_products = sorted(products, key=lambda p: (-p.get("rating", 0), p.get("price", 0)))
    for i, p in enumerate(sorted_products[:10], 1):
        lines.append(
            f"{i}. {p.get('name', 'Unknown')} — ${p.get('price', '?')} "
            f"({p.get('rating', '?')} stars) from {p.get('source', 'unknown')}"
        )

    summary_step = next((s for s in reversed(plan.steps) if s.action == "summarize"), None)
    if summary_step and summary_step.result:
        lines.append("")
        lines.append(summary_step.result.get("summary", ""))

    return "\n".join(lines)
