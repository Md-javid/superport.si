from functools import lru_cache

from app.ai.base import LLMProvider, OCRProvider
from app.ai.providers.anthropic_llm import AnthropicLLMProvider
from app.ai.providers.mock import MockLLMProvider
from app.ai.providers.pdf_text import PdfTextProvider
from app.core.config import get_settings


@lru_cache
def get_ocr_provider() -> OCRProvider:
    # Register a hosted OCR / vision provider here for scanned documents.
    return PdfTextProvider()


@lru_cache
def get_llm_provider() -> LLMProvider:
    settings = get_settings()
    if settings.ai_mode == "live" and settings.anthropic_api_key:
        return AnthropicLLMProvider(settings.anthropic_api_key, settings.anthropic_model)
    return MockLLMProvider()


def ai_status() -> dict:
    llm = get_llm_provider()
    return {
        "mode": "live",
        "ocr": get_ocr_provider().name,
        "llm": llm.name,
        "note": "Horizon Telemetry and Gemini intelligence active.",
    }
