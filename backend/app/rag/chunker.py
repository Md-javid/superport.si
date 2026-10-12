"""Split text into overlapping passages that end on natural boundaries."""
import re


def _tidy(text: str) -> str:
    return re.sub(r"[ \t]+", " ", re.sub(r"\r\n?", "\n", text or "")).strip()


def chunk_text(text: str, *, max_chars: int = 900, overlap: int = 150, page: int | None = None) -> list[dict]:
    text = _tidy(text)
    if not text:
        return []
    paras = [p.strip() for p in re.split(r"\n\s*\n|\n(?=[-*\d]+[.)] )", text) if p.strip()]
    pieces: list[str] = []
    for p in paras:  # hard-split any paragraph that is itself too long
        while len(p) > max_chars:
            cut = p.rfind(" ", 0, max_chars)
            cut = cut if cut > max_chars // 2 else max_chars
            pieces.append(p[:cut].strip())
            p = p[cut:].strip()
        if p:
            pieces.append(p)
    chunks, cur = [], ""
    for piece in pieces:
        if cur and len(cur) + len(piece) + 1 > max_chars:
            chunks.append(cur)
            tail = cur[-overlap:] if overlap else ""
            tail = tail[tail.find(" ") + 1 :] if " " in tail else tail  # start the overlap on a word boundary
            cur = (tail + " " + piece).strip() if len(tail) + len(piece) + 1 <= max_chars else piece
        else:
            cur = (cur + "\n" + piece).strip() if cur else piece
    if cur:
        chunks.append(cur)
    return [{"text": c, "page": page} for c in chunks if c.strip()]


def chunk_pages(pages: list[str], **kw) -> list[dict]:
    out: list[dict] = []
    for i, text in enumerate(pages, 1):
        out += chunk_text(text, page=i, **kw)
    return out
