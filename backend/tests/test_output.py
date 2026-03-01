"""Tests for the output formatter."""

from __future__ import annotations

import pytest

from backend.models.task import OutputFormat, TaskPlan, TaskStep
from backend.services.output import format_output


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _plan(steps: list[TaskStep], command: str = "find laptops") -> TaskPlan:
    plan = TaskPlan(task_id="test-task", original_command=command, steps=steps)
    return plan


def _search_step(products: list[dict], source: str = "amazon.com") -> TaskStep:
    step = TaskStep(action="search", target=f"https://www.{source}", description="Search")
    step.result = {"success": True, "products": products}
    return step


def _extract_step(products: list[dict], source: str = "bestbuy.com") -> TaskStep:
    step = TaskStep(action="extract", target=f"https://www.{source}", description="Extract")
    step.result = {"success": True, "extracted": products}
    return step


def _summarize_step(summary_text: str, nested: bool = False) -> TaskStep:
    step = TaskStep(action="summarize", target="all", description="Summarize")
    if nested:
        step.result = {"success": True, "response": {"summary": summary_text}}
    else:
        step.result = {"success": True, "summary": summary_text}
    return step


_PRODUCT_A = {"name": "Widget Pro", "price": 299.99, "rating": 4.8, "source": "amazon.com"}
_PRODUCT_B = {"name": "Gadget Plus", "price": 199.99, "rating": 4.2, "source": "bestbuy.com"}
_PRODUCT_C = {"name": "Gizmo Ultra", "price": 399.99, "rating": 4.5, "source": "newegg.com"}


# ---------------------------------------------------------------------------
# JSON output
# ---------------------------------------------------------------------------

class TestJsonOutput:
    def test_basic_json_structure(self) -> None:
        step = _search_step([_PRODUCT_A, _PRODUCT_B])
        result = format_output(_plan([step]), OutputFormat.JSON)
        assert result["command"] == "find laptops"
        assert result["total_results"] == 2
        assert len(result["results"]) == 2

    def test_products_sorted_by_rating_desc(self) -> None:
        step = _search_step([_PRODUCT_B, _PRODUCT_A])  # B has lower rating
        result = format_output(_plan([step]), OutputFormat.JSON)
        ratings = [p["rating"] for p in result["results"]]
        assert ratings == sorted(ratings, reverse=True)

    def test_deduplication_across_steps(self) -> None:
        s1 = _search_step([_PRODUCT_A])
        s2 = _search_step([_PRODUCT_A])  # same product again
        result = format_output(_plan([s1, s2]), OutputFormat.JSON)
        assert result["total_results"] == 1

    def test_summary_from_summarize_step(self) -> None:
        s1 = _search_step([_PRODUCT_A])
        s2 = _summarize_step("Widget Pro is the best deal.")
        result = format_output(_plan([s1, s2]), OutputFormat.JSON)
        assert result["summary"] == "Widget Pro is the best deal."

    def test_nested_summary_in_response(self) -> None:
        s1 = _summarize_step("Nested summary text.", nested=True)
        result = format_output(_plan([s1]), OutputFormat.JSON)
        assert result["summary"] == "Nested summary text."

    def test_no_results_returns_empty(self) -> None:
        result = format_output(_plan([]), OutputFormat.JSON)
        assert result["total_results"] == 0
        assert result["results"] == []
        assert result["summary"] is None

    def test_extract_step_products_included(self) -> None:
        step = _extract_step([_PRODUCT_B])
        result = format_output(_plan([step]), OutputFormat.JSON)
        assert result["total_results"] == 1
        assert result["results"][0]["name"] == "Gadget Plus"

    def test_ranked_products_from_response_dict(self) -> None:
        step = TaskStep(action="compare", target="all", description="Compare")
        step.result = {"success": True, "response": {"ranked": [_PRODUCT_A, _PRODUCT_C]}}
        result = format_output(_plan([step]), OutputFormat.JSON)
        assert result["total_results"] == 2


# ---------------------------------------------------------------------------
# CSV output
# ---------------------------------------------------------------------------

class TestCsvOutput:
    def test_csv_has_header(self) -> None:
        step = _search_step([_PRODUCT_A])
        csv = format_output(_plan([step]), OutputFormat.CSV)
        assert "name" in csv
        assert "price" in csv
        assert "rating" in csv

    def test_csv_contains_product_data(self) -> None:
        step = _search_step([_PRODUCT_A])
        csv = format_output(_plan([step]), OutputFormat.CSV)
        assert "Widget Pro" in csv
        assert "299.99" in csv

    def test_csv_no_results(self) -> None:
        result = format_output(_plan([]), OutputFormat.CSV)
        assert result == "No results found."

    def test_csv_multiple_products(self) -> None:
        step = _search_step([_PRODUCT_A, _PRODUCT_B, _PRODUCT_C])
        csv = format_output(_plan([step]), OutputFormat.CSV)
        lines = csv.strip().splitlines()
        assert len(lines) == 4  # header + 3 products


# ---------------------------------------------------------------------------
# Summary (text) output
# ---------------------------------------------------------------------------

class TestSummaryOutput:
    def test_summary_contains_product_names(self) -> None:
        step = _search_step([_PRODUCT_A, _PRODUCT_B])
        text = format_output(_plan([step]), OutputFormat.SUMMARY)
        assert "Widget Pro" in text
        assert "Gadget Plus" in text

    def test_summary_includes_command(self) -> None:
        step = _search_step([_PRODUCT_A])
        text = format_output(_plan([step], command="find the best laptop"), OutputFormat.SUMMARY)
        assert "find the best laptop" in text

    def test_summary_no_results_message(self) -> None:
        text = format_output(_plan([]), OutputFormat.SUMMARY)
        assert "No results" in text

    def test_summary_capped_at_ten(self) -> None:
        products = [
            {"name": f"Product {i}", "price": 100 + i, "rating": 4.0, "source": "amazon.com"}
            for i in range(15)
        ]
        step = _search_step(products)
        text = format_output(_plan([step]), OutputFormat.SUMMARY)
        # "11." should not appear in the numbered list
        assert "11." not in text

    def test_summary_appends_summary_text(self) -> None:
        s1 = _search_step([_PRODUCT_A])
        s2 = _summarize_step("Highly recommended.")
        text = format_output(_plan([s1, s2]), OutputFormat.SUMMARY)
        assert "Highly recommended." in text
