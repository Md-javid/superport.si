from app.ai.base import LLMProvider


class MockLLMProvider(LLMProvider):
    """Fallback LLM provider when cloud keys are not provisioned."""

    name = "horizon-llm"
    configured = True

    def complete(self, system: str, prompt: str, max_tokens: int = 600) -> str:
        return ""
