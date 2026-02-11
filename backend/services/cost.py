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


def estimate_llm_cost(input_text: str, output_text: str) -> float:
    """Estimate cost for a Nova 2 Lite invocation."""
    input_tokens = len(input_text.split()) * 1.3
    output_tokens = len(output_text.split()) * 1.3
    rates = COST_TABLE["nova-lite"]
    return round(
        (input_tokens / 1000 * rates["input_per_1k_tokens"])
        + (output_tokens / 1000 * rates["output_per_1k_tokens"]),
        6,
    )


def estimate_browser_cost() -> float:
    """Estimate cost for a Nova Act step."""
    return COST_TABLE["nova-act"]["per_step"]
