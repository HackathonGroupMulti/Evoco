"""Task planner powered by Amazon Nova 2 Lite via Bedrock.

Decomposes a natural-language command into an ordered list of TaskSteps.
Falls back to a deterministic mock plan when AWS credentials are missing.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from backend.config import settings
from backend.models.task import TaskPlan, TaskStep

logger = logging.getLogger(__name__)

NOVA_MODEL_ID = "amazon.nova-lite-v1:0"

SYSTEM_PROMPT = """\
You are an autonomous task planner. Given a user command, decompose it into
a list of concrete browser-automation steps.

Reply ONLY with a JSON array. Each element must have:
  - "action": one of "navigate", "search", "extract", "compare", "summarize"
  - "target": URL or site name
  - "description": short human-readable description

Do NOT include any text outside the JSON array.
"""


def _build_bedrock_client() -> Any:
    return boto3.client(
        "bedrock-runtime",
        region_name=settings.aws_region,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
    )


def _call_nova(command: str) -> list[dict]:
    """Invoke Nova 2 Lite and parse the JSON step list."""
    client = _build_bedrock_client()
    body = {
        "messages": [{"role": "user", "content": [{"text": command}]}],
        "system": [{"text": SYSTEM_PROMPT}],
        "inferenceConfig": {"maxTokens": 1024, "temperature": 0.2},
    }
    response = client.invoke_model(
        modelId=NOVA_MODEL_ID,
        contentType="application/json",
        accept="application/json",
        body=json.dumps(body),
    )
    result = json.loads(response["body"].read())
    text = result["output"]["message"]["content"][0]["text"]
    return json.loads(text)


def _mock_plan(command: str) -> list[dict]:
    """Generate a reasonable mock plan based on keyword heuristics."""
    cmd = command.lower()

    sites: list[str] = []
    for kw, url in [
        ("amazon", "https://www.amazon.com"),
        ("best buy", "https://www.bestbuy.com"),
        ("newegg", "https://www.newegg.com"),
        ("walmart", "https://www.walmart.com"),
        ("ebay", "https://www.ebay.com"),
    ]:
        if kw in cmd:
            sites.append(url)

    if not sites:
        sites = ["https://www.amazon.com", "https://www.bestbuy.com"]

    steps: list[dict] = []
    for url in sites:
        steps.append(
            {"action": "navigate", "target": url, "description": f"Open {url}"}
        )
        steps.append(
            {
                "action": "search",
                "target": url,
                "description": f"Search for the requested product on {url}",
            }
        )
        steps.append(
            {
                "action": "extract",
                "target": url,
                "description": f"Extract top results from {url}",
            }
        )

    steps.append(
        {
            "action": "compare",
            "target": "all",
            "description": "Compare extracted results across sites",
        }
    )
    steps.append(
        {
            "action": "summarize",
            "target": "all",
            "description": "Produce final ranked summary",
        }
    )
    return steps


def _steps_from_raw(raw: list[dict], task_id: str) -> list[TaskStep]:
    """Convert raw dicts into TaskStep models with dependency chains."""
    steps: list[TaskStep] = []
    prev_id: str | None = None
    for item in raw:
        step = TaskStep(
            id=uuid.uuid4().hex[:8],
            action=item.get("action", "unknown"),
            target=item.get("target", ""),
            description=item.get("description", ""),
            depends_on=[prev_id] if prev_id else [],
        )
        steps.append(step)
        prev_id = step.id
    return steps


async def create_plan(command: str, task_id: str) -> TaskPlan:
    """Return a TaskPlan for the given command.

    Uses Nova 2 Lite when credentials exist, otherwise falls back to mock.
    """
    try:
        if settings.has_aws_credentials:
            raw = _call_nova(command)
            logger.info("Plan generated via Nova 2 Lite (%d steps)", len(raw))
        else:
            raw = _mock_plan(command)
            logger.info("Plan generated via mock fallback (%d steps)", len(raw))
    except (BotoCoreError, ClientError, json.JSONDecodeError) as exc:
        logger.warning("Nova planner failed, using mock: %s", exc)
        raw = _mock_plan(command)

    steps = _steps_from_raw(raw, task_id)
    return TaskPlan(task_id=task_id, original_command=command, steps=steps)
