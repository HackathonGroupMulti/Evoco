"""Tests for the multi-strategy result parser."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from backend.services.result_parser import parse_result, parse_result_async


# ---------------------------------------------------------------------------
# Strategy 1: pre-parsed response
# ---------------------------------------------------------------------------

class TestStrategy1ParsedResponse:
    def test_returns_parsed_when_provided(self) -> None:
        parsed = [{"name": "Widget", "price": 9.99}]
        assert parse_result("ignored", parsed=parsed) is parsed

    def test_parsed_none_falls_through(self) -> None:
        """None parsed should fall through to strategy 2."""
        result = parse_result('{"key": "val"}', parsed=None)
        assert result == {"key": "val"}


# ---------------------------------------------------------------------------
# Strategy 2: json.loads
# ---------------------------------------------------------------------------

class TestStrategy2DirectJsonParse:
    def test_parses_object(self) -> None:
        assert parse_result('{"a": 1}') == {"a": 1}

    def test_parses_array(self) -> None:
        assert parse_result('[1, 2, 3]') == [1, 2, 3]

    def test_strips_outer_quotes(self) -> None:
        # Some LLMs return the JSON wrapped in extra quotes
        assert parse_result('"{\\"a\\": 1}"') == {"a": 1}

    def test_non_string_passthrough(self) -> None:
        data = {"already": "parsed"}
        assert parse_result(data) is data

    def test_none_passthrough(self) -> None:
        assert parse_result(None) is None


# ---------------------------------------------------------------------------
# Strategy 3: regex extraction
# ---------------------------------------------------------------------------

class TestStrategy3RegexExtraction:
    def test_extracts_array_from_mixed_text(self) -> None:
        raw = 'Here are the results: [{"name": "A"}] — enjoy!'
        result = parse_result(raw)
        assert result == [{"name": "A"}]

    def test_extracts_object_from_mixed_text(self) -> None:
        raw = 'The data is: {"score": 42} as expected.'
        result = parse_result(raw)
        assert result == {"score": 42}

    def test_nested_array(self) -> None:
        raw = 'Result: [[1, 2], [3, 4]]'
        result = parse_result(raw)
        assert result == [[1, 2], [3, 4]]

    def test_no_json_returns_raw_text(self) -> None:
        raw = "No JSON here at all."
        # Suppress strategy 4 so we're only testing the regex fallback path
        with patch("backend.services.result_parser._llm_repair", return_value=None):
            result = parse_result(raw)
        assert result == raw


# ---------------------------------------------------------------------------
# Strategy 4: LLM repair
# ---------------------------------------------------------------------------

class TestStrategy4LlmRepair:
    def _make_bedrock_response(self, text: str) -> MagicMock:
        body = MagicMock()
        body.read.return_value = json.dumps({
            "output": {"message": {"content": [{"text": text}]}}
        }).encode()
        return MagicMock(body=body)

    def test_repair_succeeds(self) -> None:
        repaired_json = '[{"name": "Fixed"}]'
        with (
            patch("backend.services.result_parser._llm_repair") as mock_repair,
        ):
            mock_repair.return_value = [{"name": "Fixed"}]
            result = parse_result("broken json {{{{")
        assert result == [{"name": "Fixed"}]

    def test_repair_exception_falls_back_to_raw(self) -> None:
        with patch("backend.services.result_parser._llm_repair", side_effect=RuntimeError("boom")):
            result = parse_result("broken json {{{{")
        assert result == "broken json {{{{"

    def test_repair_returns_none_falls_back_to_raw(self) -> None:
        with patch("backend.services.result_parser._llm_repair", return_value=None):
            result = parse_result("still broken")
        assert result == "still broken"


# ---------------------------------------------------------------------------
# Async variant
# ---------------------------------------------------------------------------

class TestParseResultAsync:
    @pytest.mark.asyncio
    async def test_strategies_1_to_3_still_work(self) -> None:
        parsed = {"pre": "parsed"}
        assert await parse_result_async("ignored", parsed=parsed) is parsed
        assert await parse_result_async('{"a": 1}') == {"a": 1}
        assert await parse_result_async('text [{"x": 2}]') == [{"x": 2}]

    @pytest.mark.asyncio
    async def test_strategy_4_runs_in_thread(self) -> None:
        """Strategy 4 should be called via asyncio.to_thread."""
        with patch("backend.services.result_parser._llm_repair", return_value={"fixed": True}) as mock_repair:
            result = await parse_result_async("unparse-able garbage !!!")
        assert result == {"fixed": True}
        mock_repair.assert_called_once()

    @pytest.mark.asyncio
    async def test_strategy_4_failure_returns_raw(self) -> None:
        with patch("backend.services.result_parser._llm_repair", return_value=None):
            result = await parse_result_async("garbage")
        assert result == "garbage"
