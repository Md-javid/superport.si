"""Read a scanned or unstructured document with Gemini vision and return typed fields."""
import re

from app.intelligence import gemini_client
from app.intelligence.errors import UpstreamError

MAX_INLINE_BYTES = 14 * 1024 * 1024
MIME = {"pdf": "application/pdf", "png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp"}
SYSTEM = (
    "You are a precise data-entry assistant for customs paperwork. Read the attached document and copy values exactly as written. "
    "Never guess, never calculate, never fill a field from outside knowledge. If a field is not visible, return an empty string with confidence 0. "
    "Reply with one JSON object only."
)


def guess_mime(filename: str, content_type: str | None) -> str | None:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext in MIME:
        return MIME[ext]
    return content_type if content_type in MIME.values() else None


def _norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def read_document(doc_label: str, specs: list[tuple[str, str]], filename: str, data: bytes, content_type: str | None, *, known_text: str = "", shipment_id: int | None = None) -> tuple[dict[str, dict], dict]:
    mime = guess_mime(filename, content_type)
    if not mime:
        raise UpstreamError("This file type cannot be read by the AI reader. Upload a PDF, PNG, JPG or WEBP.")
    if len(data) > MAX_INLINE_BYTES:
        raise UpstreamError("File is too large for the AI reader (14 MB limit).")
    fields = "\n".join(f'- "{key}": {label}' for key, label in specs)
    prompt = (
        f"Document type: {doc_label}.\nExtract these fields:\n{fields}\n\n"
        'Return JSON exactly like: {"fields": {"<key>": {"value": "<text as written>", "confidence": <0 to 1>}}}\n'
        "Include every key listed. Keep units and currency symbols as written (for example '17,200 kg')."
    )
    parsed, meta = gemini_client.generate_json("doc_extract", system=SYSTEM, parts=[gemini_client.inline_part(data, mime), {"text": prompt}], kind="fast", shipment_id=shipment_id)
    raw = parsed.get("fields")
    if not isinstance(raw, dict):
        raise UpstreamError("Gemini returned fields in an unexpected format.")
    haystack = _norm(known_text)
    out: dict[str, dict] = {}
    for key, _ in specs:
        item = raw.get(key) if isinstance(raw.get(key), dict) else {}
        value = str(item.get("value", "") or "").strip()
        try:
            conf = float(item.get("confidence", 0))
        except (TypeError, ValueError):
            conf = 0.0
        conf = max(0.0, min(conf, 0.95)) if value else 0.0  # a model's own certainty is never shown as 100%
        if value and haystack and _norm(value) not in haystack:
            conf = min(conf, 0.7)  # the value is not in the file's own text layer: be cautious
        out[key] = {"value": value, "confidence": round(conf, 2)}
    return out, {"model": meta["model"], "tokens_in": meta["tokens_in"], "tokens_out": meta["tokens_out"], "cached": meta["cached"]}
