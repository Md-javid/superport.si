import re
from difflib import SequenceMatcher


def to_number(value) -> float | None:
    """Parse '17,200 kg' / 'USD 245,000.00' into a float."""
    if value is None:
        return None
    match = re.search(r"-?\d[\d,]*\.?\d*", str(value))
    if not match:
        return None
    try:
        return float(match.group(0).replace(",", ""))
    except ValueError:
        return None


def norm_text(value: str | None) -> str:
    return re.sub(r"[^a-z0-9 ]+", " ", (value or "").lower()).strip()


def norm_id(value: str | None) -> str:
    return re.sub(r"[^A-Z0-9]", "", (value or "").upper())


def similarity(a: str | None, b: str | None) -> float:
    na, nb = norm_text(a), norm_text(b)
    if not na or not nb:
        return 0.0
    # Ignore generic legal suffixes so "Acme Ltd" matches "Acme Limited".
    drop = {"ltd", "limited", "pvt", "private", "co", "inc", "llc", "corp", "company", "gmbh", "sa"}
    tokens_a = [t for t in na.split() if t not in drop]
    tokens_b = [t for t in nb.split() if t not in drop]
    ta = " ".join(tokens_a)
    tb = " ".join(tokens_b)
    if not ta or not tb:
        return 0.0
    if ta == tb:
        return 1.0
    # If one starts with the other (common when one has address appended)
    if ta.startswith(tb) or tb.startswith(ta):
        return 0.95
    # Token subset (e.g. all core entity name words match)
    set_a, set_b = set(tokens_a), set(tokens_b)
    if set_a and (set_a.issubset(set_b) or set_b.issubset(set_a)):
        return 0.92
    return SequenceMatcher(None, ta, tb).ratio()


def doc_value(docs, doc_type: str, key: str):
    """Current value of a field on a ready document, or None."""
    for doc in docs:
        if doc.doc_type == doc_type and doc.fields:
            for f in doc.fields:
                if f["key"] == key and f.get("value") not in (None, ""):
                    return f["value"]
    return None
