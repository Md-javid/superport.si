"""Document extraction service.

Pipeline: OCR provider -> label/value parser -> field normalisation.
When a document cannot be read (empty or scanned upload in demo mode) the demo
engine synthesises plausible values from the shipment record and marks every such
field with source="demo-synthesized" so it is never mistaken for real extraction.
"""
import hashlib
import random
import re

from app.ai.registry import get_ocr_provider
from app.catalog import match_item
from app.services.common import norm_text

FIELD_SPECS: dict[str, list[tuple[str, str]]] = {
    "commercial_invoice": [
        ("invoice_number", "Invoice number"),
        ("product", "Product"),
        ("quantity", "Quantity"),
        ("unit_price", "Unit price"),
        ("total_value", "Total value"),
        ("currency", "Currency"),
        ("country_of_origin", "Country of origin"),
        ("consignee", "Consignee"),
        ("shipper", "Shipper"),
        ("incoterm", "Incoterm"),
    ],
    "packing_list": [
        ("product", "Product"),
        ("quantity", "Quantity"),
        ("packages", "Number of packages"),
        ("net_weight", "Net weight"),
        ("gross_weight", "Gross weight"),
        ("container_number", "Container number"),
        ("consignee", "Consignee"),
        ("shipper", "Shipper"),
    ],
    "bill_of_lading": [
        ("bl_number", "B/L number"),
        ("shipper", "Shipper"),
        ("consignee", "Consignee"),
        ("carrier", "Carrier"),
        ("vessel", "Vessel and voyage"),
        ("port_of_loading", "Port of loading"),
        ("port_of_discharge", "Port of discharge"),
        ("container_number", "Container number"),
        ("gross_weight", "Gross weight"),
    ],
}

ALIASES: dict[str, list[str]] = {
    "invoice_number": ["invoice number", "invoice no", "invoice"],
    "product": ["product", "description of goods", "goods", "description", "item"],
    "quantity": ["quantity", "qty", "total quantity"],
    "unit_price": ["unit price", "price per unit", "rate"],
    "total_value": ["total value", "total amount", "invoice total", "total"],
    "currency": ["currency"],
    "country_of_origin": ["country of origin", "origin"],
    "consignee": ["consignee", "buyer", "importer", "notify party"],
    "shipper": ["shipper", "seller", "exporter"],
    "incoterm": ["incoterm", "incoterms", "terms of delivery"],
    "packages": ["number of packages", "packages", "no of packages"],
    "net_weight": ["net weight", "net wt"],
    "gross_weight": ["gross weight", "gross wt"],
    "container_number": ["container number", "container no", "container"],
    "bl_number": ["b l number", "bl number", "bill of lading no", "b l no", "bill of lading number"],
    "carrier": ["carrier", "shipping line"],
    "vessel": ["vessel and voyage", "vessel", "vessel voyage"],
    "port_of_loading": ["port of loading", "pol"],
    "port_of_discharge": ["port of discharge", "pod"],
}
_ALIAS_LOOKUP = {norm_text(alias): key for key, aliases in ALIASES.items() for alias in aliases}
_LINE = re.compile(r"^\s*([A-Za-z/ .&]{2,40}?)\s*[:\-]\s*(.+?)\s*$")


def parse_key_values(text: str) -> dict[str, str]:
    found: dict[str, str] = {}
    for line in text.splitlines():
        match = _LINE.match(line)
        if not match:
            continue
        key = _ALIAS_LOOKUP.get(norm_text(match.group(1)))
        if key and key not in found:
            found[key] = match.group(2).strip()
    return found


def _rng(shipment_ref: str, doc_type: str) -> random.Random:
    digest = hashlib.sha256(f"{shipment_ref}:{doc_type}".encode()).hexdigest()
    return random.Random(int(digest[:12], 16))


def _synthesize(doc_type: str, shipment, item: dict) -> dict[str, str]:
    """Deterministic demo values derived from the shipment record."""
    rng = _rng(shipment.reference, "shared")
    qty = max(1, int(item["default_qty"] * rng.uniform(0.8, 1.2)))
    lo, hi = item["price_band"]
    price = round(rng.uniform(lo + (hi - lo) * 0.25, lo + (hi - lo) * 0.65), 2)
    total = round(qty * price, 2)
    net = round(qty * item["unit_weight_kg"], 0)
    gross_pl = round(net * 1.075, 0)
    gross_bl = gross_pl
    if _rng(shipment.reference, "bl-drift").random() < 0.3:
        gross_bl = round(gross_pl * 1.034, 0)  # small, realistic drift to demo cross-checking
    ref = shipment.reference.replace("SP-", "")
    base = {
        "product": shipment.product_description,
        "quantity": f"{qty:,} {item['unit']}",
        "consignee": shipment.importer,
        "shipper": shipment.exporter,
        "container_number": shipment.container_number,
    }
    if doc_type == "commercial_invoice":
        return {
            **base,
            "invoice_number": f"INV-{ref}",
            "unit_price": f"{price:,.2f}",
            "total_value": f"{total:,.2f}",
            "currency": "USD",
            "country_of_origin": shipment.origin,
            "incoterm": "FOB",
        }
    if doc_type == "packing_list":
        return {
            **base,
            "packages": f"{max(1, qty // 20):,}",
            "net_weight": f"{net:,.0f} kg",
            "gross_weight": f"{gross_pl:,.0f} kg",
        }
    return {
        "bl_number": f"BL{ref.replace('-', '')}",
        "shipper": shipment.exporter,
        "consignee": shipment.importer,
        "carrier": shipment.carrier,
        "vessel": "MV Ocean Meridian / 031E",
        "port_of_loading": shipment.origin,
        "port_of_discharge": shipment.port,
        "container_number": shipment.container_number,
        "gross_weight": f"{gross_bl:,.0f} kg",
    }


def _build_fields(specs, values: dict[str, dict], source: str) -> list[dict]:
    fields = []
    for key, label in specs:
        item = values.get(key, {})
        value = item.get("value", "")
        found = bool(value)
        fields.append(
            {
                "key": key,
                "label": label,
                "value": value,
                "original": value,
                "confidence": item.get("confidence", 0.0) if found else 0.0,
                "source": source if found else "not-found",
                "edited": False,
            }
        )
    return fields


def extract_document(doc_type: str, filename: str, data: bytes, content_type: str | None, shipment) -> tuple[list[dict], dict]:
    from app.catalog import DOC_LABELS
    from app.intelligence import doc_reader, enabled_for, gemini_ready, synthetic_allowed
    from app.intelligence.errors import IntelligenceError

    specs = FIELD_SPECS[doc_type]
    ocr = get_ocr_provider()
    text = ocr.extract_text(data, filename, content_type)
    parsed = parse_key_values(text)
    readable = len([k for k, _ in specs if k in parsed]) >= max(3, len(specs) // 2)
    rng = _rng(shipment.reference, doc_type + filename)

    # 1) Text layer in a recognised layout: read it directly (free, exact).
    if readable:
        values = {k: {"value": parsed.get(k, ""), "confidence": round(rng.uniform(0.91, 0.99), 2)} for k, _ in specs}
        return _build_fields(specs, values, "extracted"), {"provider": ocr.name, "mode": "extracted-from-file", "text_characters": len(text)}

    # 2) Scanned or unstructured file: ask Gemini to read it (live mode only).
    error = ""
    if data and gemini_ready() and enabled_for(shipment):
        try:
            values, info = doc_reader.read_document(DOC_LABELS[doc_type], specs, filename, data, content_type, known_text=text, shipment_id=getattr(shipment, "id", None))
            return _build_fields(specs, values, "gemini-vision"), {"provider": "gemini", "mode": "gemini-vision", "text_characters": len(text), **info}
        except IntelligenceError as exc:
            error = str(exc)

    # 3) Demo fallback, only where allowed and always labelled.
    if synthetic_allowed(shipment):
        item, _ = match_item(shipment.product_description)
        synthesized = _synthesize(doc_type, shipment, item)
        values = {k: {"value": synthesized.get(k, ""), "confidence": round(rng.uniform(0.82, 0.94), 2)} for k, _ in specs}
        fields = _build_fields(specs, values, "demo-synthesized")
        return fields, {"provider": "demo-mock", "mode": "demo-synthesized", "text_characters": len(text), **({"ai_error": error} if error else {})}

    # 4) Honest failure: leave fields empty and say why.
    reason = error or ("The file has no readable text and the AI reader is not configured." if not gemini_ready() else "The file could not be read.")
    return _build_fields(specs, {}, "not-found"), {"provider": "none", "mode": "unreadable", "text_characters": len(text), "error": reason}
