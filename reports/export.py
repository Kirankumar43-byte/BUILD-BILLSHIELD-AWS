"""CSV and branded PDF export. PDF is English (Helvetica has no Indian-script glyphs)."""
import csv
import io
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

SEV = {"Critical": "#EF4444", "High": "#F97316", "Medium": "#EAB308", "Low": "#22C55E"}


def _safe(v):
    s = str(v)
    return "'" + s if s[:1] in "=+-@\t\r" else s   # block CSV formula injection


def csv_bytes(findings):
    b = io.StringIO()
    w = csv.writer(b)
    w.writerow(["id", "severity", "category", "resource_type", "resource_id", "region", "title",
                "estimated_monthly_waste_usd"])
    for f in findings:
        w.writerow([_safe(x) for x in (f.id, f.severity, f.category, f.resource_type, f.resource_id,
                                       f.region, f.title, f"{f.monthly_waste:.2f}")])
    return b.getvalue().encode("utf-8")


def pdf_bytes(findings, score, fc=None, demo=False):
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    W, H = A4

    def header():
        c.setFillColor(HexColor("#0B1020")); c.rect(0, H - 90, W, 90, fill=1, stroke=0)
        c.setFillColor(HexColor("#22D3EE")); c.setFont("Helvetica-Bold", 22); c.drawString(40, H - 50, "BillShield")
        c.setFillColor(HexColor("#E5E7EB")); c.setFont("Helvetica", 10)
        c.drawString(40, H - 70, "Catch the waste. Close the risk. Before the bill arrives.")
        if demo:
            c.setFillColor(HexColor("#EAB308")); c.drawRightString(W - 40, H - 50, "DEMO DATA (synthetic)")

    header()
    y = H - 120
    c.setFillColor(HexColor("#111827")); c.setFont("Helvetica-Bold", 13)
    c.drawString(40, y, f"Health score: {score['score']}/100"); y -= 18
    c.setFont("Helvetica", 11)
    c.drawString(40, y, f"Estimated monthly waste: ${score['total_waste']:.2f} (estimate)"); y -= 16
    if fc:
        c.drawString(40, y, f"Forecast month-end bill: ${fc['total_mid']:.2f} (estimate)"); y -= 16
    y -= 10
    c.setFont("Helvetica-Bold", 11); c.drawString(40, y, "Findings"); y -= 16
    for f in sorted(findings, key=lambda x: -x.monthly_waste):
        if y < 60:
            c.showPage(); header(); y = H - 120
        c.setFillColor(HexColor(SEV[f.severity])); c.circle(46, y + 3, 4, fill=1, stroke=0)
        c.setFillColor(HexColor("#111827")); c.setFont("Helvetica", 9)
        c.drawString(58, y, f"{f.severity}: {f.title}"[:85])
        c.drawRightString(W - 40, y, f"${f.monthly_waste:.2f} est.")
        y -= 14
    c.setFont("Helvetica-Oblique", 8); c.setFillColor(HexColor("#6B7280"))
    c.drawString(40, 30, "All dollar figures are estimates. BillShield is read-only by default.")
    c.save()
    return buf.getvalue()
