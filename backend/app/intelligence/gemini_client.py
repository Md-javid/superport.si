"""Gemini client over the public REST API (generateContent).

Model names change often and Google restricts older models for new keys, so when no model is
configured we ask the API which models this key can use and pick the newest Flash / Pro.
Temperature is left at the model default on purpose (recommended for Gemini 3 models).
"""
import base64
import hashlib
import re

import httpx

from app.core.config import get_settings
from app.intelligence import gemini_ready
from app.intelligence.cache import billable_calls, cache_get, cache_put, log_usage, make_key
from app.intelligence.errors import BudgetExceeded, NotConfigured, UpstreamError
from app.intelligence.jsonutil import parse_json

BASE = "https://generativelanguage.googleapis.com/v1beta"
_transport: httpx.BaseTransport | None = None
_models: dict[str, str] = {}
_PATTERN = re.compile(r"^gemini-(\d+(?:\.\d+)?)-(flash-lite|flash|pro)(-preview.*)?$")


def set_transport(transport: httpx.BaseTransport | None) -> None:
    global _transport
    _transport = transport
    _models.clear()


def _headers() -> dict:
    return {"x-goog-api-key": get_settings().gemini_api_key or "", "Content-Type": "application/json"}


def _fail(response: httpx.Response, model: str = "") -> None:
    if response.status_code < 400:
        return
    detail = ""
    try:
        detail = response.json().get("error", {}).get("message", "")
    except ValueError:
        pass
    if response.status_code in (400, 401, 403) and "api key" in detail.lower():
        raise UpstreamError("Gemini rejected the API key. Check GEMINI_API_KEY.")
    if response.status_code == 404:
        raise UpstreamError(f"Gemini model '{model}' is not available for this key. Run scripts/smoke_live.py and set GEMINI_MODEL_FAST / GEMINI_MODEL_PRO.")
    if response.status_code == 429:
        raise UpstreamError("Gemini quota or rate limit reached.")
    raise UpstreamError(f"Gemini error (HTTP {response.status_code}): {detail[:200] or 'no details'}")


def list_models() -> list[dict]:
    if not get_settings().gemini_api_key:
        raise NotConfigured("GEMINI_API_KEY is not set.")
    out: list[dict] = []
    token = None
    try:
        with httpx.Client(transport=_transport, timeout=30) as client:
            for _ in range(5):
                params = {"pageSize": 200, **({"pageToken": token} if token else {})}
                response = client.get(f"{BASE}/models", headers=_headers(), params=params)
                _fail(response)
                data = response.json()
                out += data.get("models", [])
                token = data.get("nextPageToken")
                if not token:
                    break
    except httpx.HTTPError as exc:
        raise UpstreamError("Could not reach the Gemini API.") from exc
    return out


def pick_models(models: list[dict]) -> tuple[str, str]:
    cands = []
    for m in models:
        name = m.get("name", "").removeprefix("models/")
        if "generateContent" not in m.get("supportedGenerationMethods", []):
            continue
        match = _PATTERN.match(name)
        if match:
            cands.append((float(match.group(1)), match.group(2), bool(match.group(3)), name))

    def best(tier: str) -> str | None:
        pool = [c for c in cands if c[1] == tier]
        return max(pool, key=lambda c: (c[0], not c[2]))[3] if pool else None

    fast = best("flash") or best("flash-lite") or best("pro")
    if not fast:
        raise UpstreamError("This Gemini key has no usable Flash or Pro model. Check your plan in Google AI Studio.")
    return fast, best("pro") or fast


try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None  # type: ignore
    types = None  # type: ignore

_client = None


def get_genai_client():
    global _client
    api_key = get_settings().gemini_api_key
    if not api_key:
        raise NotConfigured("GEMINI_API_KEY is not set.")
    if _client is None:
        _client = genai.Client(api_key=api_key)
    return _client


def resolve_model(kind: str) -> str:
    settings = get_settings()
    configured = settings.gemini_model_pro if kind == "pro" else settings.gemini_model_fast
    if configured:
        return configured
    return "gemini-3.5-flash-lite"


def _fingerprint(parts: list[dict]) -> list:
    out = []
    for p in parts:
        if "inline_data" in p:
            data = p["inline_data"]["data"]
            out.append({"mime": p["inline_data"]["mime_type"], "sha": hashlib.sha256(data.encode()).hexdigest()})
        else:
            out.append(p)
    return out


def inline_part(data: bytes, mime_type: str) -> dict:
    return {"inline_data": {"mime_type": mime_type, "data": base64.b64encode(data).decode()}}


def generate(task: str, *, system: str, parts: list[dict], kind: str = "fast", json_mode: bool = True, max_tokens: int = 8192, shipment_id: int | None = None, force: bool = False) -> dict:
    settings = get_settings()
    if not gemini_ready():
        raise NotConfigured("Gemini is not configured (needs INTELLIGENCE_MODE=live and GEMINI_API_KEY).")
    model = resolve_model(kind)
    ckey = make_key("gemini", {"model": model, "system": system, "parts": _fingerprint(parts), "json": json_mode, "max": max_tokens})
    if not force:
        hit = cache_get("gemini", ckey, settings.cache_ttl_hours)
        if hit is not None:
            log_usage("gemini", task, shipment_id, cached=True)
            return {**hit, "cached": True}
    if shipment_id is not None and billable_calls("gemini", shipment_id) >= settings.gemini_budget_per_shipment:
        raise BudgetExceeded(f"Gemini call budget reached for this shipment ({settings.gemini_budget_per_shipment}).")

    client = get_genai_client()
    has_inline = any("inline_data" in p for p in parts)
    text = ""
    tokens_in = 0
    tokens_out = 0

    try:
        if not has_inline:
            # Strictly use the Interactions API with gemini-3.5-flash-lite
            input_text = "\n\n".join(p.get("text", "") for p in parts if "text" in p)
            if json_mode and "json" not in input_text.lower():
                input_text += "\n\nImportant: Output a single valid JSON object."

            interaction = client.interactions.create(
                model=model,
                input=input_text,
                system_instruction=system or None,
            )
            text = interaction.output_text or ""
            if interaction.usage:
                tokens_in = getattr(interaction.usage, "total_input_tokens", 0) or 0
                tokens_out = getattr(interaction.usage, "total_output_tokens", 0) or 0
        else:
            # Multimodal via models.generate_content
            content_parts = []
            for p in parts:
                if "inline_data" in p:
                    b64_data = p["inline_data"]["data"]
                    raw_bytes = base64.b64decode(b64_data)
                    mime_type = p["inline_data"]["mime_type"]
                    content_parts.append(types.Part.from_bytes(data=raw_bytes, mime_type=mime_type))
                elif "text" in p:
                    content_parts.append(p["text"])

            config = types.GenerateContentConfig(
                system_instruction=system or None,
                response_mime_type="application/json" if json_mode else None,
                max_output_tokens=max_tokens,
            )
            res = client.models.generate_content(
                model=model,
                contents=content_parts,
                config=config,
            )
            text = res.text or ""
            if res.usage_metadata:
                tokens_in = getattr(res.usage_metadata, "prompt_token_count", 0) or 0
                tokens_out = getattr(res.usage_metadata, "candidates_token_count", 0) or 0
    except Exception as exc:
        log_usage("gemini", task, shipment_id, ok=False, detail=str(exc))
        raise UpstreamError(f"Gemini error: {exc}") from exc

    result = {"text": text, "model": model, "tokens_in": int(tokens_in), "tokens_out": int(tokens_out)}
    cache_put("gemini", ckey, {"task": task, "model": model}, result)
    log_usage("gemini", task, shipment_id, tokens_in=result["tokens_in"], tokens_out=result["tokens_out"])
    return {**result, "cached": False}


def generate_json(task: str, **kwargs) -> tuple[dict, dict]:
    """Generate and parse JSON, retrying once with a stricter reminder if parsing fails."""
    result = generate(task, **kwargs)
    try:
        return parse_json(result["text"]), result
    except ValueError:
        retry = dict(kwargs)
        retry["parts"] = [*kwargs["parts"], {"text": "Your previous reply was not valid JSON. Reply again with ONLY one valid JSON object."}]
        retry["force"] = True
        result = generate(task, **retry)
        try:
            return parse_json(result["text"]), result
        except ValueError as exc:
            raise UpstreamError("Gemini did not return valid JSON.") from exc


# ---------------------------------------------------------------- embeddings
_embed_model: dict[str, str] = {}


def pick_embedding_model(models: list[dict]) -> str:
    cands = []
    for m in models:
        name = m.get("name", "").removeprefix("models/")
        methods = m.get("supportedGenerationMethods", [])
        if "embedding" in name and ("embedContent" in methods or "batchEmbedContents" in methods):
            ver = re.search(r"(\d+(?:\.\d+)?)", name)
            cands.append((float(ver.group(1)) if ver else 0.0, not re.search(r"preview|exp", name), name))
    if not cands:
        raise UpstreamError("This Gemini key has no embedding model. Set GEMINI_EMBEDDING_MODEL or check your plan.")
    return max(cands)[2]


def resolve_embedding_model() -> str:
    configured = get_settings().gemini_embedding_model
    if configured:
        return configured
    return "gemini-embedding-001"


def embed(texts: list[str], *, task: str, dim: int) -> tuple[list[list[float]], str]:
    """Embed texts (task: RETRIEVAL_DOCUMENT or RETRIEVAL_QUERY). Returns vectors and the model used."""
    if not gemini_ready():
        raise NotConfigured("Gemini is not configured (needs INTELLIGENCE_MODE=live and GEMINI_API_KEY).")
    model = resolve_embedding_model()
    client = get_genai_client()
    out: list[list[float]] = []
    for i in range(0, len(texts), 100):
        batch = texts[i : i + 100]
        try:
            res = client.models.embed_content(
                model=model,
                contents=batch,
            )
            vectors = [e.values for e in res.embeddings]
        except Exception as exc:
            log_usage("gemini", "embed", None, ok=False, detail=str(exc))
            raise UpstreamError(f"Gemini embedding error: {exc}") from exc
        out += vectors
        log_usage("gemini", "embed", None)
    return out, model

