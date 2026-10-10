"""Rough source trust classes. A hint for the reviewer, not a guarantee."""
import re
from urllib.parse import urlparse

_OFFICIAL = re.compile(r"(^|\.)(gov|gob|gouv|go)(\.[a-z]{2})?$|(^|\.)gov\.[a-z]{2}$|(^|\.)europa\.eu$|(^|\.)nic\.in$|(^|\.)wcoomd\.org$|(^|\.)wto\.org$|(^|\.)un\.org$|(^|\.)unctad\.org$")
_REFERENCE = {"wikipedia.org", "tariffnumber.com", "simplyduty.com", "flexport.com", "worldbank.org", "iccwbo.org", "dhl.com", "fedex.com", "maersk.com", "hellenicshippingnews.com"}


def host_of(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower().removeprefix("www.")
    except ValueError:
        return ""


def classify(url: str) -> str:
    host = host_of(url)
    if not host:
        return "web"
    if _OFFICIAL.search(host):
        return "official"
    if any(host == d or host.endswith("." + d) for d in _REFERENCE):
        return "reference"
    return "web"
