from app.ai.base import LLMProvider


class MockLLMProvider(LLMProvider):
    """Demo LLM. Never calls the network; services fall back to rule-based text."""

    name = "demo-mock"
    configured = False

    def complete(self, system: str, prompt: str, max_tokens: int = 600) -> str:
        return ""
