"""Task planner powered by Amazon Nova 2 Lite via Bedrock.

Decomposes a natural-language command into a DAG of TaskSteps with
executor routing (browser vs LLM) and parallel branch support.
Falls back to a deterministic mock plan when AWS credentials are missing.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from backend.config import settings
from backend.models.task import ExecutorType, TaskPlan, TaskStep

logger = logging.getLogger(__name__)

NOVA_MODEL_ID = "amazon.nova-lite-v1:0"

SYSTEM_PROMPT = """\
You are an autonomous task planner. Given a user command, decompose it into
a list of concrete steps that an AI agent will execute.

There are TWO types of executors:
  - "browser": for steps that require visiting a website (navigate, search, extract, click, fill)
  - "llm": for steps that require reasoning over data (compare, analyze, rank, summarize)

Steps that can run in parallel should NOT depend on each other.
For example, searching Amazon and searching Best Buy are independent and can run in parallel.
Only add a dependency when a step truly needs the output of a prior step.

IMPORTANT — description rules for browser steps:
  - Keep descriptions SHORT (under 10 words). They drive a browser automation agent.
  - For "search" actions: only state WHAT to search for. Example: "espresso machines under $500"
  - For "extract" actions: just say "Extract product results"
  - For "navigate" actions: just say "Open <site name>"
  - NEVER include JSON, schemas, formatting instructions, or site names in search descriptions.

Reply ONLY with a JSON array. Each element must have:
  - "action": the type of action (e.g. "navigate", "search", "extract", "compare", "summarize")
  - "target": full URL (use "aggregated" for LLM steps that process collected data)
  - "description": short action-only instruction (see rules above)
  - "executor": "browser" or "llm"
  - "group": a short label for the branch (e.g. "amazon", "bestbuy", "analysis")
  - "depends_on": array of step indices (0-based) that must complete first. Empty [] for no deps.

Example for "compare laptops on Amazon and Best Buy":
[
  {"action": "navigate", "target": "https://www.amazon.com", "description": "Open Amazon", "executor": "browser", "group": "amazon", "depends_on": []},
  {"action": "search", "target": "https://www.amazon.com", "description": "laptops under $800", "executor": "browser", "group": "amazon", "depends_on": [0]},
  {"action": "extract", "target": "https://www.amazon.com", "description": "Extract product results", "executor": "browser", "group": "amazon", "depends_on": [1]},
  {"action": "navigate", "target": "https://www.bestbuy.com", "description": "Open Best Buy", "executor": "browser", "group": "bestbuy", "depends_on": []},
  {"action": "search", "target": "https://www.bestbuy.com", "description": "laptops under $800", "executor": "browser", "group": "bestbuy", "depends_on": [3]},
  {"action": "extract", "target": "https://www.bestbuy.com", "description": "Extract product results", "executor": "browser", "group": "bestbuy", "depends_on": [4]},
  {"action": "compare", "target": "aggregated", "description": "Compare and rank by value", "executor": "llm", "group": "analysis", "depends_on": [2, 5]},
  {"action": "summarize", "target": "aggregated", "description": "Final summary with recommendations", "executor": "llm", "group": "analysis", "depends_on": [6]}
]

Do NOT include any text outside the JSON array.
"""


_bedrock_client: Any = None


def _build_bedrock_client() -> Any:
    """Return a cached Bedrock client (boto3 clients are thread-safe)."""
    global _bedrock_client
    if _bedrock_client is None:
        _bedrock_client = boto3.client(
            "bedrock-runtime",
            region_name=settings.aws_region,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
        )
    return _bedrock_client


def _invoke_nova(user_text: str, temperature: float = 0.2) -> list[dict]:
    """Call Nova 2 Lite and parse the JSON step list from the response."""
    client = _build_bedrock_client()
    body = {
        "messages": [{"role": "user", "content": [{"text": user_text}]}],
        "system": [{"text": SYSTEM_PROMPT}],
        "inferenceConfig": {"maxTokens": 2048, "temperature": temperature},
    }
    response = client.invoke_model(
        modelId=NOVA_MODEL_ID,
        contentType="application/json",
        accept="application/json",
        body=json.dumps(body),
    )
    result = json.loads(response["body"].read())
    text = result["output"]["message"]["content"][0]["text"]

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if match:
            return json.loads(match.group())
        raise


def _call_nova(command: str) -> list[dict]:
    """Invoke Nova 2 Lite and parse the JSON step list."""
    return _invoke_nova(command, temperature=0.2)


def _call_nova_replan(command: str, failed_steps: list[dict], context: list[dict]) -> list[dict]:
    """Ask Nova 2 Lite for an alternative plan after failures."""
    replan_prompt = (
        f"Original command: {command}\n\n"
        f"These steps failed:\n{json.dumps(failed_steps, indent=2)}\n\n"
        f"Available context from successful steps:\n{json.dumps(context, indent=2)}\n\n"
        "Generate an alternative plan to accomplish the original command. "
        "Try different sites or approaches. Reply ONLY with a JSON array."
    )
    return _invoke_nova(replan_prompt, temperature=0.3)


def _mock_plan(command: str) -> list[dict]:
    """Generate a reasonable mock plan based on keyword heuristics."""
    cmd = command.lower()

    sites: list[tuple[str, str]] = []
    for kw, url in [
        ("amazon", "https://www.amazon.com"),
        ("best buy", "https://www.bestbuy.com"),
        ("newegg", "https://www.newegg.com"),
        ("walmart", "https://www.walmart.com"),
        ("ebay", "https://www.ebay.com"),
        ("linkedin", "https://www.linkedin.com"),
        ("indeed", "https://www.indeed.com"),
        ("zillow", "https://www.zillow.com"),
        ("yelp", "https://www.yelp.com"),
    ]:
        if kw in cmd:
            group = kw.replace(" ", "")
            sites.append((url, group))

    if not sites:
        sites = [("https://www.google.com", "google")]

    steps: list[dict] = []
    extract_indices: list[int] = []

    # Extract a short search query from the user command
    # Strip site names and filler words to get the core search intent
    search_query = cmd
    for kw in ["amazon", "best buy", "newegg", "walmart", "ebay",
               "linkedin", "indeed", "zillow", "yelp",
               "find me", "compare", "search for", "look for", "find",
               "from", " on ", " and "]:
        search_query = search_query.replace(kw, " ")
    search_query = " ".join(search_query.split()).strip()
    if not search_query:
        search_query = command  # fallback to original

    for url, group in sites:
        base_idx = len(steps)
        site_name = group.replace("bestbuy", "Best Buy").title()
        steps.append({
            "action": "navigate", "target": url,
            "description": f"Open {site_name}",
            "executor": "browser", "group": group, "depends_on": [],
        })
        steps.append({
            "action": "search", "target": url,
            "description": search_query,
            "executor": "browser", "group": group, "depends_on": [base_idx],
        })
        steps.append({
            "action": "extract", "target": url,
            "description": "Extract product results",
            "executor": "browser", "group": group, "depends_on": [base_idx + 1],
        })
        extract_indices.append(base_idx + 2)

    steps.append({
        "action": "compare", "target": "aggregated",
        "description": "Compare and rank extracted results across all sources",
        "executor": "llm", "group": "analysis", "depends_on": extract_indices,
    })
    steps.append({
        "action": "summarize", "target": "aggregated",
        "description": "Produce final summary with recommendations",
        "executor": "llm", "group": "analysis", "depends_on": [len(steps) - 1],
    })
    return steps


def _steps_from_raw(raw: list[dict], task_id: str) -> list[TaskStep]:
    """Convert raw dicts into TaskStep models, resolving index-based depends_on to IDs."""
    # First pass: create steps with generated IDs
    steps: list[TaskStep] = []
    for item in raw:
        step = TaskStep(
            id=uuid.uuid4().hex[:8],
            action=item.get("action", "unknown"),
            target=item.get("target", ""),
            description=item.get("description", ""),
            executor=ExecutorType(item.get("executor", "browser")),
            group=item.get("group", ""),
        )
        steps.append(step)

    # Second pass: resolve index-based depends_on to step IDs
    for i, item in enumerate(raw):
        raw_deps = item.get("depends_on", [])
        resolved: list[str] = []
        for dep in raw_deps:
            if isinstance(dep, int) and 0 <= dep < len(steps):
                resolved.append(steps[dep].id)
            elif isinstance(dep, str):
                resolved.append(dep)
        steps[i].depends_on = resolved

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


async def replan(command: str, failed_steps: list[dict], context: list[dict], task_id: str) -> TaskPlan:
    """Generate an alternative plan after step failures."""
    try:
        if settings.has_aws_credentials:
            raw = _call_nova_replan(command, failed_steps, context)
            logger.info("Re-plan generated via Nova 2 Lite (%d steps)", len(raw))
        else:
            raw = _mock_plan(command)
            logger.info("Re-plan generated via mock fallback (%d steps)", len(raw))
    except (BotoCoreError, ClientError, json.JSONDecodeError) as exc:
        logger.warning("Nova re-planner failed, using mock: %s", exc)
        raw = _mock_plan(command)

    steps = _steps_from_raw(raw, task_id)
    return TaskPlan(task_id=task_id, original_command=command, steps=steps)
