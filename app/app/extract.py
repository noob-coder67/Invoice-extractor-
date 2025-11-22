import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple

ISO_DATE = re.compile(r"\b(19|20)\d{2}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])\b")
CURRENCY = re.compile(r"\b[A-Z]{3}\b")
INVOICE_ID = re.compile(r"\b(?:INV|Invoice|Bill)[-:\s]*([A-Z0-9\-]{6,})\b", re.IGNORECASE)
NUMBER = re.compile(r"-?\d+(?:[.,]\d{3})*(?:[.,]\d{2})?")

@dataclass
class LineItem:
    description: str
    quantity: float
    unit_price: float
    amount: float
    confidence: float = 0.0
    anchors: Dict[str, str] = field(default_factory=dict)

@dataclass
class Invoice:
    invoice_id: str
    invoice_date: str
    supplier_name: str
    currency: str
    subtotal: float
    tax: float
    total: float
    line_items: List[LineItem] = field(default_factory=list)
    due_date: Optional[str] = None
    po_number: Optional[str] = None
    confidence: Dict[str, float] = field(default_factory=dict)
    issues: List[str] = field(default_factory=list)
    anchors: Dict[str, str] = field(default_factory=dict)

def parse_number(s: str) -> float:
    s = s.replace(",", "").strip()
    return float(s)

def reconcile_totals(subtotal: float, tax: float, total: float, eps: float = 0.01) -> bool:
    return abs((subtotal + tax) - total) <= eps

def extract_invoice_id(text: str) -> Tuple[str, float, str]:
    m = INVOICE_ID.search(text)
    if m:
        return m.group(1), 0.9, m.group(0)
    return "", 0.0, ""

def extract_iso_date(text: str) -> Tuple[str, float, str]:
    m = ISO_DATE.search(text)
    if m:
        return m.group(0), 0.9, m.group(0)
    return "", 0.0, ""

def extract_currency(text: str) -> Tuple[str, float, str]:
    header = text[:600]
    footer = text[-600:]
    candidates = re.findall(CURRENCY, header) + re.findall(CURRENCY, footer)
    for c in candidates:
        if c.upper() in {"USD","EUR","GBP","JPY","AUD","CAD","CHF","CNY"}:
            return c, 0.9, c
    m = CURRENCY.search(text)
    if m:
        return m.group(0), 0.8, m.group(0)
    return "", 0.0, ""

def extract_totals(text: str) -> Dict[str, Tuple[float, float, str]]:
    out = {"subtotal": (0.0, 0.0, ""), "tax": (0.0, 0.0, ""), "total": (0.0, 0.0, "")}
    for label, conf in [("Subtotal", 0.85), ("Tax", 0.85), ("Total", 0.9)]:
        pattern = re.compile(rf"{label}[:\s]*({NUMBER.pattern})", re.IGNORECASE)
        m = pattern.search(text)
        if m:
            val = parse_number(m.group(1))
            out[label.lower()] = (val, conf, m.group(0))
    return out

def extract_supplier(text: str) -> Tuple[str, float, str]:
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if lines:
        first = lines[0]
        if re.match(r"^[A-Z &]{3,}$", first):
            return first.title(), 0.8, first
        if len(first.split()) <= 6:
            return first, 0.7, first
    return "", 0.0, ""

def validate_invoice(inv: Invoice) -> Invoice:
    required = ["invoice_id", "invoice_date", "supplier_name", "currency", "subtotal", "tax", "total"]
    for f in required:
        val = getattr(inv, f)
        if (isinstance(val, str) and not val.strip()) or (isinstance(val, (int,float)) and val == 0 and f in ["subtotal","tax","total"]):
            inv.issues.append(f"Missing required field: {f}")
    if inv.invoice_date and not ISO_DATE.match(inv.invoice_date):
        inv.issues.append("Invalid invoice_date format")
    if inv.currency and not CURRENCY.match(inv.currency):
        inv.issues.append("Invalid currency code")
    for f in ["subtotal","tax","total"]:
        v = getattr(inv, f)
        if isinstance(v, (int,float)) and v < 0:
            inv.issues.append(f"Negative amount in {f}")
    if not reconcile_totals(inv.subtotal, inv.tax, inv.total):
        inv.issues.append("Totals do not reconcile")
    thresholds = {"invoice_id": 0.8, "invoice_date": 0.9, "supplier_name": 0.8, "currency": 0.9, "subtotal": 0.85, "tax": 0.85, "total": 0.9}
    for k, v in inv.confidence.items():
        if v < thresholds.get(k, 0.7):
            inv.issues.append(f"Low confidence: {k} ({v:.2f})")
    return inv

def extract_invoice(text: str) -> Invoice:
    invoice_id, conf_id, anch_id = extract_invoice_id(text)
    invoice_date, conf_date, anch_date = extract_iso_date(text)
    currency, conf_cur, anch_cur = extract_currency(text)
    totals = extract_totals(text)
    subtotal, conf_sub, anch_sub = totals["subtotal"]
    tax, conf_tax, anch_tax = totals["tax"]
    total, conf_total, anch_total = totals["total"]
    supplier_name, conf_sup, anch_sup = extract_supplier(text)

    inv = Invoice(
        invoice_id=invoice_id,
        invoice_date=invoice_date,
        supplier_name=supplier_name,
        currency=currency,
        subtotal=subtotal,
        tax=tax,
        total=total,
        confidence={
            "invoice_id": conf_id,
            "invoice_date": conf_date,
            "supplier_name": conf_sup,
            "currency": conf_cur,
            "subtotal": conf_sub,
            "tax": conf_tax,
            "total": conf_total
        },
        anchors={
            "invoice_id": anch_id,
            "invoice_date": anch_date,
            "currency": anch_cur,
            "subtotal": anch_sub,
            "tax": anch_tax,
            "total": anch_total,
            "supplier_name": anch_sup
        }
    )
    return validate_invoice(inv)
