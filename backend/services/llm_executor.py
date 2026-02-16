"""LLM executor for reasoning steps (compare, summarize, analyze, rank).

Uses Amazon Nova 2 Lite via Bedrock instead of browser automation.
Receives accumulated context from prior steps and produces structured output.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from backend.models.task import TaskStep
from backend.services.cost import estimate_llm_cost
from backend.services.result_parser import parse_result

logger = logging.getLogger(__name__)

NOVA_MODEL_ID = "amazon.nova-lite-v1:0"

_SYSTEM_PROMPTS = {
    "compare": (
        "You are a data analyst. You will receive extracted data from multiple sources. "
        "Compare the items and rank them. Consider price, ratings, features, and value. "
        "Reply with a JSON object containing:\n"
        '  - "ranked": array of items sorted best to worst\n'
        '  - "analysis": brief text explaining the ranking\n'
        "Reply ONLY with JSON."
    ),
    "summarize": (
        "You are a research summarizer. You will receive data and analysis from prior steps. "
        "Produce a clear, actionable summary with specific recommendations. "
        "Reply with a JSON object containing:\n"
        '  - "summary": a 2-4 sentence summary with the top recommendation\n'
        '  - "highlights": array of key findings (3-5 items)\n'
        '  - "recommendation": the single best option with reasoning\n'
        "Reply ONLY with JSON."
    ),
    "analyze": (
        "You are a research analyst. Analyze the provided data and extract insights. "
        "Reply with a JSON object containing:\n"
        '  - "findings": array of key insights\n'
        '  - "patterns": any patterns you noticed\n'
        '  - "gaps": any missing information\n'
        "Reply ONLY with JSON."
    ),
    "rank": (
        "You are a ranking engine. Rank the provided items by the criteria in the description. "
        "Reply with a JSON object containing:\n"
        '  - "ranked": array of items sorted best to worst with scores\n'
        '  - "criteria": the criteria used for ranking\n'
        "Reply ONLY with JSON."
    ),
}

_DEFAULT_SYSTEM = (
    "You are a helpful AI assistant. Process the provided data according to the instructions. "
    "Reply ONLY with JSON."
)


def _build_bedrock_client() -> Any:
    """Reuse the planner's cached Bedrock client."""
    from backend.services.planner import _build_bedrock_client as _get_client
    return _get_client()


async def execute_with_llm(step: TaskStep, context: list[dict[str, Any]]) -> dict[str, Any]:
    """Execute a reasoning step using Nova 2 Lite.

    Args:
        step: The TaskStep to execute.
        context: Accumulated results from completed prior steps.

    Returns:
        Result dict with "success" key.
    """
    import asyncio

    def _run() -> dict[str, Any]:
        system_prompt = _SYSTEM_PROMPTS.get(step.action, _DEFAULT_SYSTEM)
        user_prompt = (
            f"Task: {step.description}\n\n"
            f"Data from prior steps:\n{json.dumps(context, indent=2, default=str)}"
        )

        client = _build_bedrock_client()
        body = {
            "messages": [{"role": "user", "content": [{"text": user_prompt}]}],
            "system": [{"text": system_prompt}],
            "inferenceConfig": {"maxTokens": 2048, "temperature": 0.2},
        }

        response = client.invoke_model(
            modelId=NOVA_MODEL_ID,
            contentType="application/json",
            accept="application/json",
            body=json.dumps(body),
        )
        raw = json.loads(response["body"].read())
        text = raw["output"]["message"]["content"][0]["text"]

        # Parse the response using multi-strategy parser
        parsed = parse_result(text)

        return {
            "success": True,
            "response": parsed,
            "raw_text": text,
            "cost_usd": estimate_llm_cost(user_prompt, text),
            "executor": "llm",
        }

    return await asyncio.to_thread(_run)


async def mock_llm_execute(step: TaskStep, context: list[dict[str, Any]]) -> dict[str, Any]:
    """Mock LLM execution for when AWS credentials aren't available."""
    import asyncio
    import random

    await asyncio.sleep(random.uniform(0.1, 0.3))

    if step.action == "compare":
        return {
            "success": True,
            "response": {
                "ranked": context,
                "analysis": "Mock comparison: items ranked by available data.",
            },
            "cost_usd": 0.0001,
            "executor": "llm",
        }

    if step.action == "summarize":
        return {
            "success": True,
            "response": {
                "summary": "Mock summary of collected research data.",
                "highlights": ["Finding 1", "Finding 2", "Finding 3"],
                "recommendation": "Based on mock data, the first result is recommended.",
            },
            "cost_usd": 0.0001,
            "executor": "llm",
        }

    return {
        "success": True,
        "response": {"result": f"Mock {step.action} analysis of {len(context)} data points."},
        "cost_usd": 0.0001,
        "executor": "llm",
    }
