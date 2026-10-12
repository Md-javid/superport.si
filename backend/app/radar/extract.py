"""Turn news articles into events. Gemini when available, a transparent keyword heuristic otherwise."""
from app.intelligence import gemini_client
from app.intelligence.errors import IntelligenceError

EVENT_TYPES = ("strike", "congestion", "weather", "tariff_change", "regulation", "closure", "carrier", "geopolitical", "other")
SEVERITIES = ("low", "medium", "high")
SYSTEM = ("You extract trade-disruption events from news for a customs and logistics team. Describe only what the articles say. "
          "Merge articles about the same event. Skip articles that are not about port, shipping, customs, tariffs, trade rules or related disruption. "
          "Never speculate and never invent events. Reply with one JSON object only.")
KEYWORDS = {
    "carrier": ["blank sailing", "vessel cancel", "schedule change", "cancelled sailing", "service suspension", "omit port", "skip port"],
    "strike": ["strike", "walkout", "lockout"],
    "congestion": ["congestion", "dwell time", "backlog", "queue", "delays", "delay"],
    "weather": ["cyclone", "storm", "typhoon", "flood", "hurricane", "monsoon"],
    "tariff_change": ["tariff", "import duty", "customs duty", "anti-dumping"],
    "regulation": ["regulation", "notification", "import ban", "restriction", "import policy", "mandatory"],
    "closure": ["closure", "closed", "shut down", "shutdown"],
}
HIGH_WORDS = ("closed", "closure", "shutdown", "cyclone", "typhoon", "hurricane", "strike", "ban")


def gemini_events(articles: list[dict], watch: dict) -> tuple[list[dict], str]:
    listing = "\n".join(f"[{i}] {a['title']} ({a['source']}, {a['date']}): {a['snippet']}" for i, a in enumerate(articles, 1))
    prompt = (f"WATCHED PORTS: {', '.join(watch.get('ports', [])) or 'none'}\nWATCHED COUNTRIES: {', '.join(sorted(watch.get('countries', []))) or 'none'}\n"
              f"WATCHED PRODUCTS: {', '.join(watch.get('products', [])) or 'none'}\nWATCHED CARRIERS: {', '.join(sorted(watch.get('carriers', []))) or 'none'}\n\nARTICLES\n{listing}\n\n"
              'Return JSON: {"events":[{"title":"short headline","event_type":"strike|congestion|weather|tariff_change|regulation|closure|carrier|geopolitical|other",'
              '"summary":"one or two plain sentences","severity":"low|medium|high","ports":["port names"],"countries":["country names"],"products":["product names"],"carriers":["shipping line names"],"articles":[article numbers]}]}\n'
              "Every event must list the article numbers that report it. Use at most 10 events.")
    parsed, meta = gemini_client.generate_json("radar_extract", system=SYSTEM, parts=[{"text": prompt}], kind="fast")
    events = []
    for raw in parsed.get("events") or []:
        if not isinstance(raw, dict):
            continue
        idx = sorted({i for i in raw.get("articles", []) if isinstance(i, int) and 1 <= i <= len(articles)})
        if not idx or not raw.get("title"):
            continue  # an event without a real article behind it is discarded
        events.append({
            "title": str(raw["title"])[:200], "event_type": raw.get("event_type") if raw.get("event_type") in EVENT_TYPES else "other",
            "summary": str(raw.get("summary", ""))[:400], "severity": raw.get("severity") if raw.get("severity") in SEVERITIES else "low",
            "ports": [str(x)[:80] for x in raw.get("ports", []) if x][:5], "countries": [str(x)[:60] for x in raw.get("countries", []) if x][:5],
            "products": [str(x)[:60] for x in raw.get("products", []) if x][:5], "carriers": [str(x)[:60] for x in raw.get("carriers", []) if x][:4], "articles": idx,
        })
    return events[:10], f"gemini:{meta['model']}"


def heuristic_events(articles: list[dict], watch: dict) -> tuple[list[dict], str]:
    groups: dict[tuple, dict] = {}
    for i, a in enumerate(articles, 1):
        text = f"{a['title']} {a['snippet']}".lower()
        etype = next((t for t, words in KEYWORDS.items() if any(w in text for w in words)), None)
        if not etype:
            continue
        ports = tuple(p for p in watch.get("ports", []) if p.lower() in text)
        countries = tuple(sorted(c for c in watch.get("countries", []) if c.lower() in text))
        products = tuple(sorted(w for w in watch.get("product_words", []) if w in text))
        carriers = tuple(sorted(c for c in watch.get("carriers", []) if c in text))
        if not (ports or countries or products or carriers):
            continue
        key = (etype, ports, countries, carriers)
        g = groups.setdefault(key, {"title": a["title"], "event_type": etype, "summary": a["snippet"], "ports": list(ports), "countries": list(countries), "carriers": list(carriers), "products": set(), "articles": [], "text": ""})
        g["articles"].append(i)
        g["products"].update(products)
        g["text"] += " " + text
    events = []
    for g in groups.values():
        severity = "high" if any(w in g["text"] for w in HIGH_WORDS) else "medium"
        events.append({"title": g["title"][:200], "event_type": g["event_type"], "summary": g["summary"][:400], "severity": severity, "ports": g["ports"], "countries": g["countries"], "products": sorted(g["products"]), "carriers": [c.title() for c in g["carriers"]], "articles": g["articles"]})
    return events[:10], "keyword-heuristic"
