#!/usr/bin/env python3
"""AI Real Estate Property Report PDF Generator.

Generates a multipage PDF property report (Composite Score gauge, comps, cash
flow, neighborhood, investment analysis, recommendation). Requires reportlab.

Usage:
  python3 generate_realestate_pdf.py                 # Demo mode
  python3 generate_realestate_pdf.py data.json       # From JSON
  python3 generate_realestate_pdf.py data.json out.pdf
"""

import json
import sys
from datetime import datetime

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import inch
    from reportlab.lib.colors import HexColor, white
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                     TableStyle, PageBreak)
    from reportlab.graphics.shapes import Drawing, Rect, Circle, String, Wedge
    from reportlab.graphics.charts.lineplots import LinePlot
    from reportlab.graphics.widgets.markers import makeMarker
    from reportlab.pdfgen import canvas
except ImportError:
    print("Error: reportlab is required. Install with: pip install reportlab")
    sys.exit(1)


COLORS = {
    "navy": HexColor("#1a2332"), "forest_green": HexColor("#007E33"),
    "amber": HexColor("#F59E0B"), "gold_light": HexColor("#FFBB33"),
    "danger": HexColor("#CC0000"), "info": HexColor("#2563EB"),
    "gray": HexColor("#78909c"), "light_bg": HexColor("#f5f7fa"),
    "text": HexColor("#1e293b"), "text_light": HexColor("#64748b"),
    "border": HexColor("#cbd5e1"), "header_bg": HexColor("#1a2332"),
    "white": white,
}

# Canonical signal states, weakest -> strongest (Strong Buy on the right).
SIGNAL_STATES = ["AVOID", "CAUTION", "WATCH", "BUY", "STRONG BUY"]
SIGNAL_COLORS = {
    "STRONG BUY": HexColor("#15803D"), "BUY": HexColor("#22C55E"),
    "WATCH": HexColor("#EAB308"), "CAUTION": HexColor("#F97316"),
    "AVOID": HexColor("#DC2626"),
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


def normalize_signal(name):
    """Map a free-form signal string onto a canonical SIGNAL_STATES value."""
    s = str(name).upper().strip()
    if "STRONG" in s: return "STRONG BUY"
    if "BUY" in s: return "BUY"
    if "WATCH" in s or "HOLD" in s: return "WATCH"
    if "CAUTION" in s: return "CAUTION"
    if "AVOID" in s or "PASS" in s: return "AVOID"
    return s if s in SIGNAL_COLORS else "WATCH"


def signal_color(score_or_name):
    """Color for a signal — accepts a numeric score or a signal name."""
    if isinstance(score_or_name, (int, float)):
        name = property_signal(score_or_name)
    else:
        name = normalize_signal(score_or_name)
    return SIGNAL_COLORS[name]


def draw_score_gauge(score, size=200):
    """Semicircular Composite Score gauge; arc fills from the left as score rises."""
    width = size + 40
    height = size * 0.62 + 42
    d = Drawing(width, height)
    cx, cy, R, band = width / 2, 46, size / 2, (size / 2) * 0.26
    f = max(0.0, min(1.0, score / 100.0))

    d.add(Wedge(cx, cy, R, 0, 180, fillColor=COLORS["light_bg"], strokeColor=None))
    # reportlab's Wedge raises ZeroDivisionError on a zero-angle sweep, which
    # happens at score 0 (start angle == end angle == 180). NOTE: a score of 0
    # usually means missing/garbage input, so this likely masks an upstream data
    # error — but we keep a hair of arc (epsilon) so rendering never crashes.
    arc_start = min(180 * (1 - f), 180 - 1e-3)
    d.add(Wedge(cx, cy, R, arc_start, 180, fillColor=score_color(score), strokeColor=None))
    d.add(Circle(cx, cy, R - band, fillColor=COLORS["white"], strokeColor=None))
    d.add(String(cx, cy + R + 6, "COMPOSITE SCORE", fontSize=13, fillColor=COLORS["gray"],
                 textAnchor="middle", fontName="Helvetica-Bold"))
    d.add(String(cx, cy + 4, str(int(score)), fontSize=44, fillColor=COLORS["text"],
                 textAnchor="middle", fontName="Helvetica-Bold"))
    d.add(String(cx, cy - 18, "/100", fontSize=12, fillColor=COLORS["gray"],
                 textAnchor="middle", fontName="Helvetica"))
    return d


def neighborhood_color(score):
    if score >= 80: return COLORS["forest_green"]
    if score >= 60: return COLORS["amber"]
    if score >= 40: return COLORS["gold_light"]
    return COLORS["danger"]


def create_bar_chart(categories, scores, width=470, height=200, bar_height=20,
                     gap=14, bar_x=170, label_chars=25, value_font=10, color_fn=score_color):
    """Horizontal bar chart of category scores (drives dashboard + neighborhood)."""
    d = Drawing(width, height)
    max_bar_width = width - 200
    start_y = height - 25
    text_dy = bar_height / 2 - 5

    for i, (cat, score) in enumerate(zip(categories, scores)):
        y = start_y - i * (bar_height + gap)
        d.add(String(5, y + text_dy, cat[:label_chars], fontSize=9,
                     fillColor=COLORS["text"], textAnchor="start", fontName="Helvetica"))
        d.add(Rect(bar_x, y, max_bar_width, bar_height, fillColor=COLORS["light_bg"],
                   strokeColor=None, rx=3))
        bar_width = max((score / 100) * max_bar_width, 2)
        d.add(Rect(bar_x, y, bar_width, bar_height, fillColor=color_fn(score),
                   strokeColor=None, rx=3))
        d.add(String(bar_x + max_bar_width + 10, y + text_dy, f"{int(score)}/100",
                     fontSize=value_font, fillColor=COLORS["text"], textAnchor="start",
                     fontName="Helvetica-Bold"))
    return d


def _digits_to_int(value):
    """Pull an integer out of a string like '$429,250' or 'Year 10'."""
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    return int(digits) if digits else 0


def create_appreciation_chart(projections, width=470, height=250, current_price=None):
    """Conservative/Moderate/Aggressive line chart; lines labeled at their right end.

    Each point is annotated with its dollar value. When current_price is given,
    all three series start from a shared Year 0 origin.
    """
    d = Drawing(width, height)

    if current_price is not None:
        price0 = _digits_to_int(current_price)
        projections = [{"year": "Year 0", "conservative": price0, "moderate": price0,
                        "aggressive": price0}] + list(projections)

    years = [_digits_to_int(p.get("year", "")) for p in projections]
    series = [
        ("Conservative", "conservative", COLORS["gray"], "FilledCircle"),
        ("Moderate", "moderate", COLORS["info"], "FilledSquare"),
        ("Aggressive", "aggressive", COLORS["forest_green"], "FilledDiamond"),
    ]
    plot_data = [[(yr, _digits_to_int(p.get(key, 0))) for yr, p in zip(years, projections)]
                 for _, key, _, _ in series]

    lp = LinePlot()
    lp.x, lp.y = 52, 40
    lp.width = width - 150     # room on the right for direct line labels
    lp.height = height - 70
    lp.data = plot_data
    for i, (_, _, color, marker) in enumerate(series):
        lp.lines[i].strokeColor = color
        lp.lines[i].strokeWidth = 2
        lp.lines[i].symbol = makeMarker(marker)
        lp.lines[i].symbol.fillColor = color
        lp.lines[i].symbol.strokeColor = color
        lp.lines[i].symbol.size = 5

    xmin, xmax = min(years), max(years)
    all_values = [y for s in plot_data for _, y in s]
    ymin = (min(all_values) // 50000) * 50000
    ymax = (max(all_values) // 50000 + 1) * 50000

    lp.xValueAxis.valueMin = xmin
    lp.xValueAxis.valueMax = xmax
    lp.xValueAxis.valueSteps = years
    lp.xValueAxis.labelTextFormat = lambda v: f"Yr {int(v)}"
    lp.xValueAxis.labels.fontName = "Helvetica"
    lp.xValueAxis.labels.fontSize = 8
    lp.xValueAxis.strokeColor = COLORS["border"]

    lp.yValueAxis.valueMin = ymin
    lp.yValueAxis.valueMax = ymax
    lp.yValueAxis.valueStep = 50000
    lp.yValueAxis.labelTextFormat = lambda v: f"${int(v / 1000)}K"
    lp.yValueAxis.labels.fontName = "Helvetica"
    lp.yValueAxis.labels.fontSize = 8
    lp.yValueAxis.strokeColor = COLORS["border"]
    lp.yValueAxis.visibleGrid = True
    lp.yValueAxis.gridStrokeColor = COLORS["light_bg"]
    d.add(lp)

    def px(xv):
        return lp.x + (xv - xmin) / (xmax - xmin) * lp.width

    def py(yv):
        return lp.y + (yv - ymin) / (ymax - ymin) * lp.height

    for i, (name, key, color, _) in enumerate(series):
        pts = plot_data[i]
        below = (key == "conservative")
        for xv, yv in pts:
            # At Year 0 all series share one value — label it once, in neutral text.
            if xv == xmin and current_price is not None:
                if i == 0:
                    d.add(String(px(xv), py(yv) - 13, f"${round(yv / 1000)}K", fontSize=6.5,
                                 fillColor=COLORS["text"], textAnchor="middle",
                                 fontName="Helvetica-Bold"))
                continue
            d.add(String(px(xv), py(yv) + (-12 if below else 7), f"${round(yv / 1000)}K",
                         fontSize=6.5, fillColor=color, textAnchor="middle",
                         fontName="Helvetica-Bold"))
        lx, ly = pts[-1]
        d.add(String(px(lx) + 9, py(ly) - 3, name, fontSize=8, fillColor=color,
                     textAnchor="start", fontName="Helvetica-Bold"))
    return d


def get_styles():
    base = getSampleStyleSheet()
    N, T, H1, H2 = base["Normal"], base["Title"], base["Heading1"], base["Heading2"]
    return {
        "title": ParagraphStyle("RETitle", parent=T, fontSize=28, textColor=COLORS["navy"], spaceAfter=4, fontName="Helvetica-Bold", leading=34),
        "address": ParagraphStyle("REAddress", parent=T, fontSize=22, textColor=COLORS["forest_green"], spaceAfter=4, fontName="Helvetica-Bold", leading=28),
        "price": ParagraphStyle("REPrice", parent=T, fontSize=36, textColor=COLORS["amber"], spaceAfter=4, fontName="Helvetica-Bold", leading=42),
        "heading": ParagraphStyle("REHeading", parent=H1, fontSize=20, textColor=COLORS["navy"], spaceBefore=16, spaceAfter=10, fontName="Helvetica-Bold"),
        "subheading": ParagraphStyle("RESubheading", parent=H2, fontSize=14, textColor=COLORS["forest_green"], spaceBefore=12, spaceAfter=6, fontName="Helvetica-Bold"),
        "body": ParagraphStyle("REBody", parent=N, fontSize=10, textColor=COLORS["text"], spaceAfter=6, fontName="Helvetica", leading=14),
        "body_small": ParagraphStyle("REBodySmall", parent=N, fontSize=8, textColor=COLORS["text"], spaceAfter=4, fontName="Helvetica", leading=11),
        "disclaimer": ParagraphStyle("REDisclaimer", parent=N, fontSize=6.5, textColor=COLORS["gray"], fontName="Helvetica", leading=9, spaceBefore=8),
        "grade_large": ParagraphStyle("REGrade", parent=T, fontSize=18, textColor=COLORS["navy"], spaceAfter=6, fontName="Helvetica-Bold", alignment=1),
        "td": ParagraphStyle("REtd", parent=N, fontSize=9, textColor=COLORS["text"], fontName="Helvetica", leading=11),
        "td_center": ParagraphStyle("REtdC", parent=N, fontSize=9, textColor=COLORS["text"], fontName="Helvetica", leading=11, alignment=1),
        "td_bold": ParagraphStyle("REtdB", parent=N, fontSize=9, textColor=COLORS["text"], fontName="Helvetica-Bold", leading=11),
    }


def standard_table_style(extra=None):
    """Standard table style with a navy header row."""
    cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), COLORS["header_bg"]),
        ("TEXTCOLOR", (0, 0), (-1, 0), COLORS["white"]),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, COLORS["border"]),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [COLORS["white"], COLORS["light_bg"]]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]
    if extra:
        cmds.extend(extra)
    return TableStyle(cmds)


def signal_legend_table(rows, width=512):
    """Rows of (label, active_signal) as horizontal shaded signal boxes.

    Each row shows all five states; the active one is filled with its color.
    Used to show Primary Residence vs Rental side by side.
    """
    label_w = 122
    box_w = (width - label_w) / len(SIGNAL_STATES)
    data = [[label] + list(SIGNAL_STATES) for label, _ in rows]
    t = Table(data, colWidths=[label_w] + [box_w] * len(SIGNAL_STATES), rowHeights=24)
    style = [
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (0, -1), 9),
        ("TEXTCOLOR", (0, 0), (0, -1), COLORS["text"]),
        ("FONTNAME", (1, 0), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (1, 0), (-1, -1), 7.5),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BACKGROUND", (1, 0), (-1, -1), COLORS["light_bg"]),
        ("TEXTCOLOR", (1, 0), (-1, -1), COLORS["text_light"]),
        ("INNERGRID", (1, 0), (-1, -1), 1.5, COLORS["white"]),
        ("BOX", (1, 0), (-1, -1), 0.5, COLORS["border"]),
    ]
    for r, (_, active) in enumerate(rows):
        active = normalize_signal(active)
        ci = 1 + SIGNAL_STATES.index(active)
        style.append(("BACKGROUND", (ci, r), (ci, r), SIGNAL_COLORS[active]))
        style.append(("TEXTCOLOR", (ci, r), (ci, r), COLORS["white"]))
    t.setStyle(TableStyle(style))
    return t


DISCLAIMER_TEXT = (
    "DISCLAIMER: This report is intended for research only "
    "and is NOT financial or investment advice. Real estate values, rental estimates, and "
    "investment projections are AI-generated approximations based on publicly available data. "
    "The authors and creators of this tool accept no liability for any losses incurred."
)

# Sample fallback data — used both as the report's defaults (when a payload omits
# these keys) and as the demo dataset. Read-only at the call sites.
DEFAULT_COMPS = [
    {"address": "135 Oak Ave", "price": "$412,000", "sqft": "1,780", "price_sqft": "$231", "sold_date": "Mar 2026", "distance": "0.3 mi"},
    {"address": "204 Elm St", "price": "$438,500", "sqft": "1,920", "price_sqft": "$228", "sold_date": "Feb 2026", "distance": "0.5 mi"},
    {"address": "89 Pine Dr", "price": "$405,000", "sqft": "1,750", "price_sqft": "$231", "sold_date": "Jan 2026", "distance": "0.7 mi"},
    {"address": "312 Cedar Ln", "price": "$445,000", "sqft": "2,010", "price_sqft": "$221", "sold_date": "Mar 2026", "distance": "0.4 mi"},
]
DEFAULT_APPRECIATION = [
    {"year": "Year 1", "conservative": "$429,250", "moderate": "$438,750", "aggressive": "$451,250"},
    {"year": "Year 3", "conservative": "$441,580", "moderate": "$466,915", "aggressive": "$503,235"},
    {"year": "Year 5", "conservative": "$458,240", "moderate": "$500,645", "aggressive": "$565,820"},
    {"year": "Year 10", "conservative": "$510,650", "moderate": "$601,810", "aggressive": "$762,430"},
]


class FooterCanvas(canvas.Canvas):
    """Stamps a left/center/right footer with 'Page X of Y' on every page.

    Two-pass: pages are buffered on showPage() and the footer drawn at save()
    once the total page count is known.
    """

    def __init__(self, *args, created="", **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_states = []
        self._created = created

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
        width = letter[0]
        self.setFont("Helvetica", 7)
        self.setFillColor(COLORS["gray"])
        self.drawString(50, 30, f"Created: {self._created}")
        self.drawCentredString(width / 2, 30, "AI Generated Report")
        self.drawRightString(width - 50, 30, f"Page {page_number} of {total}")


def generate_report(data, output_path):
    """Generate a multipage property research PDF report."""
    doc = SimpleDocTemplate(output_path, pagesize=letter, rightMargin=50,
                            leftMargin=50, topMargin=50, bottomMargin=50)
    S = get_styles()
    elements = []

    address = data.get("address", "123 Main Street, Austin, TX 78701")
    price = data.get("price", "$425,000")
    created_str = data.get("date") or datetime.now().astimezone().strftime("%b %d, %Y %-I:%M %p %Z")
    overall_score = data.get("overall_score", 0)
    grade = score_grade(overall_score)
    signal = property_signal(overall_score)

    # Two independent signals — a property can be a BUY for a primary residence
    # but only a WATCH as a rental (or vice versa).
    primary_signal = normalize_signal(data.get("primary_signal", signal))
    rental_signal = normalize_signal(data.get("rental_signal", signal))
    signal_rows = [("Primary Residence", primary_signal), ("Rental Investment", rental_signal)]

    # Page 1 — Cover
    elements.append(Spacer(1, 0.5 * inch))
    elements.append(Paragraph("AI Property Analysis Report", S["title"]))
    elements.append(Spacer(1, 30))
    elements.append(Paragraph(address, S["address"]))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph(price, S["price"]))
    elements.append(Spacer(1, 38))

    gauge = draw_score_gauge(overall_score)
    gauge.hAlign = "CENTER"
    elements.append(gauge)
    elements.append(Spacer(1, 18))

    color = score_color(overall_score)
    elements.append(Paragraph(
        f'Property Score: <font color="{color.hexval()}">{int(overall_score)}/100</font> '
        f'(Grade: <font color="{color.hexval()}">{grade}</font>)',
        S["grade_large"]))
    elements.append(Spacer(1, 16))
    elements.append(signal_legend_table(signal_rows))
    elements.append(Spacer(1, 30))

    prop_details = data.get("property_details", {})
    beds = prop_details.get("beds", "3")
    baths = prop_details.get("baths", "2")
    sqft = prop_details.get("sqft", "1,850")
    year_built = prop_details.get("year_built", "1998")
    lot_size = prop_details.get("lot_size", "0.18 acres")
    prop_type = prop_details.get("property_type", "Single Family Residence")

    details_data = [
        ["Property Type", Paragraph(prop_type, S["td"]), "Year Built", Paragraph(str(year_built), S["td"])],
        ["Bedrooms", Paragraph(str(beds), S["td"]), "Bathrooms", Paragraph(str(baths), S["td"])],
        ["Square Feet", Paragraph(str(sqft), S["td"]), "Lot Size", Paragraph(str(lot_size), S["td"])],
    ]
    details_table = Table(details_data, colWidths=[100, 130, 100, 130])
    details_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), COLORS["light_bg"]),
        ("BACKGROUND", (2, 0), (2, -1), COLORS["light_bg"]),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, COLORS["border"]),
        ("TEXTCOLOR", (0, 0), (-1, -1), COLORS["text"]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(details_table)
    elements.append(Spacer(1, 24))
    elements.append(Paragraph(DISCLAIMER_TEXT, S["disclaimer"]))
    elements.append(PageBreak())

    # Page 2 — Score dashboard & comps
    elements.append(Paragraph("Score Dashboard", S["heading"]))
    elements.append(Spacer(1, 6))

    categories = data.get("categories", {})
    if not categories:
        categories = {
            "Value & Comps": {"score": 72, "weight": "25%"},
            "Income Potential": {"score": 68, "weight": "20%"},
            "Neighborhood Quality": {"score": 75, "weight": "20%"},
            "Investment Upside": {"score": 65, "weight": "20%"},
            "Market Conditions": {"score": 70, "weight": "15%"},
        }
    cat_names = list(categories.keys())
    cat_scores = [categories[c].get("score", 50) if isinstance(categories[c], dict)
                  else categories[c] for c in cat_names]

    elements.append(create_bar_chart(cat_names, cat_scores))
    elements.append(Spacer(1, 12))

    score_data = [["Category", "Score", "Weight", "Status"]]
    for name, sc in zip(cat_names, cat_scores):
        weight = categories[name].get("weight", "--") if isinstance(categories[name], dict) else "--"
        status = "Strong" if sc >= 70 else ("Mixed" if sc >= 40 else "Weak")
        score_data.append([Paragraph(name, S["td"]), f"{int(sc)}/100", weight, status])
    score_table = Table(score_data, colWidths=[160, 80, 60, 100])
    score_style_extra = [("ALIGN", (1, 0), (-1, -1), "CENTER")]
    for i, sc in enumerate(cat_scores, 1):
        score_style_extra.append(("TEXTCOLOR", (3, i), (3, i), score_color(sc)))
        score_style_extra.append(("FONTNAME", (3, i), (3, i), "Helvetica-Bold"))
    score_table.setStyle(standard_table_style(score_style_extra))
    elements.append(score_table)
    elements.append(Spacer(1, 16))

    elements.append(Paragraph("Comparable Sales Analysis", S["subheading"]))
    comps = data.get("comps", []) or DEFAULT_COMPS
    comp_data = [["Address", "Sale Price", "Sq Ft", "$/Sq Ft", "Sold", "Distance"]]
    for c in comps:
        comp_data.append([
            Paragraph(c.get("address", ""), S["td"]),
            Paragraph(c.get("price", ""), S["td_center"]),
            Paragraph(str(c.get("sqft", "")), S["td_center"]),
            Paragraph(c.get("price_sqft", ""), S["td_center"]),
            Paragraph(c.get("sold_date", ""), S["td_center"]),
            Paragraph(c.get("distance", ""), S["td_center"]),
        ])
    comp_table = Table(comp_data, colWidths=[100, 80, 60, 60, 70, 60])
    comp_table.setStyle(standard_table_style([("ALIGN", (1, 0), (-1, -1), "CENTER")]))
    elements.append(comp_table)

    comp_summary = data.get("comp_summary", {})
    avg_price = comp_summary.get("avg_price", "$425,125")
    avg_sqft = comp_summary.get("avg_price_sqft", "$228/sq ft")
    elements.append(Spacer(1, 6))
    elements.append(Paragraph(
        f'<b>Comp Average:</b> {avg_price} &nbsp; | &nbsp; <b>Avg $/Sq Ft:</b> {avg_sqft}',
        ParagraphStyle("CompSummary", parent=S["body"], fontSize=10, alignment=1)))
    elements.append(PageBreak())

    # Page 3 — Cash flow projection
    elements.append(Paragraph("Cash Flow Projection", S["heading"]))
    elements.append(Spacer(1, 6))
    elements.append(Paragraph("Monthly &amp; Annual Cash Flow", S["subheading"]))

    cf_items = data.get("cashflow", {}).get("items", [
        {"item": "Gross Rental Income", "monthly": "$2,200", "annual": "$26,400"},
        {"item": "Vacancy Loss (8%)", "monthly": "-$176", "annual": "-$2,112"},
        {"item": "Effective Gross Income", "monthly": "$2,024", "annual": "$24,288"},
        {"item": "Mortgage (P&I)", "monthly": "-$1,285", "annual": "-$15,420"},
        {"item": "Property Taxes", "monthly": "-$354", "annual": "-$4,250"},
        {"item": "Insurance", "monthly": "-$125", "annual": "-$1,500"},
        {"item": "Maintenance (5%)", "monthly": "-$110", "annual": "-$1,320"},
        {"item": "Property Management (10%)", "monthly": "-$202", "annual": "-$2,429"},
        {"item": "Net Cash Flow", "monthly": "-$52", "annual": "-$631"},
    ])
    last_row = len(cf_items)
    cf_data = [["Item", "Monthly", "Annual"]]
    for idx, item in enumerate(cf_items, 1):
        bold = (idx == last_row)
        cf_data.append([Paragraph(item.get("item", ""), S["td_bold"] if bold else S["td"]),
                        item.get("monthly", ""), item.get("annual", "")])
    cf_table = Table(cf_data, colWidths=[220, 110, 110])
    cf_table.setStyle(standard_table_style([
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("FONTNAME", (1, last_row), (-1, last_row), "Helvetica-Bold"),
        ("BACKGROUND", (0, last_row), (-1, last_row), COLORS["light_bg"]),
    ]))
    elements.append(cf_table)
    elements.append(Spacer(1, 16))

    elements.append(Paragraph("Investment Metrics", S["subheading"]))
    inv_metrics = data.get("investment_metrics", {})
    metrics_rows = [
        ("Cap Rate", inv_metrics.get("cap_rate", "5.2%"), inv_metrics.get("cap_rate_status", "Fair — above 5% threshold")),
        ("Cash-on-Cash Return", inv_metrics.get("cash_on_cash", "3.8%"), inv_metrics.get("coc_status", "Below average — aim for 8%+")),
        ("Gross Rent Multiplier", inv_metrics.get("grm", "16.1x"), inv_metrics.get("grm_status", "Average for metro area")),
        ("Debt Service Coverage", inv_metrics.get("dscr", "1.05"), inv_metrics.get("dscr_status", "Tight — lenders prefer 1.25+")),
        ("1% Rule", inv_metrics.get("one_pct", "0.52%"), inv_metrics.get("one_pct_status", "Below 1% — typical for appreciation market")),
        ("Break-Even Occupancy", inv_metrics.get("breakeven", "92%"), inv_metrics.get("breakeven_status", "Tight margin — low vacancy tolerance")),
    ]
    metrics_items = [["Metric", "Value", "Assessment"]]
    for metric, value, assess in metrics_rows:
        metrics_items.append([Paragraph(metric, S["td_bold"]), Paragraph(str(value), S["td_center"]),
                              Paragraph(assess, S["td"])])
    metrics_table = Table(metrics_items, colWidths=[140, 80, 240])
    metrics_table.setStyle(standard_table_style([
        ("ALIGN", (1, 0), (1, -1), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    elements.append(metrics_table)
    elements.append(Spacer(1, 16))

    elements.append(Paragraph("Mortgage Summary", S["subheading"]))
    mortgage = data.get("mortgage", {})
    mort_rows = [
        ("Purchase Price", mortgage.get("purchase_price", "$425,000"), False),
        ("Down Payment", mortgage.get("down_payment", "$85,000 (20%)"), False),
        ("Loan Amount", mortgage.get("loan_amount", "$340,000"), False),
        ("Interest Rate", mortgage.get("rate", "6.75%"), False),
        ("Loan Term", mortgage.get("term", "30-year fixed"), False),
        ("Monthly P&I", mortgage.get("monthly_pi", "$2,205"), True),
        ("Total Monthly (PITI)", mortgage.get("monthly_piti", "$2,684"), True),
    ]
    mort_data = [["Parameter", "Value"]]
    for param, value, bold in mort_rows:
        text = f"<b>{value}</b>" if bold else str(value)
        mort_data.append([param, Paragraph(text, S["td_center"])])
    mort_table = Table(mort_data, colWidths=[160, 200])
    mort_table.setStyle(standard_table_style([("ALIGN", (1, 0), (1, 0), "CENTER")]))
    elements.append(mort_table)
    elements.append(PageBreak())

    # Page 4 — Neighborhood analysis
    elements.append(Paragraph("Neighborhood Analysis", S["heading"]))
    elements.append(Spacer(1, 6))

    neighborhood = data.get("neighborhood", {})
    hood_scores = neighborhood.get("scores", {
        "School Rating": 78, "Safety / Crime": 72, "Walkability": 65,
        "Transit Access": 55, "Dining & Shopping": 82, "Growth Trajectory": 88,
    })
    hood_chart = create_bar_chart(list(hood_scores.keys()), list(hood_scores.values()),
                                  height=160, bar_height=18, gap=10, bar_x=150,
                                  label_chars=22, value_font=9, color_fn=neighborhood_color)
    elements.append(hood_chart)
    elements.append(Spacer(1, 14))

    elements.append(Paragraph("Neighborhood Details", S["subheading"]))
    hood_details = neighborhood.get("details", [
        {"factor": "Top School", "detail": "Austin ISD — Rated 7/10", "notes": "Strong elementary, mixed middle school options"},
        {"factor": "Crime Rate", "detail": "22% below city average", "notes": "Property crime trending down 3 years"},
        {"factor": "Walk Score", "detail": "65 / Somewhat Walkable", "notes": "Groceries and restaurants within 0.5 mi"},
        {"factor": "Median Household Income", "detail": "$78,500", "notes": "12% above metro median"},
        {"factor": "Population Growth (5yr)", "detail": "+8.2%", "notes": "Strong in-migration, new developments"},
        {"factor": "Median Home Value", "detail": "$415,000", "notes": "Up 18% over 3 years"},
    ])
    hood_data = [["Factor", "Detail", "Notes"]]
    for h in hood_details:
        hood_data.append([Paragraph(h.get("factor", ""), S["td_bold"]),
                          Paragraph(h.get("detail", ""), S["td"]),
                          Paragraph(h.get("notes", ""), S["body_small"])])
    hood_table = Table(hood_data, colWidths=[130, 130, 210])
    hood_table.setStyle(standard_table_style([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    elements.append(hood_table)
    elements.append(Spacer(1, 16))

    elements.append(Paragraph("Area Demographics &amp; Trends", S["subheading"]))
    demographics = neighborhood.get("demographics", {})
    demo_data = [
        ["Demographic", "Value"],
        ["Population Growth", Paragraph(str(demographics.get("population_growth", "+8.2% (5-year)")), S["td"])],
        ["Median Age", Paragraph(str(demographics.get("median_age", "34.5 years")), S["td"])],
        ["Employment Rate", Paragraph(str(demographics.get("employment_rate", "96.2%")), S["td"])],
        ["Major Employers", Paragraph(str(demographics.get("major_employers", "Tech sector, University, Healthcare")), S["td"])],
    ]
    demo_table = Table(demo_data, colWidths=[160, 310])
    demo_table.setStyle(standard_table_style([("ALIGN", (1, 0), (1, -1), "LEFT")]))
    elements.append(demo_table)
    elements.append(PageBreak())

    # Page 5 — Investment analysis & scenarios
    elements.append(Paragraph("Investment Analysis", S["heading"]))
    elements.append(Spacer(1, 6))

    elements.append(Paragraph("Investment Strategy Comparison", S["subheading"]))
    strategies = data.get("strategies", [])
    if not strategies:
        strategies = [
            {"strategy": "Buy & Hold (Rental)", "projected_return": "7-9% annually", "timeframe": "5-10 years",
             "pros": "Passive income, appreciation, tax benefits", "risk": "Vacancy, maintenance, market downturn"},
            {"strategy": "BRRRR", "projected_return": "12-18% CoC", "timeframe": "12-18 months cycle",
             "pros": "Recycle capital, forced appreciation, scale faster", "risk": "Rehab overruns, appraisal risk, refi risk"},
            {"strategy": "Fix & Flip", "projected_return": "$35K-55K profit", "timeframe": "4-6 months",
             "pros": "Quick return, no tenant management", "risk": "Market timing, rehab costs, holding costs"},
        ]
    strat_data = [["Strategy", "Projected Return", "Timeframe", "Key Risk"]]
    for s in strategies:
        strat_data.append([Paragraph(s.get("strategy", ""), S["td_bold"]),
                           Paragraph(s.get("projected_return", ""), S["td_center"]),
                           Paragraph(s.get("timeframe", ""), S["td_center"]),
                           Paragraph(s.get("risk", ""), S["body_small"])])
    strat_table = Table(strat_data, colWidths=[110, 100, 95, 165])
    strat_table.setStyle(standard_table_style([
        ("VALIGN", (0, 0), (-1, -1), "TOP"), ("ALIGN", (1, 0), (2, -1), "CENTER")]))
    elements.append(strat_table)
    elements.append(Spacer(1, 14))

    elements.append(Paragraph("Appreciation Projections", S["subheading"]))
    projections = data.get("appreciation_projections", []) or DEFAULT_APPRECIATION
    proj_chart = create_appreciation_chart(projections, current_price=price)
    proj_chart.hAlign = "CENTER"
    elements.append(proj_chart)
    elements.append(Spacer(1, 14))

    elements.append(Paragraph("Scenario Analysis", S["subheading"]))
    scenarios = data.get("scenarios", [])
    if not scenarios:
        scenarios = [
            {"scenario": "Bull Case", "probability": "25%", "return": "+25% to +40% (5yr)",
             "trigger": "Tech job growth, rate cuts, low inventory, population boom"},
            {"scenario": "Base Case", "probability": "50%", "return": "+10% to +20% (5yr)",
             "trigger": "Steady appreciation, stable rental market, moderate growth"},
            {"scenario": "Bear Case", "probability": "25%", "return": "-5% to -15% (5yr)",
             "trigger": "Job losses, oversupply, rate hikes, recession, natural disaster"},
        ]
    sc_data = [["Scenario", "Probability", "Expected Return", "Trigger"]]
    for sc in scenarios:
        sc_data.append([Paragraph(sc.get("scenario", ""), S["td_bold"]),
                        sc.get("probability", ""), sc.get("return", ""),
                        Paragraph(sc.get("trigger", ""), S["body_small"])])
    sc_table = Table(sc_data, colWidths=[85, 75, 120, 190])
    sc_style = [("VALIGN", (0, 0), (-1, -1), "TOP"), ("ALIGN", (1, 0), (2, -1), "CENTER")]
    if len(scenarios) >= 3:
        sc_style.append(("TEXTCOLOR", (2, 1), (2, 1), COLORS["forest_green"]))
        sc_style.append(("TEXTCOLOR", (2, 2), (2, 2), COLORS["info"]))
        sc_style.append(("TEXTCOLOR", (2, 3), (2, 3), COLORS["danger"]))
        sc_style.append(("FONTNAME", (2, 1), (2, 3), "Helvetica-Bold"))
    sc_table.setStyle(standard_table_style(sc_style))
    elements.append(sc_table)
    elements.append(PageBreak())

    # Page 6 — Recommendation & risks
    elements.append(Paragraph("Recommendation &amp; Risk Factors", S["heading"]))
    elements.append(Spacer(1, 6))

    elements.append(Paragraph("Investment Recommendation", S["subheading"]))
    recommendation = data.get("recommendation", {})
    rec_signal = recommendation.get("signal", signal)
    rec_summary = recommendation.get("summary",
        "This property presents a moderate investment opportunity with solid neighborhood "
        "fundamentals and appreciation potential. Cash flow is thin at current pricing and rates, "
        "making it better suited for a buy-and-hold appreciation play rather than pure cash flow. "
        "The neighborhood's growth trajectory and below-average crime rate are strong positives. "
        "Consider negotiating 3-5% below asking price to improve returns.")
    rec_offer = recommendation.get("suggested_offer", "$405,000 - $415,000")
    rec_action = recommendation.get("action_items", [
        "Get a professional inspection — focus on roof, HVAC, and foundation",
        "Request seller concessions for closing costs or rate buydown",
        "Verify rental estimates with 3 local property managers",
        "Review HOA documents if applicable (special assessments, rental restrictions)",
        "Check flood zone status and insurance requirements",
    ])

    rec_color = signal_color(overall_score)
    elements.append(Paragraph(
        f'Signal: <font color="{rec_color.hexval()}">{rec_signal}</font> &nbsp; | &nbsp; '
        f'Suggested Offer: <font color="{COLORS["forest_green"].hexval()}">{rec_offer}</font>',
        ParagraphStyle("RecLine", parent=S["body"], fontSize=13, fontName="Helvetica-Bold",
                       alignment=1, spaceAfter=12)))
    elements.append(Paragraph(rec_summary, S["body"]))
    elements.append(Spacer(1, 10))

    elements.append(Paragraph("Action Items Before Purchase", S["subheading"]))
    for i, item in enumerate(rec_action, 1):
        elements.append(Paragraph(f"{i}. {item}", S["body"]))
    elements.append(Spacer(1, 14))

    elements.append(Paragraph("Risk Factors", S["subheading"]))
    risk_factors = data.get("risk_factors", [])
    if not risk_factors:
        risk_factors = [
            {"factor": "Market Risk", "probability": "Medium", "impact": "High",
             "notes": "Local market correction, rising rates reducing buyer pool"},
            {"factor": "Vacancy Risk", "probability": "Low-Medium", "impact": "Medium",
             "notes": "Strong rental demand in area, but thin cash flow margin"},
            {"factor": "Maintenance / Capex", "probability": "Medium", "impact": "Medium",
             "notes": "Roof age, HVAC condition, plumbing should be inspected"},
            {"factor": "Regulatory Risk", "probability": "Low", "impact": "Medium",
             "notes": "Rent control proposals, STR restrictions, zoning changes"},
            {"factor": "Natural Disaster", "probability": "Low", "impact": "High",
             "notes": "Check flood zone, wildfire risk, storm/hail history"},
        ]
    rf_data = [["Risk Factor", "Probability", "Impact", "Notes"]]
    for rf in risk_factors:
        rf_data.append([Paragraph(rf.get("factor", ""), S["td_bold"]),
                        rf.get("probability", ""), rf.get("impact", ""),
                        Paragraph(rf.get("notes", ""), S["body_small"])])
    rf_table = Table(rf_data, colWidths=[110, 80, 65, 215])
    rf_table.setStyle(standard_table_style([
        ("VALIGN", (0, 0), (-1, -1), "TOP"), ("ALIGN", (1, 0), (2, -1), "CENTER")]))
    elements.append(rf_table)
    elements.append(Spacer(1, 20))
    elements.append(Paragraph(DISCLAIMER_TEXT, S["disclaimer"]))

    doc.build(elements, canvasmaker=lambda *a, **k: FooterCanvas(*a, created=created_str, **k))
    return output_path


def get_demo_data():
    """Sample data for demo mode."""
    return {
        "address": "4821 Ridgeview Drive, Austin, TX 78735",
        "price": "$425,000",
        "date": datetime.now().astimezone().strftime("%b %d, %Y %-I:%M %p %Z"),
        "overall_score": 72,
        "primary_signal": "BUY",
        "rental_signal": "WATCH",
        "property_details": {"beds": "3", "baths": "2", "sqft": "1,850", "year_built": "1998",
                             "lot_size": "0.18 acres", "property_type": "Single Family Residence"},
        "categories": {
            "Value & Comps": {"score": 74, "weight": "25%"},
            "Income Potential": {"score": 62, "weight": "20%"},
            "Neighborhood Quality": {"score": 78, "weight": "20%"},
            "Investment Upside": {"score": 72, "weight": "20%"},
            "Market Conditions": {"score": 68, "weight": "15%"},
        },
        "comps": DEFAULT_COMPS,
        "comp_summary": {"avg_price": "$425,125", "avg_price_sqft": "$228/sq ft"},
        "cashflow": {"items": [
            {"item": "Gross Rental Income", "monthly": "$2,200", "annual": "$26,400"},
            {"item": "Vacancy Loss (8%)", "monthly": "-$176", "annual": "-$2,112"},
            {"item": "Effective Gross Income", "monthly": "$2,024", "annual": "$24,288"},
            {"item": "Mortgage (P&I)", "monthly": "-$1,285", "annual": "-$15,420"},
            {"item": "Property Taxes", "monthly": "-$354", "annual": "-$4,250"},
            {"item": "Insurance", "monthly": "-$125", "annual": "-$1,500"},
            {"item": "Maintenance (5%)", "monthly": "-$110", "annual": "-$1,320"},
            {"item": "Property Mgmt (10%)", "monthly": "-$202", "annual": "-$2,429"},
            {"item": "Net Cash Flow", "monthly": "-$52", "annual": "-$631"},
        ]},
        "investment_metrics": {
            "cap_rate": "5.2%", "cap_rate_status": "Fair — above 5% threshold for metro area",
            "cash_on_cash": "3.8%", "coc_status": "Below average — aim for 8%+ for pure cash flow",
            "grm": "16.1x", "grm_status": "Average for Austin metro area",
            "dscr": "1.05", "dscr_status": "Tight — most lenders require 1.25+",
            "one_pct": "0.52%", "one_pct_status": "Below 1% rule — typical for appreciation markets",
            "breakeven": "92%", "breakeven_status": "Tight margin — low vacancy tolerance",
        },
        "mortgage": {
            "purchase_price": "$425,000", "down_payment": "$85,000 (20%)", "loan_amount": "$340,000",
            "rate": "6.75%", "term": "30-year fixed", "monthly_pi": "$2,205", "monthly_piti": "$2,684",
        },
        "neighborhood": {
            "scores": {"School Rating": 78, "Safety / Crime": 72, "Walkability": 65,
                       "Transit Access": 55, "Dining & Shopping": 82, "Growth Trajectory": 88},
            "details": [
                {"factor": "Top School", "detail": "Austin ISD — Rated 7/10", "notes": "Strong elementary, mixed middle school"},
                {"factor": "Crime Rate", "detail": "22% below city avg", "notes": "Property crime trending down 3 years"},
                {"factor": "Walk Score", "detail": "65 / Somewhat Walkable", "notes": "Groceries and restaurants within 0.5 mi"},
                {"factor": "Median Income", "detail": "$78,500", "notes": "12% above metro median"},
                {"factor": "Pop. Growth (5yr)", "detail": "+8.2%", "notes": "Strong in-migration, new developments"},
                {"factor": "Median Home Value", "detail": "$415,000", "notes": "Up 18% over 3 years"},
            ],
            "demographics": {
                "population_growth": "+8.2% (5-year)", "median_age": "34.5 years",
                "employment_rate": "96.2%", "major_employers": "Tech sector, University of Texas, Healthcare",
            },
        },
        "strategies": [
            {"strategy": "Buy & Hold (Rental)", "projected_return": "7-9% annually", "timeframe": "5-10 years",
             "pros": "Passive income, appreciation, tax benefits", "risk": "Vacancy, maintenance costs, market downturn"},
            {"strategy": "BRRRR", "projected_return": "12-18% CoC", "timeframe": "12-18 month cycle",
             "pros": "Recycle capital, forced appreciation, scale faster", "risk": "Rehab cost overruns, appraisal risk, refi rates"},
            {"strategy": "Fix & Flip", "projected_return": "$35K-55K profit", "timeframe": "4-6 months",
             "pros": "Quick return, no tenant management", "risk": "Market timing, rehab costs, holding costs"},
        ],
        "appreciation_projections": DEFAULT_APPRECIATION,
        "scenarios": [
            {"scenario": "Bull Case", "probability": "25%", "return": "+25% to +40% (5yr)",
             "trigger": "Tech hiring boom, rate cuts, low inventory persists"},
            {"scenario": "Base Case", "probability": "50%", "return": "+10% to +20% (5yr)",
             "trigger": "Steady appreciation, stable rental market, moderate growth"},
            {"scenario": "Bear Case", "probability": "25%", "return": "-5% to -15% (5yr)",
             "trigger": "Tech layoffs, oversupply from new builds, rate hikes"},
        ],
        "recommendation": {
            "signal": "BUY",
            "summary": (
                "This property presents a solid buy-and-hold opportunity in a high-growth Austin "
                "neighborhood. Cash flow is thin at current interest rates, but the neighborhood's "
                "strong appreciation trajectory (18% over 3 years) and population growth (+8.2%) "
                "make it a compelling appreciation play. The property scores well on comps — priced "
                "at fair market value with room for negotiation. School ratings and declining crime "
                "support long-term demand. Best suited for investors with a 5+ year horizon who "
                "prioritize equity growth over immediate cash flow."
            ),
            "suggested_offer": "$405,000 - $415,000",
            "action_items": [
                "Get a professional inspection — home is 28 years old, check roof, HVAC, plumbing",
                "Request seller concessions for 2-1 rate buydown to improve Year 1 cash flow",
                "Verify rental estimates with 3 local property managers before closing",
                "Check flood zone status and get insurance quotes (Austin has flood-prone areas)",
                "Run title search — confirm no liens, easements, or encumbrances",
            ],
        },
        "risk_factors": [
            {"factor": "Market Risk", "probability": "Medium", "impact": "High",
             "notes": "Austin saw 15% correction in 2022-23; cyclical risk remains"},
            {"factor": "Vacancy Risk", "probability": "Low-Med", "impact": "Medium",
             "notes": "Strong rental demand, but new supply coming online in 2026-27"},
            {"factor": "Maintenance / Capex", "probability": "Medium", "impact": "Medium",
             "notes": "1998 build — HVAC, water heater, roof may need replacement within 5 years"},
            {"factor": "Interest Rate Risk", "probability": "Medium", "impact": "Medium",
             "notes": "Rate drops improve refinance and buyer pool; rate hikes hurt both"},
            {"factor": "Natural Disaster", "probability": "Low", "impact": "High",
             "notes": "Austin has flood and hail risk; verify flood zone and insurance coverage"},
        ],
    }


def main():
    if len(sys.argv) < 2 or sys.argv[1] == "--demo":
        output = "PROPERTY-REPORT-sample.pdf"
        generate_report(get_demo_data(), output)
        print(f"Sample report generated: {output}")
        return

    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else "PROPERTY-REPORT.pdf"
    with open(input_file, "r") as f:
        data = json.load(f)
    generate_report(data, output_file)
    print(f"Report generated: {output_file}")


if __name__ == "__main__":
    main()
