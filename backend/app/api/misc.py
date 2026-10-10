from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.ai.registry import ai_status
from app.services.workflow import SAMPLE_DIR

router = APIRouter(tags=["misc"])


@router.get("/health")
def health():
    return {"status": "ok", "ai": ai_status()}


@router.get("/samples/{name}")
def sample(name: str):
    allowed = {"commercial_invoice.pdf", "packing_list.pdf", "bill_of_lading.pdf"}
    if name not in allowed:
        raise HTTPException(404, "Sample not found.")
    path = SAMPLE_DIR / name
    if not path.exists():
        raise HTTPException(404, "Sample not generated yet. Run scripts/make_sample_docs.py.")
    return FileResponse(path, media_type="application/pdf", filename=name)
