"""
Model clients. Each returns (text, info) where info has seconds and token counts.

  gemini:<model>   Google Gemini through google-genai (needs GEMINI_API_KEY)
  mlx:<repo>       a local model on Apple Silicon through MLX (no network, no API cost)

Everything runs at temperature 0.
"""

import copy
import os
import time

MODELS = {
    "gemini-flash-lite": "gemini:gemini-3.5-flash-lite",
    "qwen-coder-7b": "mlx:mlx-community/Qwen2.5-Coder-7B-Instruct-4bit",
    "qwen-coder-3b": "mlx:mlx-community/Qwen2.5-Coder-3B-Instruct-4bit",
}
MAX_OUTPUT_TOKENS = 600


class GeminiClient:
    def __init__(self, model: str):
        from google import genai
        from google.genai import types
        key = os.getenv("GEMINI_API_KEY", "")
        if not key or key == "your_key_here":
            raise RuntimeError("GEMINI_API_KEY is not set in .env")
        self.model, self.types = model, types
        self.client = genai.Client(api_key=key, http_options=types.HttpOptions(
            timeout=60_000, retry_options=types.HttpRetryOptions(attempts=1)))

    def generate(self, system: str, user: str):
        cfg = self.types.GenerateContentConfig(system_instruction=system, temperature=0,
                                               max_output_tokens=MAX_OUTPUT_TOKENS)
        delay, last = 4.0, None
        for attempt in range(6):          # rate limits and 5xx: wait and try again
            start = time.perf_counter()
            try:
                reply = self.client.models.generate_content(model=self.model, contents=user, config=cfg)
                usage = reply.usage_metadata
                return (reply.text or ""), {
                    "seconds": round(time.perf_counter() - start, 3), "attempts": attempt + 1,
                    "tokens_in": getattr(usage, "prompt_token_count", None),
                    "tokens_out": getattr(usage, "candidates_token_count", None)}
            except Exception as exc:  # noqa: BLE001
                last = exc
                code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
                if code not in (429, 500, 502, 503, 504) and "timed out" not in str(exc).lower():
                    break
                time.sleep(delay)
                delay = min(delay * 2, 60)
        raise RuntimeError(f"Gemini call failed: {type(last).__name__}: {str(last)[:300]}")


class MLXClient:
    """Local model. The long context block is processed once per setup and reused (prompt cache)."""

    def __init__(self, repo: str):
        from mlx_lm import load
        self.model, self.tokenizer = load(repo)
        self._prefix_key, self._prefix_tokens, self._prefix_cache = None, None, None

    def _tokens(self, system: str, user: str):
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        return self.tokenizer.apply_chat_template(messages, add_generation_prompt=True, tokenize=True)

    def _cached_prefix(self, system: str, user: str, tokens: list):
        """KV cache for everything up to the question, built once per (system, context)."""
        from mlx_lm.models.cache import make_prompt_cache
        import mlx.core as mx
        marker = "\n\n# Question\n"
        context = user.split(marker)[0]
        key = (system, context)
        if key != self._prefix_key:
            other = self._tokens(system, context + marker + "x")
            n = 0
            while n < min(len(tokens), len(other)) and tokens[n] == other[n]:
                n += 1
            n = max(n - 8, 0)             # stay clear of the boundary tokens
            cache = make_prompt_cache(self.model)
            if n:
                self.model(mx.array(tokens[:n])[None], cache=cache)
                mx.eval([c.state for c in cache])
            self._prefix_key, self._prefix_tokens, self._prefix_cache = key, tokens[:n], cache
        return self._prefix_tokens, self._prefix_cache

    def generate(self, system: str, user: str):
        from mlx_lm import stream_generate
        from mlx_lm.sample_utils import make_sampler
        start = time.perf_counter()
        tokens = self._tokens(system, user)
        prefix, cache = self._cached_prefix(system, user, tokens)
        if prefix and tokens[:len(prefix)] == prefix:
            prompt, prompt_cache = tokens[len(prefix):], copy.deepcopy(cache)
        else:
            prompt, prompt_cache = tokens, None
        text, out = "", 0
        for chunk in stream_generate(self.model, self.tokenizer, prompt, max_tokens=MAX_OUTPUT_TOKENS,
                                     sampler=make_sampler(temp=0.0), prompt_cache=prompt_cache):
            text += chunk.text
            out += 1
        return text, {"seconds": round(time.perf_counter() - start, 3), "attempts": 1,
                      "tokens_in": len(tokens), "tokens_out": out}


def get_client(name: str):
    spec = MODELS.get(name, name)
    kind, _, model = spec.partition(":")
    if kind == "gemini":
        return GeminiClient(model)
    if kind == "mlx":
        return MLXClient(model)
    raise ValueError(f"unknown model: {name}")
