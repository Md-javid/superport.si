"""Provider abstractions for the AI layer.

Services depend on these interfaces only. Demo mode wires in deterministic local
providers; live mode can wire in hosted OCR / vision / LLM providers without
touching any business logic.
"""
from abc import ABC, abstractmethod


class OCRProvider(ABC):
    """Turns an uploaded file into plain text."""

    name: str = "ocr"

    @abstractmethod
    def extract_text(self, data: bytes, filename: str, content_type: str | None) -> str: ...


class LLMProvider(ABC):
    """Generic text-completion provider."""

    name: str = "llm"
    configured: bool = False

    @abstractmethod
    def complete(self, system: str, prompt: str, max_tokens: int = 600) -> str: ...


class ProviderNotConfigured(RuntimeError):
    pass
