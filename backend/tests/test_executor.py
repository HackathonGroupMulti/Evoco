"""Tests for the executor service."""

from backend.models.task import TaskStep
from backend.services.executor import _mock_result_for_step


class TestMockExecutor:
    def test_navigate(self) -> None:
        step = TaskStep(action="navigate", target="https://www.amazon.com", description="Open Amazon")
        result = _mock_result_for_step(step)
        assert result["success"] is True
        assert "amazon.com" in result["url"]

    def test_search_returns_products(self) -> None:
        step = TaskStep(action="search", target="https://www.amazon.com", description="Search")
        result = _mock_result_for_step(step)
        assert result["success"] is True
        assert len(result["products"]) > 0

    def test_extract_returns_products(self) -> None:
        step = TaskStep(action="extract", target="https://www.bestbuy.com", description="Extract")
        result = _mock_result_for_step(step)
        assert result["success"] is True
        assert len(result["extracted"]) > 0

    def test_compare_returns_ranked_list(self) -> None:
        step = TaskStep(action="compare", target="all", description="Compare")
        result = _mock_result_for_step(step)
        assert result["success"] is True
        assert len(result["ranked"]) > 0
        # Should be sorted by rating descending
        ratings = [p["rating"] for p in result["ranked"]]
        assert ratings == sorted(ratings, reverse=True)

    def test_summarize_returns_best(self) -> None:
        step = TaskStep(action="summarize", target="all", description="Summarize")
        result = _mock_result_for_step(step)
        assert result["success"] is True
        assert "best_rated" in result
        assert "best_value" in result
        assert "summary" in result

    def test_unknown_action(self) -> None:
        step = TaskStep(action="custom_thing", target="somewhere", description="Do it")
        result = _mock_result_for_step(step)
        assert result["success"] is True
