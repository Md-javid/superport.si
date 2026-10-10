"""Demo product knowledge base.

Illustrative reference data used by the demo classification, compliance and risk
engines. HS codes, price bands and certificate lists are NOT authoritative tariff
data. In production, replace this module with a licensed tariff / rules provider.
"""

CATALOG: list[dict] = [
    {
        "key": "lithium_battery",
        "name": "Lithium-ion batteries",
        "keywords": ["lithium", "li-ion", "battery", "batteries", "accumulator", "energy storage", "48v", "kwh"],
        "hs_code": "8507.60",
        "hs_label": "Lithium-ion accumulators",
        "chapter": "Chapter 85: Electrical machinery and equipment",
        "alternatives": [
            ("8507.80", "Other electric accumulators", "Applies to non-lithium chemistries; the documents state lithium-ion."),
            ("8506.50", "Primary cells and batteries, lithium", "Primary (non-rechargeable) cells; these packs are rechargeable."),
            ("8504.40", "Static converters", "Only if the pack is shipped as an inverter or charger unit."),
        ],
        "unit": "units",
        "default_qty": 400,
        "price_band": (450.0, 900.0),
        "unit_weight_kg": 40.0,
        "restrictions": [
            "Dangerous goods: Class 9 (UN3480 / UN3481). Carrier acceptance and IMDG declaration required.",
            "Rechargeable lithium packs may need safety standard registration at the destination.",
        ],
        "certificates": [
            "UN 38.3 test summary",
            "Safety Data Sheet (SDS)",
            "Dangerous goods declaration",
            "Certificate of origin",
        ],
    },
    {
        "key": "cotton_tshirt",
        "name": "Cotton T-shirts",
        "keywords": ["t-shirt", "tshirt", "t shirt", "cotton", "knitted", "apparel", "garment", "tee"],
        "hs_code": "6109.10",
        "hs_label": "T-shirts, singlets and vests, of cotton, knitted",
        "chapter": "Chapter 61: Knitted or crocheted apparel",
        "alternatives": [
            ("6109.90", "T-shirts of other textile materials", "Applies if the fibre content is not mainly cotton."),
            ("6205.20", "Men's shirts of cotton, woven", "Applies only to woven construction; these are knitted."),
        ],
        "unit": "pcs",
        "default_qty": 12000,
        "price_band": (1.8, 6.5),
        "unit_weight_kg": 0.2,
        "restrictions": ["Textile labelling and fibre content declaration may apply."],
        "certificates": ["Certificate of origin", "Fibre content declaration"],
    },
    {
        "key": "led_lighting",
        "name": "LED lighting",
        "keywords": ["led", "luminaire", "lamp", "lighting", "downlight", "panel light", "bulb"],
        "hs_code": "9405.42",
        "hs_label": "Other electric lamps and lighting fittings, LED",
        "chapter": "Chapter 94: Furniture; lighting; prefabricated buildings",
        "alternatives": [
            ("8539.52", "LED lamps (bulbs and tubes)", "Applies to retrofit lamps and bulbs rather than complete fittings."),
            ("9405.49", "Other electric lighting fittings", "Applies if the fitting does not use LED sources."),
        ],
        "unit": "pcs",
        "default_qty": 5000,
        "price_band": (3.5, 18.0),
        "unit_weight_kg": 0.6,
        "restrictions": ["Electrical safety conformity is usually required before sale."],
        "certificates": ["Conformity / safety test report", "Certificate of origin"],
    },
    {
        "key": "coffee",
        "name": "Green coffee beans",
        "keywords": ["coffee", "arabica", "robusta", "green coffee", "beans"],
        "hs_code": "0901.11",
        "hs_label": "Coffee, not roasted, not decaffeinated",
        "chapter": "Chapter 09: Coffee, tea, mate and spices",
        "alternatives": [
            ("0901.21", "Coffee, roasted, not decaffeinated", "Applies only to roasted coffee."),
            ("0901.12", "Coffee, not roasted, decaffeinated", "Applies only if decaffeinated."),
        ],
        "unit": "kg",
        "default_qty": 19200,
        "price_band": (3.2, 7.5),
        "unit_weight_kg": 1.0,
        "restrictions": ["Plant and food import controls apply; inspection on arrival is likely."],
        "certificates": ["Phytosanitary certificate", "Certificate of origin", "Food safety registration"],
    },
    {
        "key": "centrifugal_pump",
        "name": "Industrial pumps",
        "keywords": ["pump", "centrifugal", "impeller", "booster", "submersible"],
        "hs_code": "8413.70",
        "hs_label": "Other centrifugal pumps",
        "chapter": "Chapter 84: Machinery and mechanical appliances",
        "alternatives": [
            ("8413.81", "Other pumps", "Applies to non-centrifugal pump types."),
            ("8413.91", "Parts of pumps", "Applies if shipped as spare parts, not complete pumps."),
        ],
        "unit": "units",
        "default_qty": 60,
        "price_band": (900.0, 4200.0),
        "unit_weight_kg": 85.0,
        "restrictions": ["Quality control order or equivalent standard may apply for some pump categories."],
        "certificates": ["Certificate of origin", "Manufacturer test certificate"],
    },
    {
        "key": "smartphone",
        "name": "Smartphones",
        "keywords": ["smartphone", "mobile phone", "cell phone", "handset", "5g phone"],
        "hs_code": "8517.13",
        "hs_label": "Smartphones",
        "chapter": "Chapter 85: Electrical machinery and equipment",
        "alternatives": [
            ("8517.14", "Other telephones for cellular networks", "Applies to non-smartphone cellular handsets."),
            ("8517.62", "Machines for reception or transmission of data", "Applies to modules and gateways."),
        ],
        "unit": "units",
        "default_qty": 2000,
        "price_band": (120.0, 900.0),
        "unit_weight_kg": 0.45,
        "restrictions": ["Wireless equipment approval and device registration are typically required."],
        "certificates": ["Wireless equipment type approval", "Safety conformity certificate", "Certificate of origin"],
    },
    {
        "key": "olive_oil",
        "name": "Olive oil",
        "keywords": ["olive oil", "olive", "extra virgin", "evoo"],
        "hs_code": "1509.20",
        "hs_label": "Olive oil, extra virgin",
        "chapter": "Chapter 15: Animal, vegetable or microbial fats and oils",
        "alternatives": [
            ("1509.30", "Olive oil, virgin", "Applies to virgin grade rather than extra virgin."),
            ("1509.90", "Other olive oil", "Applies to refined or blended olive oils."),
        ],
        "unit": "litres",
        "default_qty": 18000,
        "price_band": (4.5, 11.0),
        "unit_weight_kg": 0.92,
        "restrictions": ["Food labelling and import registration requirements apply."],
        "certificates": ["Certificate of origin", "Food safety registration", "Analysis certificate"],
    },
]

GENERIC_ITEM: dict = {
    "key": "generic",
    "name": "General merchandise",
    "keywords": [],
    "hs_code": "8479.89",
    "hs_label": "Machines and mechanical appliances, not elsewhere specified",
    "chapter": "Chapter 84: Machinery and mechanical appliances",
    "alternatives": [
        ("8543.70", "Other electrical machines and apparatus", "Possible if the product is electrical."),
        ("3926.90", "Other articles of plastics", "Possible if the product is a moulded plastic article."),
    ],
    "unit": "units",
    "default_qty": 500,
    "price_band": (20.0, 400.0),
    "unit_weight_kg": 5.0,
    "restrictions": ["Product could not be matched confidently. Restrictions need manual review."],
    "certificates": ["Certificate of origin"],
}

# Demo "lane familiarity" heuristic. It is NOT a sanctions or country-risk list.
ORIGIN_LANES: dict[str, tuple[int, str]] = {
    "china": (14, "High-volume lane with a well-known document pattern."),
    "vietnam": (12, "Established lane for apparel and electronics."),
    "india": (8, "Domestic or regional lane with strong history."),
    "germany": (6, "Established lane with consistent documentation."),
    "united arab emirates": (12, "Frequent transshipment hub; verify the true country of origin."),
    "singapore": (10, "Frequent transshipment hub; verify the true country of origin."),
    "brazil": (11, "Established lane for agricultural goods."),
    "bangladesh": (12, "Established lane for apparel."),
    "united states": (7, "Established lane with consistent documentation."),
    "italy": (7, "Established lane with consistent documentation."),
    "spain": (7, "Established lane with consistent documentation."),
}
DEFAULT_ORIGIN = (20, "Limited lane history in demo data; extra care recommended.")

REQUIRED_DOCS = ["commercial_invoice", "packing_list", "bill_of_lading"]
DOC_LABELS = {
    "commercial_invoice": "Commercial Invoice",
    "packing_list": "Packing List",
    "bill_of_lading": "Bill of Lading",
}


def match_item(text: str) -> tuple[dict, list[str]]:
    """Return the best catalog item and the keywords that matched."""
    lowered = text.lower()
    best, best_hits = GENERIC_ITEM, []
    for item in CATALOG:
        hits = [k for k in item["keywords"] if k in lowered]
        if len(hits) > len(best_hits):
            best, best_hits = item, hits
    return best, best_hits
