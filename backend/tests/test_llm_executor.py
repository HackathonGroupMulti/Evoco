"""Tests for the LLM executor (reasoning steps)."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.models.task import TaskStep
from backend.services.llm_executor import execute_with_llm, mock_llm_execute


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _step(action: str, description: str = "Do something") -> TaskStep:
    return TaskStep(action=action, target="all", description=description)


def _bedrock_response(text: str) -> MagicMock:
    """Build a fake boto3 invoke_model response containing ``text``."""
    body = MagicMock()
    body.read.return_value = json.dumps({
        "output": {"message": {"content": [{"text": text}]}}
    }).encode()
    client = MagicMock()
    client.invoke_model.return_value = {"body": body}
    return client


# ---------------------------------------------------------------------------
# execute_with_llm
# ---------------------------------------------------------------------------

class TestExecuteWithLlm:
    @pytest.mark.asyncio
    async def test_compare_returns_ranked_list(self) -> None:
        payload = json.dumps({"ranked": [{"name": "A"}], "analysis": "ok"})
        client = _bedrock_response(payload)

        with (
            patch("backend.services.llm_executor._build_bedrock_client", return_value=client),
            patch("backend.services.llm_executor.parse_result_async", new=AsyncMock(return_value={"ranked": [{"name": "A"}], "analysis": "ok"})),
        ):
            result = await execute_with_llm(_step("compare"), context=[{"data": 1}])

        assert result["success"] is True
        assert result["executor"] == "llm"
        assert "response" in result
        assert "cost_usd" in result

    @pytest.mark.asyncio
    async def test_summarize_returns_summary(self) -> None:
        payload = json.dumps({"summary": "great", "highlights": [], "recommendation": "buy A"})
        client = _bedrock_response(payload)

        with (
            patch("backend.services.llm_executor._build_bedrock_client", return_value=client),
            patch("backend.services.llm_executor.parse_result_async", new=AsyncMock(return_value={"summary": "great"})),
        ):
            result = await execute_with_llm(_step("summarize"), context=[])

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_unknown_action_uses_default_system_prompt(self) -> None:
        payload = json.dumps({"result": "something"})
        client = _bedrock_response(payload)

        with (
            patch("backend.services.llm_executor._build_bedrock_client", return_value=client),
            patch("backend.services.llm_executor.parse_result_async", new=AsyncMock(return_value={"result": "something"})),
        ):
            result = await execute_with_llm(_step("custom_action"), context=[])

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_malformed_bedrock_response_propagates(self) -> None:
        """If boto3 returns garbage, execute_with_llm should raise (caller retries)."""
        bad_client = MagicMock()
        bad_client.invoke_model.side_effect = RuntimeError("service error")

        with patch("backend.services.llm_executor._build_bedrock_client", return_value=bad_client):
            with pytest.raises(RuntimeError, match="service error"):
                await execute_with_llm(_step("compare"), context=[])

    @pytest.mark.asyncio
    async def test_context_is_serialised_into_prompt(self) -> None:
        """Verify that context data is included in the prompt sent to Bedrock."""
        captured: list[dict] = []

        def _fake_invoke_model(**kwargs: object) -> dict:
            captured.append(json.loads(str(kwargs["body"])))
            body = MagicMock()
            body.read.return_value = json.dumps({
                "output": {"message": {"content": [{"text": '{"r": 1}'}]}}
            }).encode()
            return {"body": body}

        client = MagicMock()
        client.invoke_model.side_effect = _fake_invoke_model

        context = [{"product": "Widget", "price": 9.99}]
        with (
            patch("backend.services.llm_executor._build_bedrock_client", return_value=client),
            patch("backend.services.llm_executor.parse_result_async", new=AsyncMock(return_value={"r": 1})),
        ):
            await execute_with_llm(_step("compare", "Find the best"), context=context)

        body_sent = captured[0]
        user_text = body_sent["messages"][0]["content"][0]["text"]
        assert "Widget" in user_text
        assert "9.99" in user_text


# ---------------------------------------------------------------------------
# mock_llm_execute
# ---------------------------------------------------------------------------

class TestMockLlmExecute:
    @pytest.mark.asyncio
    async def test_compare_mock(self) -> None:
        result = await mock_llm_execute(_step("compare"), context=[{"x": 1}])
        assert result["success"] is True
        assert "ranked" in result["response"]

    @pytest.mark.asyncio
    async def test_summarize_mock(self) -> None:
        result = await mock_llm_execute(_step("summarize"), context=[])
        assert result["success"] is True
        assert "summary" in result["response"]
        assert "highlights" in result["response"]

    @pytest.mark.asyncio
    async def test_unknown_action_mock(self) -> None:
        result = await mock_llm_execute(_step("custom"), context=[1, 2, 3])
        assert result["success"] is True
        assert "3 data points" in result["response"]["result"]

    @pytest.mark.asyncio
    async def test_cost_is_non_negative(self) -> None:
        result = await mock_llm_execute(_step("compare"), context=[])
        assert result["cost_usd"] >= 0
