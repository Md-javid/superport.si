import httpx

from app.ai.base import LLMProvider, ProviderNotConfigured


class AnthropicLLMProvider(LLMProvider):
    """Live LLM provider (integration scaffold, not exercised by the demo tests)."""

    name = "anthropic"

    def __init__(self, api_key: str | None, model: str):
        self.api_key = api_key
        self.model = model
        self.configured = bool(api_key)

    def complete(self, system: str, prompt: str, max_tokens: int = 600) -> str:
        if not self.configured:
            raise ProviderNotConfigured("ANTHROPIC_API_KEY is not set")
        response = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": self.api_key or "",
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": self.model,
                "max_tokens": max_tokens,
                "system": system,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=30,
        )
        response.raise_for_status()
        blocks = response.json().get("content", [])
        return "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
