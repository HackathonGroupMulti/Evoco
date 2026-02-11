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


def _collect_responses(plan: TaskPlan) -> list[dict[str, str]]:
    """Pull text responses from Nova Act step results."""
    responses: list[dict[str, str]] = []
    for step in plan.steps:
        if step.result is None or not isinstance(step.result, dict):
            continue
        response = step.result.get("response")
        if response:
            responses.append({
                "action": step.action,
                "description": step.description,
                "response": response.strip('"') if isinstance(response, str) else str(response),
            })
    return responses


def format_output(plan: TaskPlan, fmt: OutputFormat) -> Any:
    """Return the final formatted output for the task."""
    products = _collect_products(plan)
    responses = _collect_responses(plan)

    if fmt == OutputFormat.JSON:
        return _as_json(plan, products, responses)
    if fmt == OutputFormat.CSV:
        return _as_csv(products, responses)
    return _as_summary(plan, products, responses)


def _as_json(plan: TaskPlan, products: list[dict], responses: list[dict]) -> dict[str, Any]:
    summary_step = next((s for s in reversed(plan.steps) if s.action == "summarize"), None)
    summary = None
    if summary_step and summary_step.result:
        summary = summary_step.result.get("summary") or summary_step.result.get("response", "")
        if isinstance(summary, str):
            summary = summary.strip('"')

    if products:
        sorted_products = sorted(products, key=lambda p: (-p.get("rating", 0), p.get("price", 0)))
        return {
            "command": plan.original_command,
            "total_results": len(sorted_products),
            "results": sorted_products,
            "summary": summary,
        }

    return {
        "command": plan.original_command,
        "total_results": len(responses),
        "steps": responses,
        "summary": summary,
    }


def _as_csv(products: list[dict], responses: list[dict]) -> str:
    if products:
        buf = io.StringIO()
        fields = ["name", "price", "rating", "source"]
        writer = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for p in sorted(products, key=lambda p: (-p.get("rating", 0), p.get("price", 0))):
            writer.writerow(p)
        return buf.getvalue()

    if responses:
        buf = io.StringIO()
        fields = ["action", "description", "response"]
        writer = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for r in responses:
            writer.writerow(r)
        return buf.getvalue()

    return "No results found."


def _as_summary(plan: TaskPlan, products: list[dict], responses: list[dict]) -> str:
    lines: list[str] = [f"Results for: {plan.original_command}", ""]

    if products:
        sorted_products = sorted(products, key=lambda p: (-p.get("rating", 0), p.get("price", 0)))
        for i, p in enumerate(sorted_products[:10], 1):
            lines.append(
                f"{i}. {p.get('name', 'Unknown')} — ${p.get('price', '?')} "
                f"({p.get('rating', '?')} stars) from {p.get('source', 'unknown')}"
            )
    elif responses:
        for r in responses:
            lines.append(f"[{r['action']}] {r['response']}")
    else:
        return "No results were found for your query."

    summary_step = next((s for s in reversed(plan.steps) if s.action == "summarize"), None)
    if summary_step and summary_step.result:
        summary = summary_step.result.get("summary") or summary_step.result.get("response", "")
        if isinstance(summary, str):
            summary = summary.strip('"')
        lines.append("")
        lines.append(summary)

    return "\n".join(lines)
