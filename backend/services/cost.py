"""Cost tracking for pipeline execution."""

from __future__ import annotations

# Approximate costs per model invocation
COST_TABLE = {
    "nova-lite": {
        "input_per_1k_tokens": 0.00006,
        "output_per_1k_tokens": 0.00024,
    },
    "nova-act": {
        "per_step": 0.002,
    },
}


def _count_tokens(text: str) -> int:
    """Estimate token count using the standard ~4 chars/token heuristic."""
    return max(1, len(text) // 4)


def estimate_llm_cost(input_text: str, output_text: str) -> float:
    """Estimate cost for a Nova 2 Lite invocation."""
    input_tokens = _count_tokens(input_text)
    output_tokens = _count_tokens(output_text)
    rates = COST_TABLE["nova-lite"]
    return round(
        (input_tokens / 1000 * rates["input_per_1k_tokens"])
        + (output_tokens / 1000 * rates["output_per_1k_tokens"]),
        6,
    )


def estimate_browser_cost() -> float:
    """Estimate cost for a Nova Act step."""
    return COST_TABLE["nova-act"]["per_step"]
