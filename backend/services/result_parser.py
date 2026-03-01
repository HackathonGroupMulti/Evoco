"""Multi-strategy result parser for Nova Act and LLM outputs.

Four fallback strategies (matching FaceCraft's robustness):
1. parsed_response — Nova Act's built-in schema-validated output
2. Standard JSON parse — json.loads() on raw response
3. JSON extraction — regex to find [{...}] in mixed text
4. LLM repair — send malformed output to Nova 2 Lite to fix

Use ``parse_result`` from sync (threaded) contexts and
``parse_result_async`` from async contexts — the async version runs
strategy 4 in a thread so the event loop is never blocked.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


def _strategies_1_to_3(raw: Any, parsed: Any = None) -> tuple[Any, bool]:
    """Run the first three parse strategies.

    Returns ``(result, success)`` where ``success`` is False only if all
    three strategies failed and LLM repair (strategy 4) should be attempted.
    """
    # Strategy 1: Use pre-parsed response if available and valid
    if parsed is not None:
        logger.debug("Parse strategy 1 (parsed_response): success")
        return parsed, True

    if not isinstance(raw, str):
        return raw, True

    text = raw.strip().strip('"')

    # Strategy 2: Direct JSON parse
    try:
        result = json.loads(text)
        logger.debug("Parse strategy 2 (json.loads): success")
        return result, True
    except (json.JSONDecodeError, TypeError):
        pass

    # Strategy 3: Regex extraction — find JSON array or object in mixed text.
    # Use greedy matching so nested structures like [[1,2],[3,4]] are captured
    # fully, then fall back to non-greedy if greedy produces invalid JSON.
    for label, greedy, nongreedy in (
        ("array",  r"\[[\s\S]*\]",  r"\[[\s\S]*?\]"),
        ("object", r"\{[\s\S]*\}",  r"\{[\s\S]*?\}"),
    ):
        for pattern in (greedy, nongreedy):
            match = re.search(pattern, text)
            if match:
                try:
                    result = json.loads(match.group())
                    logger.debug("Parse strategy 3 (regex %s): success", label)
                    return result, True
                except json.JSONDecodeError:
                    continue

    return text, False


def parse_result(raw: Any, parsed: Any = None) -> Any:
    """Try multiple strategies to extract structured data from a response.

    Runs strategies 1–4 synchronously. Safe to call from threads
    (e.g. inside ``asyncio.to_thread``). Do NOT call from async code
    directly — use ``parse_result_async`` instead to avoid blocking the
    event loop during strategy 4.

    Args:
        raw: The raw response string from Nova Act or LLM.
        parsed: The pre-parsed response from Nova Act (parsed_response field).

    Returns:
        Parsed data (usually a list or dict), or the raw string if all strategies fail.
    """
    result, ok = _strategies_1_to_3(raw, parsed)
    if ok:
        return result

    # result is the stripped text at this point
    text: str = result  # type: ignore[assignment]

    # Strategy 4: LLM repair (blocking — runs boto3 synchronously)
    try:
        repaired = _llm_repair(text)
        if repaired is not None:
            logger.debug("Parse strategy 4 (LLM repair): success")
            return repaired
    except Exception as exc:
        logger.debug("Parse strategy 4 (LLM repair) failed: %s", exc)

    logger.warning("All parse strategies failed, returning raw text")
    return text


async def parse_result_async(raw: Any, parsed: Any = None) -> Any:
    """Async version of ``parse_result``.

    Strategies 1–3 run synchronously (they are CPU-bound and fast).
    Strategy 4 (LLM repair via boto3) is dispatched to a thread pool so
    the event loop is never blocked by the network call.

    Use this from async code paths such as ``execute_with_llm``.
    """
    import asyncio

    result, ok = _strategies_1_to_3(raw, parsed)
    if ok:
        return result

    text: str = result  # type: ignore[assignment]

    # Strategy 4: run the blocking boto3 call in a thread
    try:
        repaired = await asyncio.to_thread(_llm_repair, text)
        if repaired is not None:
            logger.debug("Parse strategy 4 async (LLM repair): success")
            return repaired
    except Exception as exc:
        logger.debug("Parse strategy 4 async (LLM repair) failed: %s", exc)

    logger.warning("All parse strategies failed, returning raw text")
    return text


def _llm_repair(malformed: str) -> Any:
    """Send malformed output to Nova 2 Lite to fix JSON."""
    from backend.config import settings

    if not settings.has_aws_credentials:
        return None

    from backend.services.planner import _build_bedrock_client

    client = _build_bedrock_client()
    prompt = (
        "The following text was supposed to be valid JSON but is malformed. "
        "Extract the data and return ONLY valid JSON. No explanation.\n\n"
        f"Malformed input:\n{malformed[:2000]}"
    )

    body = {
        "messages": [{"role": "user", "content": [{"text": prompt}]}],
        "system": [{"text": "You are a JSON repair tool. Output ONLY valid JSON."}],
        "inferenceConfig": {"maxTokens": 1024, "temperature": 0.0},
    }
    response = client.invoke_model(
        modelId="amazon.nova-lite-v1:0",
        contentType="application/json",
        accept="application/json",
        body=json.dumps(body),
    )
    result = json.loads(response["body"].read())
    text = result["output"]["message"]["content"][0]["text"]

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try greedy first, then non-greedy
        for pattern in (r"[\[{][\s\S]*[}\]]", r"[\[{][\s\S]*?[}\]]"):
            match = re.search(pattern, text)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    continue
    return None
