"""One-page Suspicious Activity Report (SAR) PDF for an alert, built with reportlab."""
from datetime import datetime, timezone
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .rules import inr

ROWS = 12  # related transactions shown, so the report always fits on one page
WHAT = {
    "cycle": "Money left an account and came back to it through 3-6 accounts within 48 hours (round-tripping). "
             "This can hide where the money came from.",
    "structuring": "Several transfers were kept just under a reporting level instead of one large transfer, "
                   "which can be an attempt to avoid attention.",
    "fan_in": "Many different accounts sent money to one account in a short time, a pattern seen in mule accounts.",
    "fan_out": "One account sent money to many different accounts in a short time, a pattern seen when funds are spread out.",
    "pass_through": "An account received a large amount and passed most of it on within hours, acting as a middleman.",
    "amount_spike": "A transfer was far larger than this account normally sends.",
    "velocity": "This account made far more transactions in an hour than it normally does.",
}


def _t(text):
    """Safe text for the PDF. The standard PDF fonts have no ₹ or → glyph, so we write 'Rs' and '->'."""
    return str(text).replace("₹", "Rs ").replace("→", "->")


def build(alert, account):
    """alert: dict from GET /api/alerts/{id} (with 'transactions'); account: row of the accounts table as a dict."""
    styles = getSampleStyleSheet()
    body, small = styles["Normal"], styles["Normal"].clone("small", fontSize=8, leading=10, textColor=colors.grey)
    body.fontSize, body.leading = 9.5, 12
    h = styles["Heading3"]

    def table(rows, widths, header=False):
        t = Table(rows, colWidths=widths)
        t.setStyle(TableStyle([("FONTSIZE", (0, 0), (-1, -1), 8.5), ("GRID", (0, 0), (-1, -1), 0.4, colors.lightgrey),
                               ("VALIGN", (0, 0), (-1, -1), "TOP")] +
                              ([("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke)] if header else [])))
        return t

    txs = alert["transactions"]
    notes = Table([[""]], colWidths=[170 * mm], rowHeights=[60])  # empty box for the analyst to write in
    notes.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.grey)]))
    story = [
        Paragraph("Suspicious Activity Report (draft for analyst review)", styles["Title"]),
        Paragraph(f"Alert #{alert['id']} · generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC", small),
        Spacer(1, 6),
        Paragraph("Alert summary", h),
        table([["Pattern", _t(alert["pattern"].replace("_", " "))], ["Risk level", f"{alert['level'].upper()} (score {alert['score']} / 100)"],
               ["Status", alert["status"]], ["Raised at", alert["created_at"].replace("T", " ") + " UTC"]], [35 * mm, 135 * mm]),
        Paragraph("Account", h),
        table([["Name", _t(account["name"])], ["Account ID", _t(account["id"])], ["First seen", account["created_at"].replace("T", " ") + " UTC"]],
              [35 * mm, 135 * mm]),
        Paragraph("Why it was flagged", h),
        *[Paragraph(escape(_t(r)), body, bulletText="•") for r in alert["reasons"]],  # Paragraph reads <tags>, so escape
        Paragraph("What this pattern means", h),
        Paragraph(WHAT.get(alert["pattern"], ""), body),
        Paragraph(f"Related transactions (last 24 h, showing {min(ROWS, len(txs))} of {len(txs)})", h),
        table([["Time (UTC)", "From", "To", "Amount", "Channel", "Risk"]] +
              [[t["ts"].replace("T", " "), _t(t["from_account"]), _t(t["to_account"]), _t(inr(t["amount"])), t["channel"], t["risk_score"]]
               for t in txs[:ROWS]], [38 * mm, 32 * mm, 32 * mm, 30 * mm, 20 * mm, 18 * mm], header=True),
        Paragraph("Analyst notes", h),
        notes,
        Spacer(1, 6),
        Paragraph("Generated automatically from synthetic data for review only. No real customer data is used. "
                  "The system never blocks anyone: a human analyst makes the final decision.", small),
    ]
    buf = BytesIO()
    SimpleDocTemplate(buf, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=15 * mm, bottomMargin=15 * mm,
                      title=f"SAR alert {alert['id']}").build(story)
    return buf.getvalue()
