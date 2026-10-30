"""Transparent estimate helpers for the public demo; not billing-grade accounting."""
from __future__ import annotations

MODEL_RATES_USD_PER_MILLION = {
    "nvidia/nemotron-3-super-120b-a12b": {"input": 0.30, "output": 0.90},
    "nvidia/Nemotron-3-Nano-30B": {"input": 0.06, "output": 0.24},
}

def estimate_completion_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate one completion from public rate-card values; does not include other calls."""
    if model not in MODEL_RATES_USD_PER_MILLION:
        raise ValueError(f"No public demo rate configured for model {model!r}")
    if input_tokens < 0 or output_tokens < 0:
        raise ValueError("Token counts must be non-negative")
    rates = MODEL_RATES_USD_PER_MILLION[model]
    return (input_tokens * rates["input"] + output_tokens * rates["output"]) / 1_000_000
