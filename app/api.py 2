from fastapi import FastAPI
from pydantic import BaseModel
from typing import Any, Dict
from .extract import extract_invoice

app = FastAPI(title="Structured Data Extraction API")

class ExtractionResult(BaseModel):
    record: Dict[str, Any]
    status: str
    issues: list
    confidence: Dict[str, float]
    anchors: Dict[str, str]

@app.post("/extract/text", response_model=ExtractionResult)
async def extract_from_text(payload: Dict[str, str]):
    text = payload.get("text", "")
    inv = extract_invoice(text)
    status = "needs_review" if len(inv.issues) > 0 else "validated"
    return {
        "record": {
            "invoice_id": inv.invoice_id,
            "invoice_date": inv.invoice_date,
            "supplier_name": inv.supplier_name,
            "currency": inv.currency,
            "subtotal": inv.subtotal,
            "tax": inv.tax,
            "total": inv.total,
            "line_items": [li.__dict__ for li in inv.line_items],
            "due_date": inv.due_date,
            "po_number": inv.po_number
        },
        "status": status,
        "issues": inv.issues,
        "confidence": inv.confidence,
        "anchors": inv.anchors
    }
