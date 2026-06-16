#!/usr/bin/env python3
"""
AI Real Estate Property Report PDF Generator
"""

import json
import sys
from datetime import datetime

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import inch
    from reportlab.lib.colors import HexColor, white, black
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                     TableStyle, PageBreak)
    from reportlab.graphics.shapes import Drawing, Rect, Circle, String, Line
    from reportlab.graphics.charts.lineplots import LinePlot
    from reportlab.graphics.widgets.markers import makeMarker
    from reportlab.pdfgen import canvas
except ImportError:
    print("Error: reportlab is required. Install with: pip install reportlab")
    sys.exit(1)

# Available printable width: 612 - 100 = 512
PRINTABLE_WIDTH = 512

COLORS = {
    "navy": HexColor("#1a2332"),
    "navy_light": HexColor("#243347"),
    "forest_green": HexColor("#007E33"),
    "green_light": HexColor("#00C851"),
    "amber": HexColor("#F59E0B"),
    "gold_light": HexColor("#FFBB33"),
    "danger": HexColor("#CC0000"),
    "info": HexColor("#2563EB"),
    "gray": HexColor("#78909c"),
    "light_bg": HexColor("#f5f7fa"),
    "text": HexColor("#1e293b"),
    "text_light": HexColor("#64748b"),
    "border": HexColor("#cbd5e1"),
    "header_bg": HexColor("#1a2332"),
    "row_alt": HexColor("#f0f4f8"),
    "white": white,
    "black": black,
}

def score_color(score):
    if score >= 70: return COLORS["forest_green"]
    if score >= 40: return COLORS["amber"]
    return COLORS["danger"]

def score_grade(score):
    if score >= 85: return "A+"
    if score >= 70: return "A"
    if score >= 55: return "B"
    if score >= 40: return "C"
    if score >= 25: return "D"
    return "F"

def property_signal(score):
    if score >= 85: return "STRONG BUY"
    if score >= 70: return "BUY"
    if score >= 55: return "WATCH"
    if score >= 40: return "CAUTION"
    return "AVOID"

def signal_color(score):
    if score >= 85: return COLORS["forest_green"]
    if score >= 70: return COLORS["green_light"]
    if score >= 55: return COLORS["amber"]
    if score >= 40: return COLORS["gold_light"]
    return COLORS["danger"]

def draw_score_gauge(score, size=140):
    d = Drawing(size + 20, size + 20)
    cx = size / 2 + 10
    cy = size / 2 + 10
    d.add(Circle(cx, cy, size / 2, fillColor=COLORS["light_bg"], strokeColor=COLORS["navy"], strokeWidth=2))
    color = score_color(score)
    inner_r = size / 2 - 8
    d.add(Circle(cx, cy, inner_r, fillColor=color, strokeColor=None))
    d.add(Circle(cx, cy, inner_r - 14, fillColor=COLORS["white"], strokeColor=None))
    d.add(String(cx, cy + 2, str(int(score)), fontSize=36, fillColor=COLORS["navy"], textAnchor="middle", fontName="Helvetica-Bold"))
    d.add(String(cx, cy - 18, "/ 100", fontSize=10, fillColor=COLORS["gray"], textAnchor="middle", fontName="Helvetica"))
    return d

def create_bar_chart(categories, scores, width=PRINTABLE_WIDTH, height=150, bar_height=16, gap=10, bar_x=150, color_fn=score_color):
    d = Drawing(width, height)
    max_bar_width = width - bar_x - 60
    start_y = height - 20
    text_dy = bar_height / 2 - 3

    for i, (cat, score) in enumerate(zip(categories, scores)):
        y = start_y - i * (bar_height + gap)
        d.add(String(5, y + text_dy, cat[:25], fontSize=9, fillColor=COLORS["text"], fontName="Helvetica"))
        d.add(Rect(bar_x, y, max_bar_width, bar_height, fillColor=COLORS["light_bg"], strokeColor=None, rx=3))
        bar_width = max((score / 100) * max_bar_width, 2)
        d.add(Rect(bar_x, y, bar_width, bar_height, fillColor=color_fn(score), strokeColor=None, rx=3))
        d.add(String(bar_x + max_bar_width + 10, y + text_dy, f"{int(score)}/100", fontSize=9, fillColor=COLORS["text"], fontName="Helvetica-Bold"))
    return d

def _digits_to_int(value):
    if not value: return 0
    cleaned = str(value).replace('$', '').replace(',', '').replace(' ', '')
    if '(' in cleaned or '-' in cleaned:
        cleaned = cleaned.replace('(','').replace(')','').replace('-','')
        try: return -int(float(cleaned))
        except ValueError: return 0
    try: return int(float(cleaned))
    except ValueError: return 0

def create_appreciation_chart(projections, width=PRINTABLE_WIDTH, height=180):
    d = Drawing(width, height)
    years = [int(p.get("year", 0)) for p in projections]
    series = [
        ("Conservative", "conservative", COLORS["danger"], "FilledCircle"),
        ("Moderate", "moderate", COLORS["gray"], "FilledSquare"),
        ("Aggressive", "aggressive", COLORS["forest_green"], "FilledDiamond"),
    ]
    plot_data = [[(yr, _digits_to_int(p.get(key, 0))) for yr, p in zip(years, projections)] for _, key, _, _ in series]

    lp = LinePlot()
    lp.x, lp.y, lp.width, lp.height = 55, 30, width - 85, height - 60
    lp.data = plot_data

    for i, (_, _, color, marker) in enumerate(series):
        lp.lines[i].strokeColor = color
        lp.lines[i].strokeWidth = 2
        lp.lines[i].symbol = makeMarker(marker)
        lp.lines[i].symbol.fillColor, lp.lines[i].symbol.strokeColor, lp.lines[i].symbol.size = color, color, 5

    lp.xValueAxis.valueSteps = years
    lp.xValueAxis.labelTextFormat = lambda v: f"Yr {int(v)}"
    lp.xValueAxis.labels.fontName, lp.xValueAxis.labels.fontSize = "Helvetica", 8
    lp.xValueAxis.strokeColor = COLORS["border"]

    all_values = [y for s in plot_data for _, y in s]
    v_min = (min(all_values) // 50000) * 50000 if all_values else 300000
    v_max = (max(all_values) // 50000 + 1) * 50000 if all_values else 600000
    lp.yValueAxis.valueMin, lp.yValueAxis.valueMax, lp.yValueAxis.valueStep = v_min, v_max, 50000
    lp.yValueAxis.labelTextFormat = lambda v: f"${int(v / 1000)}K"
    lp.yValueAxis.labels.fontName, lp.yValueAxis.labels.fontSize = "Helvetica", 8
    lp.yValueAxis.strokeColor = COLORS["border"]
    lp.yValueAxis.visibleGrid = True
    lp.yValueAxis.gridStrokeColor = COLORS["light_bg"]
    d.add(lp)

    legend_y = height - 12
    lx = 55
    for label, _, color, _ in series:
        d.add(Rect(lx, legend_y, 8, 8, fillColor=color, strokeColor=None))
        d.add(String(lx + 12, legend_y + 1, label, fontSize=8, fillColor=COLORS["text"], fontName="Helvetica"))
        lx += 80
    return d

def get_styles():
    styles = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("RETitle", parent=styles["Title"], fontSize=26, textColor=COLORS["navy"], spaceAfter=4, fontName="Helvetica-Bold", leading=30),
        "address": ParagraphStyle("REAddress", parent=styles["Title"], fontSize=20, textColor=COLORS["forest_green"], spaceAfter=4, fontName="Helvetica-Bold", leading=24),
        "price": ParagraphStyle("REPrice", parent=styles["Title"], fontSize=32, textColor=COLORS["amber"], spaceAfter=4, fontName="Helvetica-Bold", leading=38),
        "heading": ParagraphStyle("REHeading", parent=styles["Heading1"], fontSize=18, textColor=COLORS["navy"], spaceBefore=12, spaceAfter=8, fontName="Helvetica-Bold"),
        "subheading": ParagraphStyle("RESubheading", parent=styles["Heading2"], fontSize=12, textColor=COLORS["forest_green"], spaceBefore=10, spaceAfter=4, fontName="Helvetica-Bold"),
        "body": ParagraphStyle("REBody", parent=styles["Normal"], fontSize=9.5, textColor=COLORS["text"], spaceAfter=4, fontName="Helvetica", leading=13),
        "body_small": ParagraphStyle("REBodySmall", parent=styles["Normal"], fontSize=8, textColor=COLORS["text"], fontName="Helvetica", leading=11),
        "table_text": ParagraphStyle("RETableText", parent=styles["Normal"], fontSize=8.5, textColor=COLORS["text"], fontName="Helvetica", leading=11),
        "table_header": ParagraphStyle("RETableHeader", parent=styles["Normal"], fontSize=9, textColor=COLORS["white"], fontName="Helvetica-Bold", leading=12),
        "signal": ParagraphStyle("RESignal", parent=styles["Title"], fontSize=22, textColor=COLORS["forest_green"], fontName="Helvetica-Bold", alignment=1),
        "disclaimer": ParagraphStyle("REDisclaimer", parent=styles["Normal"], fontSize=6.5, textColor=COLORS["gray"], fontName="Helvetica", leading=9, spaceBefore=6),
        "grade_large": ParagraphStyle("REGrade", parent=styles["Title"], fontSize=16, textColor=COLORS["navy"], spaceAfter=4, fontName="Helvetica-Bold", alignment=1),
        "bullet": ParagraphStyle("REBullet", parent=styles["Normal"], fontSize=9.5, textColor=COLORS["text"], spaceAfter=4, fontName="Helvetica", leading=13, leftIndent=12),
    }

def standard_table_style(extra=None):
    cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), COLORS["header_bg"]),
        ("GRID", (0, 0), (-1, -1), 0.5, COLORS["border"]),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [COLORS["white"], COLORS["light_bg"]]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    if extra: cmds.extend(extra)
    return TableStyle(cmds)

DISCLAIMER_TEXT = "DISCLAIMER: This report is intended for research only and is NOT investment advice. Projections are AI approximations."

class FooterCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        self._created = kwargs.pop('created', datetime.now().strftime("%b %d, %Y"))
        super().__init__(*args, **kwargs)
        self._saved_states = []

    def showPage(self):
        self._saved_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._saved_states)
        for page_number, state in enumerate(self._saved_states, start=1):
            self.__dict__.update(state)
            self._draw_footer(page_number, total)
            super().showPage()
        super().save()

    def _draw_footer(self, page_number, total):
        self.setFont("Helvetica", 7)
        self.setFillColor(COLORS["gray"])
        self.drawString(50, 30, f"Created: {self._created}")
        self.drawCentredString(letter[0] / 2, 30, "AI Generated Property Report")
        self.drawRightString(letter[0] - 50, 30, f"Page {page_number} of {total}")

def wrap_cells(data_matrix, style, header_style=None):
    wrapped = []
    for row_idx, row in enumerate(data_matrix):
        wrapped_row = []
        for cell in row:
            if isinstance(cell, Paragraph):
                wrapped_row.append(cell)
            else:
                active_style = header_style if (row_idx == 0 and header_style) else style
                wrapped_row.append(Paragraph(str(cell), active_style))
        wrapped.append(wrapped_row)
    return wrapped

def generate_report(data, output_path):
    doc = SimpleDocTemplate(output_path, pagesize=letter, rightMargin=50, leftMargin=50, topMargin=50, bottomMargin=50)
    S = get_styles()
    elements = []

    address = data.get("address", "123 Main Street, Austin, TX 78701")
    price = data.get("price", "$425,000")
    overall_score = data.get("overall_score", 72)
    grade = score_grade(overall_score)
    signal = property_signal(overall_score)
    sig_color = signal_color(overall_score)

    # =====================================================================
    # PAGE 1 — COVER
    # =====================================================================
    elements.append(Spacer(1, 20))
    elements.append(Paragraph("AI Property Analysis Report", S["title"]))
    elements.append(Spacer(1, 15))
    elements.append(Paragraph(address, S["address"]))
    elements.append(Spacer(1, 10))
    elements.append(Paragraph(price, S["price"]))
    elements.append(Spacer(1, 20))

    gauge = draw_score_gauge(overall_score, size=130)
    gauge.hAlign = "CENTER"
    elements.append(gauge)
    elements.append(Spacer(1, 15))

    color = score_color(overall_score)
    elements.append(Paragraph(f'Property Score: <font color="{color.hexval()}">{int(overall_score)}/100</font> (Grade: <font color="{color.hexval()}">{grade}</font>)', S["grade_large"]))
    elements.append(Spacer(1, 5))
    elements.append(Paragraph(f'Signal: <font color="{sig_color.hexval()}">{signal}</font>', ParagraphStyle("SigL", parent=S["signal"], textColor=sig_color, fontSize=22)))
    elements.append(Spacer(1, 20))

    prop_details = data.get("property_details", {})
    details_data = [
        ["Property Type", prop_details.get("property_type", "Single Family"), "Year Built", prop_details.get("year_built", "1998")],
        ["Bedrooms", prop_details.get("beds", "3"), "Bathrooms", prop_details.get("baths", "2")],
        ["Square Feet", prop_details.get("sqft", "1,850"), "Lot Size", prop_details.get("lot_size", "0.18 acres")],
    ]
    details_table = Table(wrap_cells(details_data, S["table_text"]), colWidths=[110, 146, 110, 146])
    details_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), COLORS["light_bg"]),
        ("BACKGROUND", (2, 0), (2, -1), COLORS["light_bg"]),
        ("GRID", (0, 0), (-1, -1), 0.5, COLORS["border"]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    elements.append(details_table)
    elements.append(Spacer(1, 20))
    elements.append(Paragraph(DISCLAIMER_TEXT, S["disclaimer"]))
    elements.append(PageBreak())

    # =====================================================================
    # PAGE 2 — DASHBOARD & COMPS
    # =====================================================================
    elements.append(Paragraph("Score Dashboard", S["heading"]))
    categories = data.get("categories", {"Value & Comps": 72, "Income Potential": 68, "Neighborhood Quality": 75, "Investment Upside": 65, "Market Conditions": 70})
    cat_names = list(categories.keys())
    cat_scores = list(categories.values())

    elements.append(create_bar_chart(cat_names, cat_scores))
    elements.append(Spacer(1, 15))

    score_data = [["Category", "Score", "Status"]]
    for name, sc in zip(cat_names, cat_scores):
        status = "Strong" if sc >= 70 else "Mixed" if sc >= 40 else "Weak"
        score_data.append([name, f"{int(sc)}/100", status])
    score_table = Table(wrap_cells(score_data, S["table_text"], S["table_header"]), colWidths=[212, 150, 150])
    score_table.setStyle(standard_table_style([("ALIGN", (1, 0), (-1, -1), "CENTER")]))
    elements.append(score_table)

    elements.append(Paragraph("Comparable Sales Analysis", S["subheading"]))
    comps = data.get("comps", [
        {"address": "135 Oak Ave", "price": "$412,000", "sqft": "1,780", "sold_date": "Mar 2026", "distance": "0.3 mi"},
        {"address": "204 Elm St", "price": "$438,500", "sqft": "1,920", "sold_date": "Feb 2026", "distance": "0.5 mi"},
    ])
    comp_data = [["Address", "Sale Price", "Sq Ft", "Sold", "Distance"]]
    for c in comps:
        comp_data.append([c.get("address", ""), c.get("price", ""), c.get("sqft", ""), c.get("sold_date", ""), c.get("distance", "")])
    comp_table = Table(wrap_cells(comp_data, S["table_text"], S["table_header"]), colWidths=[172, 85, 75, 95, 85])
    comp_table.setStyle(standard_table_style([("ALIGN", (1, 0), (-1, -1), "CENTER")]))
    elements.append(comp_table)
    elements.append(PageBreak())

    # =====================================================================
    # PAGE 3 — CASH FLOW
    # =====================================================================
    elements.append(Paragraph("Cash Flow Projection", S["heading"]))
    cashflow_items = data.get("cashflow", [
        {"item": "Gross Rental Income", "monthly": "$2,200", "annual": "$26,400"},
        {"item": "Effective Gross Income", "monthly": "$2,024", "annual": "$24,288"},
        {"item": "Net Cash Flow", "monthly": "-$52", "annual": "-$631"}
    ])
    cf_data = [["Item", "Monthly", "Annual"]]
    for item in cashflow_items:
        cf_data.append([item.get("item"), item.get("monthly"), item.get("annual")])
    cf_table = Table(wrap_cells(cf_data, S["table_text"], S["table_header"]), colWidths=[272, 120, 120])
    cf_table.setStyle(standard_table_style([("ALIGN", (1,0), (-1,-1), "RIGHT")]))
    elements.append(cf_table)

    elements.append(Paragraph("Investment Metrics", S["subheading"]))
    metrics = [
        ["Metric", "Value", "Assessment"],
        ["Cap Rate", "5.2%", "Fair — above asset class floor"],
        ["Cash-on-Cash", "3.8%", "Below average structural return"]
    ]
    metrics_table = Table(wrap_cells(metrics, S["table_text"], S["table_header"]), colWidths=[140, 90, 282])
    metrics_table.setStyle(standard_table_style())
    elements.append(metrics_table)
    elements.append(PageBreak())

    # =====================================================================
    # PAGE 4 — NEIGHBORHOOD
    # =====================================================================
    elements.append(Paragraph("Neighborhood Analysis", S["heading"]))
    hood_scores = {"School Rating": 78, "Safety": 72, "Walkability": 65, "Growth Trajectory": 88}
    elements.append(create_bar_chart(list(hood_scores.keys()), list(hood_scores.values())))
    elements.append(Spacer(1, 15))

    hood_details = [["Factor", "Detail"], ["Top School", "Austin ISD - Rated 7/10"], ["Pop. Growth", "+8.2% over 5 years"]]
    hood_table = Table(wrap_cells(hood_details, S["table_text"], S["table_header"]), colWidths=[160, 352])
    hood_table.setStyle(standard_table_style())
    elements.append(hood_table)
    elements.append(PageBreak())

    # =====================================================================
    # PAGE 5 — STRATEGIES & SCENARIOS
    # =====================================================================
    elements.append(Paragraph("Investment Analysis &amp; Scenarios", S["heading"]))
    strategies = data.get("strategies", [
        {"strategy": "Buy & Hold", "return": "7-9% annual", "pros": "Passive income, compound growth", "risk": "High rate landscape"},
        {"strategy": "Fix & Flip", "return": "$35K Profit", "pros": "Liquid execution speed", "risk": "Rehab budget creep"}
    ])
    strat_data = [["Strategy", "Projected Return", "Pros", "Risks"]]
    for strat in strategies:
        strat_data.append([strat["strategy"], strat["return"], strat["pros"], strat["risk"]])
    strat_table = Table(wrap_cells(strat_data, S["table_text"], S["table_header"]), colWidths=[100, 110, 152, 150])
    strat_table.setStyle(standard_table_style())
    elements.append(strat_table)

    elements.append(Paragraph("Long-Term Value Projections", S["subheading"]))
    projections = [{"year": "1", "conservative": "430000", "moderate": "442000", "aggressive": "450000"},
                   {"year": "3", "conservative": "445000", "moderate": "475000", "aggressive": "510000"},
                   {"year": "5", "conservative": "460000", "moderate": "510000", "aggressive": "580000"}]
    elements.append(create_appreciation_chart(projections))
    elements.append(PageBreak())

    # =====================================================================
    # PAGE 6 — RECOMMENDATION & ACQUISITION
    # =====================================================================
    elements.append(Paragraph("Final Acquisition Framework", S["heading"]))
    elements.append(Paragraph("Based on the calculated metrics and sub-market indexing, this asset presents as an asymmetric appreciation play rather than an immediate liquidity engine. Financing constraints impose high initial hurdle rates.", S["body"]))
    elements.append(Spacer(1, 10))
    
    elements.append(Paragraph("Strategic Playbook &amp; Action Items", S["subheading"]))
    elements.append(Paragraph("<bullet>&bull;</bullet><b>Value-Add Capture:</b> Execute localized cosmetic refits within Year 1 to lift immediate rent caps up toward market averages.", S["bullet"]))
    elements.append(Paragraph("<bullet>&bull;</bullet><b>Rate Renegotiation:</b> Factor a standard refinancing contingency option into the mid-term holding schedule.", S["bullet"]))
    elements.append(Paragraph("<bullet>&bull;</bullet><b>Expense Containment:</b> Move property allocation to boutique hyper-local managers targeting sub-8% overhead rates.", S["bullet"]))

    doc.build(elements, canvasmaker=FooterCanvas)

if __name__ == "__main__":
    demo_data = {"address": "123 Main Street, Austin, TX 78701", "price": "$425,000", "overall_score": 76}
    generate_report(demo_data, "output.pdf")
    print("Report generated successfully as 'output.pdf'.")
