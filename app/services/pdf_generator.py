from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from io import BytesIO
from datetime import datetime


def generate_bill_pdf(bill: dict, alert: dict, prediction: dict, stats: dict,
                       comparison: dict | None, savings: dict | None) -> bytes:
    """
    FESCO bill ka PDF generate karta hai.
    Returns: bytes (PDF content)
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=15 * mm,
        leftMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        "TitleStyle",
        parent=styles["Heading1"],
        fontSize=20,
        textColor=colors.HexColor("#667eea"),
        alignment=TA_CENTER,
        spaceAfter=6,
    )
    subtitle_style = ParagraphStyle(
        "SubtitleStyle",
        parent=styles["Normal"],
        fontSize=10,
        textColor=colors.HexColor("#666666"),
        alignment=TA_CENTER,
        spaceAfter=20,
    )
    section_style = ParagraphStyle(
        "SectionStyle",
        parent=styles["Heading2"],
        fontSize=14,
        textColor=colors.HexColor("#333333"),
        spaceBefore=15,
        spaceAfter=8,
    )

    story = []

    # Header
    story.append(Paragraph("⚡ FESCO Bill Tracker", title_style))
    story.append(Paragraph(
        f"Generated on {datetime.now().strftime('%d %b %Y, %I:%M %p')}",
        subtitle_style
    ))

    # Alert Box
    alert_colors = {
        "safe": colors.HexColor("#d4edda"),
        "warning": colors.HexColor("#fff3cd"),
        "danger": colors.HexColor("#f8d7da"),
        "critical": colors.HexColor("#f5c6cb"),
        "early_warning": colors.HexColor("#fff3cd"),
    }
    alert_bg = alert_colors.get(alert.get("status", "safe"), colors.HexColor("#e2e3e5"))

    alert_data = [[
        Paragraph(
            f"<b>{alert.get('status', 'Status').upper()}</b><br/>{alert.get('message', '')}",
            styles["Normal"]
        )
    ]]
    alert_table = Table(alert_data, colWidths=[180 * mm])
    alert_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), alert_bg),
        ("PADDING", (0, 0), (-1, -1), 12),
        ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#cccccc")),
    ]))
    story.append(alert_table)
    story.append(Spacer(1, 10))

    # Consumer Detail
    story.append(Paragraph("👤 Consumer Detail", section_style))
    consumer_data = [
        ["Name:", bill.get("name", "N/A")],
        ["Reference No:", bill.get("reference_no", "N/A")],
        ["Consumer ID:", bill.get("consumer_id", "N/A")],
        ["Bill Month:", bill.get("bill_month", "N/A")],
        ["Due Date:", bill.get("due_date", "N/A")],
    ]
    consumer_table = Table(consumer_data, colWidths=[45 * mm, 135 * mm])
    consumer_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e0e0e0")),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f7f8fc")),
    ]))
    story.append(consumer_table)
    story.append(Spacer(1, 15))

    # Current Bill Stats
    story.append(Paragraph("📊 Current Bill", section_style))
    bill_stats = [[
        Paragraph(f"<b>UNITS</b><br/>{bill.get('current_units', 0)}", styles["Normal"]),
        Paragraph(f"<b>CURRENT BILL</b><br/>Rs {bill.get('current_bill', 0)}", styles["Normal"]),
        Paragraph(f"<b>GRAND TOTAL</b><br/>Rs {bill.get('grand_total', 0)}", styles["Normal"]),
    ]]
    bill_table = Table(bill_stats, colWidths=[60 * mm, 60 * mm, 60 * mm])
    bill_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f7f8fc")),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("PADDING", (0, 0), (-1, -1), 15),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#dddddd")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dddddd")),
    ]))
    story.append(bill_table)
    story.append(Spacer(1, 15))

    # Prediction
    story.append(Paragraph("🔮 Prediction (Month End)", section_style))
    pred_data = [[
        Paragraph(f"<b>DAYS PASSED</b><br/>{prediction.get('days_passed', 0)}", styles["Normal"]),
        Paragraph(f"<b>DAILY AVG</b><br/>{prediction.get('daily_average', 0)}", styles["Normal"]),
        Paragraph(f"<b>PREDICTED</b><br/>{prediction.get('predicted_units', 0)} units", styles["Normal"]),
    ]]
    pred_table = Table(pred_data, colWidths=[60 * mm, 60 * mm, 60 * mm])
    pred_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f7f8fc")),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("PADDING", (0, 0), (-1, -1), 15),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#dddddd")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dddddd")),
    ]))
    story.append(pred_table)
    story.append(Spacer(1, 15))

    # Comparison
    if comparison:
        story.append(Paragraph("📊 Year-over-Year Comparison", section_style))
        story.append(Paragraph(comparison.get("message", ""), styles["Normal"]))
        story.append(Spacer(1, 10))

    # Savings Hint
    if savings:
        story.append(Paragraph("💰 Savings Hint", section_style))
        story.append(Paragraph(savings.get("message", ""), styles["Normal"]))
        if savings.get("savings_rs"):
            story.append(Paragraph(
                f"<b>Potential Savings: Rs {savings['savings_rs']}</b>",
                styles["Normal"]
            ))
        story.append(Spacer(1, 10))

    # History Table
    story.append(Paragraph("📋 12-Month History", section_style))
    history_data = [["Month", "Units", "Bill (Rs)", "Payment (Rs)"]]
    for h in bill.get("history", []):
        history_data.append([
            h["month"],
            str(h["units"]),
            str(h["bill"]),
            str(h["payment"]),
        ])
    history_table = Table(history_data, colWidths=[45 * mm, 45 * mm, 45 * mm, 45 * mm])
    history_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#667eea")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dddddd")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f9fafb")]),
    ]))
    story.append(history_table)

    # Footer
    story.append(Spacer(1, 20))
    story.append(Paragraph(
        "<i>Generated by FESCO Bill Tracker — fesco-tracker</i>",
        subtitle_style
    ))

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes