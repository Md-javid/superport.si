"""Generate the three demo trade documents (text-based PDFs).

Run once:  python scripts/make_sample_docs.py
The shipment they describe: 400 lithium-ion battery packs, Shenzhen to Chennai.
The packing list and bill of lading weights differ by ~3.6% on purpose, so the
cross-check has something real to find.
"""
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

OUT = Path(__file__).resolve().parent.parent / "app" / "sample_data"
OUT.mkdir(parents=True, exist_ok=True)

PARTY = {
    "shipper": "Shenzhen VoltEdge Technologies Co., Ltd",
    "consignee": "Meridian Power Systems Pvt Ltd",
    "container": "MSKU7294816",
    "product": "Lithium-ion battery packs, 48V 100Ah, for energy storage systems",
}

DOCS = {
    "commercial_invoice.pdf": ("COMMERCIAL INVOICE", [
        ("Invoice number", "INV-VE-20260918"),
        ("Shipper", PARTY["shipper"]),
        ("Consignee", PARTY["consignee"]),
        ("Product", PARTY["product"]),
        ("Quantity", "400 units"),
        ("Unit price", "612.50"),
        ("Total value", "245,000.00"),
        ("Currency", "USD"),
        ("Country of origin", "China"),
        ("Incoterm", "FOB Shenzhen"),
    ]),
    "packing_list.pdf": ("PACKING LIST", [
        ("Shipper", PARTY["shipper"]),
        ("Consignee", PARTY["consignee"]),
        ("Product", PARTY["product"]),
        ("Quantity", "400 units"),
        ("Number of packages", "400"),
        ("Net weight", "16,000 kg"),
        ("Gross weight", "17,200 kg"),
        ("Container number", PARTY["container"]),
    ]),
    "bill_of_lading.pdf": ("BILL OF LADING", [
        ("B/L number", "MAEU260918771"),
        ("Shipper", PARTY["shipper"]),
        ("Consignee", PARTY["consignee"]),
        ("Carrier", "Maersk Line"),
        ("Vessel and voyage", "MV Ocean Meridian / 031E"),
        ("Port of loading", "Shenzhen (Yantian)"),
        ("Port of discharge", "Chennai Port (INMAA)"),
        ("Container number", PARTY["container"]),
        ("Gross weight", "17,820 kg"),
    ]),
}

for name, (title, rows) in DOCS.items():
    c = canvas.Canvas(str(OUT / name), pagesize=A4)
    w, h = A4
    c.setFillColorRGB(0.01, 0.07, 0.19)
    c.rect(0, h - 90, w, 90, fill=1, stroke=0)
    c.setFillColorRGB(1, 1, 1)
    c.setFont("Helvetica-Bold", 20)
    c.drawString(48, h - 55, title)
    c.setFont("Helvetica", 9)
    c.drawString(48, h - 74, "Sample document for SuperPort demo. Fictional companies and values.")
    y = h - 140
    c.setFillColorRGB(0.05, 0.1, 0.2)
    for label, value in rows:
        c.setFont("Helvetica", 11)
        c.drawString(48, y, f"{label}: {value}")
        y -= 28
    c.showPage()
    c.save()
    print("wrote", name)
