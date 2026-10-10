"""Price check: compare the invoice unit price with live Google Shopping listings.

Retail prices are higher than import (FOB) prices, so the 'normal' band is deliberately wide.
This is a sanity check that points a human at an oddly priced invoice. It is not proof of anything.
"""
import statistics

from app.intelligence import gemini_client, gemini_ready, serpapi_client
from app.intelligence.errors import IntelligenceError
from app.intelligence.evidence import replace_evidence
from app.services.common import doc_value, to_number

SYSTEM = "You compare product listings for a customs analyst. Reply with one JSON object only."


def _band(ratio: float) -> tuple[str, int, str]:
    if ratio < 0.10:
        return "high", 80, "far below"
    if ratio < 0.20:
        return "medium", 40, "well below"
    if ratio <= 1.2:
        return "low", 8, "within the normal range of"
    if ratio <= 2.0:
        return "medium", 40, "above"
    return "high", 70, "far above"


def run(shipment, docs, *, fixture: bool, force: bool = False) -> dict:
    product = (doc_value(docs, "commercial_invoice", "product") or shipment.product_description).strip()
    unit_price = to_number(doc_value(docs, "commercial_invoice", "unit_price"))
    currency = (doc_value(docs, "commercial_invoice", "currency") or "").upper().strip()
    mode_label = "fixture" if fixture else "live"
    base = {"kind": "price", "source_mode": mode_label, "query": product[:100]}
    if unit_price is None:
        return {**base, "status": "inconclusive", "summary": "The invoice has no unit price to compare."}
    if currency and currency != "USD":
        return {**base, "status": "not_comparable", "summary": f"Invoice currency is {currency}. Market prices are fetched in USD, so no comparison was made."}

    data = serpapi_client.search("google_shopping", {"q": product[:100], "gl": "us", "hl": "en"}, shipment_id=getattr(shipment, "id", None), force=force, fixture=fixture)
    items = []
    for r in data.get("shopping_results") or []:
        price = r.get("extracted_price")
        if isinstance(price, (int, float)) and price > 0:
            items.append({"title": str(r.get("title", ""))[:160], "price": float(price), "source": str(r.get("source", "")), "url": r.get("product_link") or r.get("link") or ""})
    if len(items) < 3:
        return {**base, "status": "inconclusive", "summary": f"Only {len(items)} priced listings were found. Not enough to compare."}

    filtered, notes = False, ""
    if not fixture and gemini_ready():
        listing = "\n".join(f"[{i}] {it['title']} - {it['price']:.2f} USD" for i, it in enumerate(items, 1))
        prompt = (f"Invoice product: {product}\nInvoice unit price: {unit_price:.2f} USD\n\nLISTINGS\n{listing}\n\n"
                  'Return JSON: {"comparable":[listing numbers],"notes":"one short sentence"}\n'
                  "Include only listings for the same kind of product as ONE unit with the same key specification. Exclude accessories, parts, multipacks and different capacities.")
        try:
            parsed, _ = gemini_client.generate_json("price_filter", system=SYSTEM, parts=[{"text": prompt}], kind="fast", shipment_id=getattr(shipment, "id", None), force=force)
            keep = [i for i in parsed.get("comparable", []) if isinstance(i, int) and 1 <= i <= len(items)]
            if len(keep) >= 3:
                items, filtered = [items[i - 1] for i in keep], True
            notes = str(parsed.get("notes", ""))[:200]
        except IntelligenceError:
            pass

    prices = sorted(i["price"] for i in items)
    if len(prices) >= 5:  # trim obvious outliers (accessories, errors) with the IQR rule
        q1, _, q3 = statistics.quantiles(prices, n=4, method="inclusive")
        lo, hi = q1 - 1.5 * (q3 - q1), q3 + 1.5 * (q3 - q1)
        trimmed = [p for p in prices if lo <= p <= hi]
        if len(trimmed) >= 3:
            prices = trimmed
    median = statistics.median(prices)
    p25, _, p75 = statistics.quantiles(prices, n=4, method="inclusive") if len(prices) >= 2 else (prices[0], 0, prices[0])
    ratio = unit_price / median
    level, score, phrase = _band(ratio)
    summary = (f"Invoice unit price {unit_price:,.2f} USD is {ratio * 100:.0f}% of the median listing price ({median:,.2f} USD, {len(prices)} listings): {phrase} the expected range. "
               "Retail prices run higher than import prices, so a wide range is normal.")
    listings = [{"title": i["title"], "price": i["price"], "source": i["source"], "url": i["url"]} for i in items[:6]]
    if getattr(shipment, "id", None):
        replace_evidence(shipment.id, "price", [{"engine": "google_shopping", "query": product[:100], "title": l["title"], "url": l["url"], "snippet": f"{l['price']:,.2f} USD at {l['source']}", "trust": "web", "source_mode": mode_label} for l in listings if l["url"]])
    return {**base, "status": "ok", "unit_price": unit_price, "currency": "USD", "market": {"n": len(prices), "median": round(median, 2), "p25": round(p25, 2), "p75": round(p75, 2), "min": round(min(prices), 2), "max": round(max(prices), 2)},
            "ratio": round(ratio, 2), "level": level, "score": score, "summary": summary, "listings": listings, "filtered_by_ai": filtered, "notes": notes}
