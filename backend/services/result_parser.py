"""Multi-strategy result parser for Nova Act and LLM outputs.

Four fallback strategies (matching FaceCraft's robustness):
1. parsed_response — Nova Act's built-in schema-validated output
2. Standard JSON parse — json.loads() on raw response
3. JSON extraction — regex to find [{...}] in mixed text
4. LLM repair — send malformed output to Nova 2 Lite to fix
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


def parse_result(raw: Any, parsed: Any = None) -> Any:
    """Try multiple strategies to extract structured data from a response.

    Args:
        raw: The raw response string from Nova Act or LLM.
        parsed: The pre-parsed response from Nova Act (parsed_response field).

    Returns:
        Parsed data (usually a list or dict), or the raw string if all strategies fail.
    """
    # Strategy 1: Use pre-parsed response if available and valid
    if parsed is not None:
        logger.debug("Parse strategy 1 (parsed_response): success")
        return parsed

    if not isinstance(raw, str):
        return raw

    text = raw.strip().strip('"')

    # Strategy 2: Direct JSON parse
    try:
        result = json.loads(text)
        logger.debug("Parse strategy 2 (json.loads): success")
        return result
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
                    return result
                except json.JSONDecodeError:
                    continue

    # Strategy 4: LLM repair (deferred — calls back to Bedrock)
    try:
        repaired = _llm_repair(text)
        if repaired is not None:
            logger.debug("Parse strategy 4 (LLM repair): success")
            return repaired
    except Exception as exc:
        logger.debug("Parse strategy 4 (LLM repair) failed: %s", exc)

    # All strategies failed — return raw text
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
