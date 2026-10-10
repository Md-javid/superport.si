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


def resolve_model(kind: str) -> str:
    settings = get_settings()
    configured = settings.gemini_model_pro if kind == "pro" else settings.gemini_model_fast
    if configured:
        return configured
    if not _models:
        fast, pro = pick_models(list_models())
        _models.update({"fast": fast, "pro": pro})
    return _models["pro" if kind == "pro" else "fast"]


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

    body: dict = {"contents": [{"role": "user", "parts": parts}], "generationConfig": {"maxOutputTokens": max_tokens}}
    if json_mode:
        body["generationConfig"]["responseMimeType"] = "application/json"
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}

    try:
        with httpx.Client(transport=_transport, timeout=90) as client:
            response = client.post(f"{BASE}/models/{model}:generateContent", headers=_headers(), json=body)
    except httpx.HTTPError as exc:
        log_usage("gemini", task, shipment_id, ok=False, detail=type(exc).__name__)
        raise UpstreamError("Could not reach the Gemini API.") from exc
    try:
        _fail(response, model)
    except UpstreamError as exc:
        log_usage("gemini", task, shipment_id, ok=False, detail=str(exc))
        raise

    data = response.json()
    candidates = data.get("candidates") or []
    if not candidates:
        reason = (data.get("promptFeedback") or {}).get("blockReason", "no candidates returned")
        log_usage("gemini", task, shipment_id, ok=False, detail=f"blocked: {reason}")
        raise UpstreamError(f"Gemini returned no answer ({reason}).")
    candidate = candidates[0]
    text = "".join(p.get("text", "") for p in (candidate.get("content") or {}).get("parts", []) if not p.get("thought"))
    if candidate.get("finishReason") == "MAX_TOKENS" and not text.strip():
        log_usage("gemini", task, shipment_id, ok=False, detail="max tokens")
        raise UpstreamError("Gemini ran out of output tokens before answering.")
    usage = data.get("usageMetadata") or {}
    result = {"text": text, "model": model, "tokens_in": int(usage.get("promptTokenCount", 0)), "tokens_out": int(usage.get("candidatesTokenCount", 0))}
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
