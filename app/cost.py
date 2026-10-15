# USD per 1M tokens: (input, output).
# EXAMPLE numbers. Replace with real prices from each model's page.
PRICES = {
    "meta-llama/Llama-3.1-8B-Instruct": (0.10, 0.20),
    "google/gemma-3-4b-it": (0.05, 0.10),
    "meta-llama/Llama-3.3-70B-Instruct": (0.60, 0.80),
    "Qwen/Qwen2.5-72B-Instruct": (0.60, 0.80),
    "openai/gpt-oss-120b": (0.50, 0.70),
}
DEFAULT_PRICE = (0.0, 0.0)


def compute_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    inp, out = PRICES.get(model, DEFAULT_PRICE)
    return (prompt_tokens * inp + completion_tokens * out) / 1_000_000