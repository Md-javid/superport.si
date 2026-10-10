import io

from app.ai.base import OCRProvider


class PdfTextProvider(OCRProvider):
    """Local text extraction for text-based PDFs and plain text files.

    Scanned images return an empty string; in production a vision / OCR provider
    would be registered for those (see app/ai/registry.py).
    """

    name = "local-pdf-text"

    def extract_text(self, data: bytes, filename: str, content_type: str | None) -> str:
        if not data:
            return ""
        lower = filename.lower()
        if lower.endswith(".pdf") or content_type == "application/pdf":
            try:
                from pypdf import PdfReader

                reader = PdfReader(io.BytesIO(data))
                return "\n".join((page.extract_text() or "") for page in reader.pages)
            except Exception:
                return ""
        if lower.endswith((".txt", ".csv", ".json", ".md")):
            return data.decode("utf-8", errors="ignore")
        return ""
