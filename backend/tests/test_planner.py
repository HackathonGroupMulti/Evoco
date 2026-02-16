"""Tests for the planner service."""

from backend.services.planner import _mock_plan, _steps_from_raw


class TestMockPlan:
    def test_detects_amazon(self) -> None:
        raw = _mock_plan("find laptops on amazon")
        targets = [s["target"] for s in raw]
        assert any("amazon.com" in t for t in targets)

    def test_detects_multiple_sites(self) -> None:
        raw = _mock_plan("compare prices on amazon and best buy")
        targets = [s["target"] for s in raw]
        assert any("amazon.com" in t for t in targets)
        assert any("bestbuy.com" in t for t in targets)

    def test_defaults_when_no_site_mentioned(self) -> None:
        raw = _mock_plan("find the cheapest headphones")
        assert len(raw) > 0
        assert raw[-1]["action"] == "summarize"

    def test_always_ends_with_compare_and_summarize(self) -> None:
        raw = _mock_plan("anything goes here")
        actions = [s["action"] for s in raw]
        assert actions[-2] == "compare"
        assert actions[-1] == "summarize"


class TestStepsFromRaw:
    def test_builds_dependency_chain(self) -> None:
        raw = [
            {"action": "navigate", "target": "https://a.com", "description": "go", "depends_on": []},
            {"action": "search", "target": "https://a.com", "description": "search", "depends_on": [0]},
        ]
        steps = _steps_from_raw(raw, "test-1")
        assert len(steps) == 2
        assert steps[0].depends_on == []
        assert steps[1].depends_on == [steps[0].id]

    def test_step_ids_are_unique(self) -> None:
        raw = [{"action": "a", "target": "", "description": ""} for _ in range(10)]
        steps = _steps_from_raw(raw, "test-2")
        ids = [s.id for s in steps]
        assert len(ids) == len(set(ids))
