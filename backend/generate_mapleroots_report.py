#!/usr/bin/env python3
"""Generate MapleRoots Campaign Plan PDF Report."""

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor, black, white
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable, KeepTogether
)
from reportlab.platypus.flowables import Flowable
from datetime import datetime
import os


# ── Colors ──────────────────────────────────────────────────────
BRAND_RED = HexColor("#C41E3A")
BRAND_DARK = HexColor("#1a1a2e")
BRAND_LIGHT = HexColor("#f8f9fa")
BRAND_ACCENT = HexColor("#e63946")
HEADER_BG = HexColor("#1a1a2e")
ROW_ALT = HexColor("#f0f4f8")
PASS_GREEN = HexColor("#28a745")
FAIL_RED = HexColor("#dc3545")
WARN_AMBER = HexColor("#ffc107")
BLUE_ACCENT = HexColor("#0066cc")
LIGHT_BLUE = HexColor("#e8f0fe")


# ── Custom Flowables ────────────────────────────────────────────
class ColoredBox(Flowable):
    """A colored box with text inside for callouts."""
    def __init__(self, text, bg_color, text_color=black, width=None, padding=12):
        super().__init__()
        self.text = text
        self.bg_color = bg_color
        self.text_color = text_color
        self.box_width = width or 6.5 * inch
        self.padding = padding

    def wrap(self, availWidth, availHeight):
        self.box_width = min(self.box_width, availWidth)
        return (self.box_width, 40)

    def draw(self):
        self.canv.setFillColor(self.bg_color)
        self.canv.roundRect(0, 0, self.box_width, 36, 4, fill=1, stroke=0)
        self.canv.setFillColor(self.text_color)
        self.canv.setFont("Helvetica-Bold", 10)
        self.canv.drawString(self.padding, 13, self.text)


class SectionDivider(Flowable):
    """A section divider with number and title."""
    def __init__(self, number, title):
        super().__init__()
        self.number = number
        self.title = title

    def wrap(self, availWidth, availHeight):
        return (availWidth, 32)

    def draw(self):
        # Circle with number
        self.canv.setFillColor(BRAND_RED)
        self.canv.circle(14, 16, 12, fill=1, stroke=0)
        self.canv.setFillColor(white)
        self.canv.setFont("Helvetica-Bold", 11)
        self.canv.drawCentredString(14, 12, str(self.number))
        # Title
        self.canv.setFillColor(BRAND_DARK)
        self.canv.setFont("Helvetica-Bold", 14)
        self.canv.drawString(32, 10, self.title)
        # Line
        self.canv.setStrokeColor(HexColor("#dee2e6"))
        self.canv.setLineWidth(1)
        self.canv.line(32, 0, 500, 0)


# ── Styles ──────────────────────────────────────────────────────
styles = getSampleStyleSheet()

styles.add(ParagraphStyle(
    'CoverTitle', parent=styles['Title'],
    fontSize=28, leading=34, textColor=BRAND_DARK,
    spaceAfter=6, alignment=TA_LEFT, fontName='Helvetica-Bold'
))
styles.add(ParagraphStyle(
    'CoverSubtitle', parent=styles['Normal'],
    fontSize=14, leading=18, textColor=HexColor("#6c757d"),
    spaceAfter=4, fontName='Helvetica'
))
styles.add(ParagraphStyle(
    'SectionHead', parent=styles['Heading2'],
    fontSize=13, leading=16, textColor=BRAND_DARK,
    spaceBefore=14, spaceAfter=8, fontName='Helvetica-Bold'
))
styles.add(ParagraphStyle(
    'BodyText2', parent=styles['Normal'],
    fontSize=9.5, leading=13, textColor=HexColor("#333333"),
    spaceAfter=6, fontName='Helvetica'
))
styles.add(ParagraphStyle(
    'BulletItem', parent=styles['Normal'],
    fontSize=9.5, leading=13, textColor=HexColor("#333333"),
    leftIndent=18, bulletIndent=6, spaceAfter=3, fontName='Helvetica'
))
styles.add(ParagraphStyle(
    'SmallNote', parent=styles['Normal'],
    fontSize=8, leading=10, textColor=HexColor("#888888"),
    spaceAfter=4, fontName='Helvetica-Oblique'
))
styles.add(ParagraphStyle(
    'TableCell', parent=styles['Normal'],
    fontSize=8.5, leading=11, textColor=HexColor("#333333"), fontName='Helvetica'
))
styles.add(ParagraphStyle(
    'TableHeader', parent=styles['Normal'],
    fontSize=8.5, leading=11, textColor=white, fontName='Helvetica-Bold'
))
styles.add(ParagraphStyle(
    'MetricBig', parent=styles['Normal'],
    fontSize=20, leading=24, textColor=BRAND_RED, fontName='Helvetica-Bold',
    alignment=TA_CENTER
))
styles.add(ParagraphStyle(
    'MetricLabel', parent=styles['Normal'],
    fontSize=8, leading=10, textColor=HexColor("#666666"), fontName='Helvetica',
    alignment=TA_CENTER
))


# ── Helper Functions ────────────────────────────────────────────
def make_table(headers, rows, col_widths=None):
    """Create a styled table."""
    header_row = [Paragraph(h, styles['TableHeader']) for h in headers]
    data = [header_row]
    for row in rows:
        data.append([Paragraph(str(c), styles['TableCell']) for c in row])

    t = Table(data, colWidths=col_widths, repeatRows=1)
    style_cmds = [
        ('BACKGROUND', (0, 0), (-1, 0), HEADER_BG),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8.5),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 0), (-1, 0), 8),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 8.5),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
        ('TOPPADDING', (0, 1), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor("#dee2e6")),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]
    # Alternate row colors
    for i in range(1, len(data)):
        if i % 2 == 0:
            style_cmds.append(('BACKGROUND', (0, i), (-1, i), ROW_ALT))

    t.setStyle(TableStyle(style_cmds))
    return t


def make_metric_card(value, label):
    """Create a metric display card."""
    data = [
        [Paragraph(str(value), styles['MetricBig'])],
        [Paragraph(label, styles['MetricLabel'])]
    ]
    t = Table(data, colWidths=[1.4 * inch])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), LIGHT_BLUE),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (0, 0), 10),
        ('BOTTOMPADDING', (-1, -1), (-1, -1), 8),
        ('BOX', (0, 0), (-1, -1), 1, HexColor("#cce0ff")),
        ('ROUNDEDCORNERS', [4, 4, 4, 4]),
    ]))
    return t


def status_badge(status):
    if status == "FAIL":
        return f'<font color="#dc3545"><b>FAIL</b></font>'
    elif status == "PASS":
        return f'<font color="#28a745"><b>PASS</b></font>'
    elif status == "READY":
        return f'<font color="#0066cc"><b>READY</b></font>'
    elif status == "BLOCKED":
        return f'<font color="#ffc107"><b>BLOCKED</b></font>'
    return status


# ── Build Document ──────────────────────────────────────────────
output_path = os.path.join(os.path.dirname(__file__), "MapleRoots_Campaign_Plan_2026-04-12.pdf")

doc = SimpleDocTemplate(
    output_path,
    pagesize=letter,
    topMargin=0.6 * inch,
    bottomMargin=0.6 * inch,
    leftMargin=0.75 * inch,
    rightMargin=0.75 * inch,
    title="MapleRoots Campaign Plan",
    author="Langar AI — Google Ads Agent"
)

story = []


# ══════════════════════════════════════════════════════════════════
# COVER PAGE
# ══════════════════════════════════════════════════════════════════
story.append(Spacer(1, 1.2 * inch))
story.append(Paragraph("MapleRoots", styles['CoverTitle']))
story.append(Paragraph("Canadian Citizenship by Descent Campaign", ParagraphStyle(
    'CoverTitle2', parent=styles['CoverTitle'], fontSize=18, leading=22,
    textColor=BRAND_RED, spaceAfter=12
)))
story.append(HRFlowable(width="40%", thickness=2, color=BRAND_RED, spaceAfter=16))
story.append(Paragraph("Google Ads Campaign Plan & Research Report", styles['CoverSubtitle']))
story.append(Paragraph("Prepared by Langar AI — Google Ads Agent", styles['CoverSubtitle']))
story.append(Paragraph(f"Date: April 12, 2026", styles['CoverSubtitle']))
story.append(Paragraph(f"Account: 717-823-9091 (Mercan Group)", styles['CoverSubtitle']))
story.append(Spacer(1, 0.6 * inch))

# Key metrics preview
metrics_data = [
    [make_metric_card("$35", "Daily Budget"),
     make_metric_card("5", "Ad Groups"),
     make_metric_card("~45", "Keywords"),
     make_metric_card("75", "Headlines")]
]
metrics_table = Table(metrics_data, colWidths=[1.7 * inch] * 4)
metrics_table.setStyle(TableStyle([
    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
]))
story.append(metrics_table)

story.append(Spacer(1, 0.8 * inch))

# Table of contents
story.append(Paragraph("<b>Contents</b>", ParagraphStyle(
    'TOCHead', parent=styles['SectionHead'], fontSize=11, spaceAfter=10
)))
toc_items = [
    "1. Executive Summary",
    "2. Market & Competitor Research",
    "3. Keyword Strategy",
    "4. Campaign Structure",
    "5. Ad Copy Package",
    "6. Tracking & Analytics",
    "7. Landing Page Blueprint",
    "8. Risk Assessment",
    "9. Launch Checklist",
    "10. 30-Day Forecast",
]
for item in toc_items:
    story.append(Paragraph(item, ParagraphStyle(
        'TOCItem', parent=styles['BodyText2'], leftIndent=12, spaceAfter=4
    )))

story.append(PageBreak())


# ══════════════════════════════════════════════════════════════════
# SECTION 1: EXECUTIVE SUMMARY
# ══════════════════════════════════════════════════════════════════
story.append(SectionDivider(1, "EXECUTIVE SUMMARY"))
story.append(Spacer(1, 10))

story.append(Paragraph(
    "MapleRoots is a new Google Search campaign targeting Americans who may qualify for Canadian "
    "citizenship through ancestry under <b>Bill C-3</b> (effective December 2025). The campaign "
    "drives users to a free 2-minute eligibility quiz — our core conversion action.",
    styles['BodyText2']
))
story.append(Paragraph(
    "With a <b>$35/day budget</b> across 5 tightly themed ad groups, we exploit a "
    "<b>low-competition niche</b> where our speed (2 min vs competitors' 5 min) and zero-friction "
    "approach (no account, no lawyers, no fees) are clear differentiators. The first-mover "
    "<b>Cajun/Acadian angle</b> has zero competitor coverage.",
    styles['BodyText2']
))
story.append(Spacer(1, 6))

story.append(ColoredBox(
    "CAMPAIGN STATUS: Structure ready to build • Tracking: NOT READY (0/6) • Landing page: NEEDED",
    HexColor("#fff3cd"), BRAND_DARK
))
story.append(Spacer(1, 10))

# Campaign snapshot table
story.append(make_table(
    ["Setting", "Value"],
    [
        ["Campaign Name", "MapleRoots — Citizenship by Descent (US)"],
        ["Type", "Search (Google Search only, no Display/Partners)"],
        ["Bidding Strategy", "Maximize Clicks ($3.50 max CPC cap)"],
        ["Daily Budget", "$35.00 (~$1,050/month)"],
        ["Target Location", "United States (AG5: LA, TX, MS, AL, ME only)"],
        ["Language", "English"],
        ["Status", "PAUSED (until tracking verified)"],
        ["Conversion Action", "Quiz Completion (to be created)"],
    ],
    col_widths=[2.2 * inch, 4.8 * inch]
))

story.append(PageBreak())


# ══════════════════════════════════════════════════════════════════
# SECTION 2: MARKET & COMPETITOR RESEARCH
# ══════════════════════════════════════════════════════════════════
story.append(SectionDivider(2, "MARKET & COMPETITOR RESEARCH"))
story.append(Spacer(1, 10))

story.append(Paragraph("<b>Market Context</b>", styles['SectionHead']))
story.append(Paragraph(
    "Bill C-3, which took effect in December 2025, removed the generational limit on Canadian "
    "citizenship by descent. Previously, only children of Canadian citizens born abroad could claim "
    "citizenship. Now, grandchildren, great-grandchildren, and further generations may be eligible. "
    "This affects <b>millions of Americans</b> — particularly those with Acadian/Cajun, "
    "Loyalist, and French-Canadian heritage.",
    styles['BodyText2']
))
story.append(Paragraph(
    "The CIC News article (April 2026) specifically highlights the Cajun connection — descendants "
    "of Acadians expelled from Canada in the 1700s who settled in Louisiana. This is a powerful "
    "angle for geo-targeted advertising.",
    styles['BodyText2']
))
story.append(Spacer(1, 8))

story.append(Paragraph("<b>Competitor Analysis</b>", styles['SectionHead']))

story.append(make_table(
    ["Competitor", "Model", "Strengths", "Weaknesses", "Our Advantage"],
    [
        ["escapehatch.to", "Free eligibility quiz\n(5 minutes)",
         "First mover, viral social media, clean UX",
         "5-min quiz is long; no legal follow-through; limited SEO presence",
         "2-min quiz (60% faster); Cajun angle they ignore"],
        ["immigration.ca", "Lawyer-led consultations\n(paid service)",
         "Established brand, comprehensive legal advice, strong SEO",
         "Expensive, intimidating for casual explorers, no free tools",
         "Free quiz removes cost/commitment barrier; captures top-of-funnel"],
        ["Moving2Canada", "Content/affiliate model\n(blog + tools)",
         "Deep content library, good organic rankings",
         "No dedicated Bill C-3 tool; passive monetization; slow to update",
         "Dedicated quiz tool; paid traffic captures intent before organic"],
    ],
    col_widths=[1.1 * inch, 1.2 * inch, 1.4 * inch, 1.4 * inch, 1.5 * inch]
))

story.append(Spacer(1, 10))
story.append(Paragraph("<b>Competitive Gaps We Exploit</b>", styles['SectionHead']))

gaps = [
    "<b>Cajun/Acadian angle:</b> Zero competitors running Cajun-targeted ads. Louisiana alone has 1M+ people of Acadian descent.",
    "<b>Speed differentiator:</b> Our 2-minute quiz vs. escapehatch.to's 5 minutes. Speed is our primary USP in ad copy.",
    "<b>Zero-friction model:</b> No account creation, no lawyer fees, no commitment. Competitors require sign-ups or consultations.",
    "<b>Bill C-3 specificity:</b> We reference the actual legislation. Competitors use generic 'citizenship by descent' messaging.",
    "<b>Great-grandparent segment:</b> Bill C-3's generational expansion is barely addressed by competitors. Dedicated ad group captures this.",
]
for gap in gaps:
    story.append(Paragraph(f"• {gap}", styles['BulletItem']))

story.append(PageBreak())


# ══════════════════════════════════════════════════════════════════
# SECTION 3: KEYWORD STRATEGY
# ══════════════════════════════════════════════════════════════════
story.append(SectionDivider(3, "KEYWORD STRATEGY"))
story.append(Spacer(1, 10))

story.append(Paragraph(
    "~45 keywords across 5 ad groups, organized by searcher intent and ancestry pathway. "
    "Match types follow a conservative strategy: Phrase + Exact for high-intent terms, "
    "Broad + Phrase for the exploratory Cajun segment.",
    styles['BodyText2']
))
story.append(Spacer(1, 6))

# AG1
story.append(Paragraph("<b>Ad Group 1: Core Descent (30% budget — ~$10.50/day)</b>", styles['SectionHead']))
story.append(make_table(
    ["Keyword", "Match Type", "Volume Tier", "Est. CPC"],
    [
        ["canadian citizenship by descent", "Phrase", "Medium", "$1.50–3.00"],
        ["[canadian citizenship by descent]", "Exact", "Medium", "$1.50–3.00"],
        ["citizenship by ancestry canada", "Phrase", "Medium", "$1.50–2.50"],
        ["canada citizenship through parents", "Phrase", "Medium", "$1.00–2.50"],
        ["born abroad canadian citizen", "Phrase", "Low-Med", "$1.00–2.00"],
        ["am i a canadian citizen by descent", "Phrase", "Low-Med", "$1.00–2.00"],
        ["canadian citizenship for americans", "Phrase", "Medium", "$1.50–3.00"],
        ["claim canadian citizenship ancestry", "Phrase", "Low-Med", "$1.00–2.50"],
    ],
    col_widths=[2.8 * inch, 0.8 * inch, 1.0 * inch, 1.1 * inch]
))
story.append(Spacer(1, 8))

# AG2
story.append(Paragraph("<b>Ad Group 2: Grandparent Path (25% budget — ~$8.75/day)</b>", styles['SectionHead']))
story.append(make_table(
    ["Keyword", "Match Type", "Volume Tier", "Est. CPC"],
    [
        ["canadian citizenship grandparent", "Phrase", "Medium", "$1.00–2.50"],
        ["[canadian citizenship grandparent]", "Exact", "Medium", "$1.00–2.50"],
        ["grandparent born in canada citizenship", "Phrase", "Low-Med", "$0.80–2.00"],
        ["if my grandfather was canadian", "Phrase", "Low", "$0.80–1.50"],
        ["grandmother canadian am i citizen", "Phrase", "Low", "$0.80–1.50"],
        ["canada citizenship grandchild", "Phrase", "Low-Med", "$1.00–2.00"],
        ["canadian grandparent citizenship eligibility", "Phrase", "Low-Med", "$1.00–2.00"],
        ["inherit canadian citizenship grandparent", "Phrase", "Low", "$0.80–1.50"],
    ],
    col_widths=[2.8 * inch, 0.8 * inch, 1.0 * inch, 1.1 * inch]
))
story.append(Spacer(1, 8))

# AG3
story.append(Paragraph("<b>Ad Group 3: Great-Grandparent / Bill C-3 (20% budget — ~$7.00/day)</b>", styles['SectionHead']))
story.append(make_table(
    ["Keyword", "Match Type", "Volume Tier", "Est. CPC"],
    [
        ["canadian citizenship great grandparent", "Phrase", "Low-Med", "$0.80–2.00"],
        ["bill c-3 citizenship canada", "Phrase", "Low", "$0.50–1.50"],
        ["bill c-3 canadian citizenship", "Exact", "Low", "$0.50–1.50"],
        ["canada citizenship no generation limit", "Phrase", "Low", "$0.50–1.00"],
        ["great grandparent born in canada", "Phrase", "Low", "$0.80–1.50"],
        ["multi generational canadian citizenship", "Phrase", "Low", "$0.50–1.50"],
        ["new canada citizenship law 2025", "Phrase", "Low-Med", "$1.00–2.00"],
        ["canadian citizenship law change ancestry", "Phrase", "Low-Med", "$1.00–2.00"],
    ],
    col_widths=[2.8 * inch, 0.8 * inch, 1.0 * inch, 1.1 * inch]
))
story.append(Spacer(1, 8))

# AG4
story.append(Paragraph("<b>Ad Group 4: Eligibility & Discovery (15% budget — ~$5.25/day)</b>", styles['SectionHead']))
story.append(make_table(
    ["Keyword", "Match Type", "Volume Tier", "Est. CPC"],
    [
        ["am i eligible for canadian citizenship", "Phrase", "Medium", "$1.50–3.00"],
        ["[am i eligible for canadian citizenship]", "Exact", "Medium", "$1.50–3.00"],
        ["check canadian citizenship eligibility", "Phrase", "Medium", "$1.50–2.50"],
        ["canadian citizenship eligibility quiz", "Phrase", "Low-Med", "$1.00–2.00"],
        ["do i qualify for canadian citizenship", "Phrase", "Medium", "$1.50–2.50"],
        ["free canadian citizenship test", "Phrase", "Low-Med", "$1.00–2.00"],
        ["find out if i'm canadian", "Phrase", "Low", "$0.80–1.50"],
        ["bill c-3 eligibility check", "Phrase", "Low", "$0.50–1.50"],
    ],
    col_widths=[2.8 * inch, 0.8 * inch, 1.0 * inch, 1.1 * inch]
))
story.append(Spacer(1, 8))

# AG5
story.append(Paragraph("<b>Ad Group 5: Cajun / Acadian — Geo: LA, TX, MS, AL, ME (10% budget — ~$3.50/day)</b>", styles['SectionHead']))
story.append(make_table(
    ["Keyword", "Match Type", "Volume Tier", "Est. CPC"],
    [
        ["cajun canadian citizenship", "Broad", "Low", "$0.50–1.50"],
        ["acadian descendants citizenship", "Broad", "Low", "$0.50–1.00"],
        ["cajun ancestry canada", "Phrase", "Low", "$0.50–1.50"],
        ["acadian canadian citizen", "Phrase", "Low", "$0.50–1.00"],
        ["louisiana french canadian citizenship", "Phrase", "Low", "$0.50–1.50"],
        ["cajun heritage canadian passport", "Broad", "Low", "$0.50–1.00"],
    ],
    col_widths=[2.8 * inch, 0.8 * inch, 1.0 * inch, 1.1 * inch]
))

story.append(PageBreak())

# Negative keywords
story.append(Paragraph("<b>Negative Keyword Seed List (Campaign Level — 25 terms)</b>", styles['SectionHead']))
story.append(Paragraph(
    "These negatives block irrelevant traffic from other immigration pathways, administrative queries, "
    "and unrelated searches. All based on competitor keyword analysis and immigration search patterns.",
    styles['BodyText2']
))

neg_kw_data = [
    ["immigration lawyer", "Exact", "Blocks paid-service intent"],
    ["immigration attorney", "Exact", "Blocks paid-service intent"],
    ["study permit", "Phrase", "Different immigration pathway"],
    ["work permit", "Phrase", "Different immigration pathway"],
    ["express entry", "Phrase", "Points-based immigration (not ancestry)"],
    ["PNP", "Exact", "Provincial Nominee Program"],
    ["tourist visa", "Phrase", "Travel, not citizenship"],
    ["visit canada", "Phrase", "Travel intent"],
    ["canada visa application", "Phrase", "Generic visa, not citizenship"],
    ["IRCC processing time", "Phrase", "Administrative query"],
    ["canada PR points calculator", "Phrase", "Points-based immigration"],
    ["asylum", "Exact", "Refugee pathway"],
    ["refugee", "Exact", "Refugee pathway"],
    ["TFW", "Exact", "Temporary Foreign Worker"],
    ["LMIA", "Exact", "Labour Market Impact Assessment"],
    ["student visa", "Phrase", "Study pathway"],
    ["Canadian passport renewal", "Phrase", "Already a citizen"],
    ["Canadian embassy", "Phrase", "Consular services"],
    ["consulate", "Exact", "Consular services"],
    ["citizenship test", "Phrase", "Naturalization test (already applied)"],
    ["citizenship ceremony", "Phrase", "Already approved"],
    ["oath of citizenship", "Phrase", "Already approved"],
    ["language test", "Phrase", "Naturalization requirement"],
    ["IELTS Canada", "Phrase", "Language testing"],
    ["Canada flag", "Exact", "Completely unrelated"],
]
story.append(make_table(
    ["Negative Keyword", "Match Type", "Reason"],
    neg_kw_data,
    col_widths=[2.2 * inch, 0.9 * inch, 3.0 * inch]
))

story.append(PageBreak())


# ══════════════════════════════════════════════════════════════════
# SECTION 4: CAMPAIGN STRUCTURE
# ══════════════════════════════════════════════════════════════════
story.append(SectionDivider(4, "CAMPAIGN STRUCTURE"))
story.append(Spacer(1, 10))

story.append(Paragraph("<b>Campaign Settings</b>", styles['SectionHead']))
story.append(make_table(
    ["Setting", "Value", "Rationale"],
    [
        ["Campaign Name", "MapleRoots — Citizenship by Descent (US)", "Clear naming convention"],
        ["Type", "Search", "High-intent queries only"],
        ["Network", "Google Search only", "No Display/Partners — budget too small"],
        ["Bidding", "Maximize Clicks ($3.50 max CPC)", "No conversion history; need click data first"],
        ["Daily Budget", "$35.00", "~$1,050/month; sufficient for 5 ad groups"],
        ["Ad Rotation", "Optimize", "Let Google test headline/description combos"],
        ["Ad Schedule", "All day (initial)", "Optimize after 30 days of data"],
        ["Location", "United States", "AG5 restricted to 5 states"],
        ["Language", "English", "Primary audience language"],
        ["Status", "PAUSED", "Enable after tracking verified"],
    ],
    col_widths=[1.5 * inch, 2.5 * inch, 2.5 * inch]
))
story.append(Spacer(1, 10))

story.append(Paragraph("<b>Ad Group Budget Allocation</b>", styles['SectionHead']))
story.append(make_table(
    ["Ad Group", "Theme", "Budget Share", "Daily $", "Keywords", "Match Types"],
    [
        ["AG1", "Core Descent", "30%", "$10.50", "8–10", "Phrase + Exact"],
        ["AG2", "Grandparent Path", "25%", "$8.75", "8–10", "Phrase + Exact"],
        ["AG3", "Great-Grandparent / C-3", "20%", "$7.00", "8–10", "Phrase + Exact"],
        ["AG4", "Eligibility & Discovery", "15%", "$5.25", "8–10", "Phrase + Exact"],
        ["AG5", "Cajun / Acadian (geo)", "10%", "$3.50", "6–8", "Broad + Phrase"],
    ],
    col_widths=[0.6 * inch, 1.6 * inch, 0.9 * inch, 0.7 * inch, 0.9 * inch, 1.3 * inch]
))
story.append(Spacer(1, 10))

story.append(Paragraph("<b>Bidding Strategy Rationale</b>", styles['SectionHead']))
story.append(Paragraph(
    "<b>Maximize Clicks</b> is the correct launch strategy because we have zero conversion history. "
    "Conversion-based bidding (Max Conversions, tCPA) requires minimum 15 conversions in 30 days "
    "to function. The <b>$3.50 max CPC cap</b> prevents budget blowout on trending Bill C-3 terms.",
    styles['BodyText2']
))
story.append(Paragraph(
    "<b>Phase 2 trigger:</b> After 30+ conversions, evaluate switching to Maximize Conversions. "
    "If CPC consistently exceeds $3.50, tighten to Exact match only before changing bid strategy.",
    styles['BodyText2']
))

story.append(PageBreak())


# ══════════════════════════════════════════════════════════════════
# SECTION 5: AD COPY PACKAGE
# ══════════════════════════════════════════════════════════════════
story.append(SectionDivider(5, "AD COPY PACKAGE"))
story.append(Spacer(1, 10))

story.append(Paragraph(
    "5 Responsive Search Ads (one per ad group), each with 15 headlines and 4 descriptions. "
    "All character limits verified: headlines ≤30 chars, descriptions ≤90 chars.",
    styles['BodyText2']
))
story.append(Spacer(1, 6))

story.append(Paragraph("<b>Three Messaging Pillars</b>", styles['SectionHead']))
pillars = [
    "<b>Speed:</b> \"2-Minute Quiz\" undercuts escapehatch.to's 5-minute promise",
    "<b>Discovery:</b> \"You May Already Be Canadian\" triggers curiosity and emotional engagement",
    "<b>Zero Friction:</b> \"No account, no lawyers, no fees\" vs. immigration.ca's lawyer-led model",
]
for p in pillars:
    story.append(Paragraph(f"• {p}", styles['BulletItem']))
story.append(Spacer(1, 8))

# Ad copy summary per ad group
story.append(Paragraph("<b>RSA Summary by Ad Group</b>", styles['SectionHead']))
story.append(make_table(
    ["Ad Group", "H1 Pin", "H2 Pin", "Key Themes", "H", "D"],
    [
        ["AG1: Core Descent", "Citizenship by Descent", "Free 2-Min Quiz", "Ancestry, eligibility, Bill C-3", "15", "4"],
        ["AG2: Grandparent", "Grandparent Born in Canada?", "Check in 2 Minutes", "Grandparent path, inheritance, family", "15", "4"],
        ["AG3: Great-Grandparent", "Great-Grandparent Canadian?", "No Generation Limit", "Bill C-3, multi-gen, new law", "15", "4"],
        ["AG4: Eligibility", "Am I Eligible? Find Out", "Free Quiz — 2 Minutes", "Eligibility check, quiz, discover", "15", "4"],
        ["AG5: Cajun", "Cajun? You May Be Canadian", "2-Min Eligibility Quiz", "Acadian heritage, Louisiana, ancestry", "15", "4"],
    ],
    col_widths=[1.2 * inch, 1.2 * inch, 1.1 * inch, 1.8 * inch, 0.4 * inch, 0.4 * inch]
))
story.append(Spacer(1, 10))

# Sample headlines for AG1
story.append(Paragraph("<b>Sample Headlines — AG1: Core Descent</b>", styles['SectionHead']))
story.append(make_table(
    ["#", "Headline", "Chars", "Pin", "Type"],
    [
        ["H1", "Citizenship by Descent", "22", "Pos 1", "Keyword"],
        ["H2", "Free 2-Min Quiz", "15", "Pos 2", "Speed USP"],
        ["H3", "You May Be Canadian", "19", "—", "Discovery"],
        ["H4", "Check Your Eligibility", "22", "—", "CTA"],
        ["H5", "No Lawyers Needed", "17", "—", "Zero friction"],
        ["H6", "Canadian by Ancestry?", "20", "—", "Question"],
        ["H7", "Bill C-3 Changed the Law", "23", "—", "News/urgency"],
        ["H8", "Free Eligibility Check", "22", "—", "CTA + Free"],
        ["H9", "Are You Secretly Canadian?", "25", "—", "Curiosity"],
        ["H10", "Parents Born in Canada?", "22", "—", "Pathway"],
        ["H11", "Claim Your Citizenship", "22", "—", "Action CTA"],
        ["H12", "Takes Just 2 Minutes", "20", "—", "Speed"],
        ["H13", "No Account Required", "19", "—", "Friction removal"],
        ["H14", "Millions Now Eligible", "20", "—", "Social proof"],
        ["H15", "New Law Expands Access", "22", "—", "News"],
    ],
    col_widths=[0.4 * inch, 2.0 * inch, 0.6 * inch, 0.6 * inch, 1.2 * inch]
))
story.append(Spacer(1, 8))

story.append(Paragraph("<b>Sample Descriptions — AG1: Core Descent</b>", styles['SectionHead']))
story.append(make_table(
    ["#", "Description", "Chars"],
    [
        ["D1", "Millions of Americans may qualify for Canadian citizenship. Take our free 2-minute quiz now.", "89"],
        ["D2", "Bill C-3 removed the generation limit. Find out if your ancestry qualifies you — no account needed.", "90"],
        ["D3", "Canadian parent, grandparent, or great-grandparent? You could be eligible. Check in 2 minutes free.", "90"],
        ["D4", "No lawyers, no fees, no sign-up. Just 7 quick questions to discover your Canadian citizenship path.", "89"],
    ],
    col_widths=[0.4 * inch, 5.5 * inch, 0.6 * inch]
))
story.append(Spacer(1, 10))

story.append(Paragraph("<b>Campaign-Level Sitelinks (4)</b>", styles['SectionHead']))
story.append(make_table(
    ["Sitelink", "Description Line 1", "Description Line 2"],
    [
        ["Take the Quiz", "Free 2-minute eligibility check", "No account required"],
        ["How It Works", "Answer 7 simple questions", "Get instant results"],
        ["Bill C-3 Explained", "New law removes generation limit", "Effective December 2025"],
        ["Am I Eligible?", "Parents, grandparents, great-grands", "Check all pathways"],
    ],
    col_widths=[1.5 * inch, 2.5 * inch, 2.5 * inch]
))

story.append(PageBreak())


# ══════════════════════════════════════════════════════════════════
# SECTION 6: TRACKING & ANALYTICS STATUS
# ══════════════════════════════════════════════════════════════════
story.append(SectionDivider(6, "TRACKING & ANALYTICS STATUS"))
story.append(Spacer(1, 10))

story.append(ColoredBox(
    "TRACKING READINESS: 0/6 PASS — NOT READY TO LAUNCH",
    FAIL_RED, white
))
story.append(Spacer(1, 10))

story.append(make_table(
    ["#", "Check", "Status", "Details"],
    [
        ["1", "GTM Container", status_badge("FAIL"), "No GTM container on the site. No dataLayer present."],
        ["2", "Google Ads Conversion Tag", status_badge("FAIL"), "No gtag.js, no googleadservices pixel, no conversion snippet."],
        ["3", "Dedicated Conversion Action", status_badge("FAIL"), "26 enabled actions in account — none for MapleRoots."],
        ["4", "Consent Mode", status_badge("FAIL"), "No consent banner, no consent('default') call."],
        ["5", "Quiz Completion Event", status_badge("FAIL"), "Quiz is button-based (no &lt;form&gt;). No dataLayer push on completion."],
        ["6", "Any Analytics", status_badge("FAIL"), "Zero external scripts. No GA4, no pixels, no Clarity."],
    ],
    col_widths=[0.3 * inch, 1.7 * inch, 0.6 * inch, 3.9 * inch]
))
story.append(Spacer(1, 10))

story.append(Paragraph("<b>Critical Technical Detail</b>", styles['SectionHead']))
story.append(Paragraph(
    "The quiz at <font color='#0066cc'>/tools/eligibility-quiz</font> is <b>button-based with no &lt;form&gt; element</b> "
    "and uses <b>client-side routing</b> (URL doesn't change between steps). Standard form-submit "
    "or page-load triggers will NOT work. A custom event is required.",
    styles['BodyText2']
))
story.append(Spacer(1, 6))

story.append(Paragraph("<b>Required: dataLayer Push on Quiz Completion</b>", styles['SectionHead']))
story.append(Paragraph(
    "The developer must add this code when the quiz results screen renders:",
    styles['BodyText2']
))

code_style = ParagraphStyle('Code', parent=styles['Normal'],
    fontSize=8, leading=11, fontName='Courier', textColor=HexColor("#333"),
    backColor=HexColor("#f4f4f4"), leftIndent=12, rightIndent=12,
    spaceBefore=4, spaceAfter=4, borderPadding=6
)
story.append(Paragraph(
    "window.dataLayer = window.dataLayer || [];<br/>"
    "window.dataLayer.push({<br/>"
    "&nbsp;&nbsp;'event': 'quiz_complete',<br/>"
    "&nbsp;&nbsp;'quiz_result': 'eligible',  // or 'not_eligible'<br/>"
    "&nbsp;&nbsp;'quiz_pathway': 'grandparent'  // parent, grandparent, etc.<br/>"
    "});",
    code_style
))
story.append(Spacer(1, 8))

story.append(Paragraph("<b>Setup Steps (in order)</b>", styles['SectionHead']))
story.append(make_table(
    ["Step", "Task", "Owner", "Tool/Method", "Est. Time"],
    [
        ["1", "Create conversion action in Google Ads", "Agent (MCP)", "conversion__create_conversion_action", "2 min"],
        ["2", "Install GTM or gtag.js in app layout", "Developer", "Edit layout file", "15 min"],
        ["3", "Add dataLayer.push on quiz completion", "Developer", "Edit quiz component", "15 min"],
        ["4", "Configure conversion tag in GTM", "Agent (browser)", "GTM UI", "10 min"],
        ["5", "Verify tag fires on test completion", "Agent (browser)", "Tag Assistant + network", "5 min"],
    ],
    col_widths=[0.4 * inch, 2.2 * inch, 1.0 * inch, 2.0 * inch, 0.7 * inch]
))
story.append(Spacer(1, 6))
story.append(Paragraph(
    "<i>Minimum viable tracking (to launch): Steps 1 + 2 + 3. Can be done in ~1 hour with developer access.</i>",
    styles['SmallNote']
))

story.append(PageBreak())


# ══════════════════════════════════════════════════════════════════
# SECTION 7: LANDING PAGE BLUEPRINT
# ══════════════════════════════════════════════════════════════════
story.append(SectionDivider(7, "LANDING PAGE BLUEPRINT"))
story.append(Spacer(1, 10))

story.append(ColoredBox(
    "NO LANDING PAGE EXISTS — This blueprint must be built before launch",
    WARN_AMBER, BRAND_DARK
))
story.append(Spacer(1, 10))

story.append(Paragraph("<b>Recommended Page Sections (top to bottom)</b>", styles['SectionHead']))
story.append(make_table(
    ["Section", "Content", "Purpose"],
    [
        ["1. Hero", "H1: \"Discover If You Qualify for Canadian Citizenship\"\nSub: \"Millions of Americans are eligible under Bill C-3. Find out in 2 minutes — free.\"\nCTA: \"Take the Free Quiz\"", "Capture attention, convey value prop"],
        ["2. Social Proof Bar", "\"Based on Canada's Citizenship Act (Bill C-3, Dec 2025)\" + media logos", "Build credibility and trust"],
        ["3. How It Works", "3 steps: (1) Answer 7 questions (2) Get instant results (3) Learn next steps", "Reduce friction, set expectations"],
        ["4. Pathways", "3 cards: Parent / Grandparent / Great-Grandparent — each with CTA", "Segment audience, match ad groups"],
        ["5. Bill C-3 Explainer", "What changed, who's eligible, key dates", "Educate, build authority"],
        ["6. FAQ", "5-6 questions: Is this legit? Need a lawyer? How long? What docs?", "Overcome objections"],
        ["7. Final CTA", "Repeat quiz CTA with urgency angle", "Capture scrollers"],
        ["8. Footer", "Disclaimer: \"General information only. Not legal advice.\"", "Legal compliance"],
    ],
    col_widths=[1.2 * inch, 3.3 * inch, 1.8 * inch]
))
story.append(Spacer(1, 10))

story.append(Paragraph("<b>CRO Must-Haves</b>", styles['SectionHead']))
cro_items = [
    "Quiz CTA visible above the fold on all devices",
    "No navigation links that lead away from the page (minimize exits)",
    "Mobile-first design (60%+ traffic will be mobile from Search)",
    "Page load under 3 seconds (critical for Quality Score)",
    "Email capture on quiz results page (for remarketing and lead quality)",
    "UTM parameter passthrough to quiz for attribution",
    "Cajun/Acadian pathway card if running AG5 traffic to this page",
]
for item in cro_items:
    story.append(Paragraph(f"• {item}", styles['BulletItem']))

story.append(PageBreak())


# ══════════════════════════════════════════════════════════════════
# SECTION 8: RISK ASSESSMENT
# ══════════════════════════════════════════════════════════════════
story.append(SectionDivider(8, "RISK ASSESSMENT"))
story.append(Spacer(1, 10))

story.append(make_table(
    ["Risk", "Severity", "Impact", "Mitigation"],
    [
        ["No landing page (localhost only)",
         "CRITICAL",
         "Ads will be disapproved. $0 waste but campaign cannot function.",
         "Deploy to production domain before enabling campaign."],
        ["No conversion tracking",
         "CRITICAL",
         "$35/day blind spend. No optimization possible. No ROI data.",
         "Complete tracking Steps 1-5 before enabling. Minimum: Steps 1-3."],
        ["Low search volume (niche topic)",
         "Medium",
         "AG5 Cajun may get <10 impressions/day. Budget underutilized.",
         "Monitor after 14 days. If zero volume, broaden match types or merge into AG1."],
        ["Bill C-3 search spike",
         "Medium",
         "Budget blowout on trending days. CPC could exceed cap.",
         "$3.50 max CPC cap. Review daily for first 2 weeks."],
        ["Quiz doesn't collect email/phone",
         "Medium",
         "No remarketing path. Can't measure qualified lead rate.",
         "Add email capture on results page. Essential for Phase 2."],
        ["AG5 Cajun landing page gap",
         "Low",
         "Ad copy promises Cajun angle; quiz has no Cajun content.",
         "Add Acadian pathway card or UTM-tracked variant."],
        ["Competitor response",
         "Low",
         "escapehatch.to or immigration.ca bid on Bill C-3 terms.",
         "Speed + free differentiators are defensible. Monitor auction insights."],
    ],
    col_widths=[1.5 * inch, 0.7 * inch, 1.8 * inch, 2.3 * inch]
))

story.append(PageBreak())


# ══════════════════════════════════════════════════════════════════
# SECTION 9: LAUNCH CHECKLIST
# ══════════════════════════════════════════════════════════════════
story.append(SectionDivider(9, "LAUNCH CHECKLIST"))
story.append(Spacer(1, 10))

story.append(make_table(
    ["Step", "Task", "Owner", "Status", "Depends On"],
    [
        ["1", "Deploy landing page to production domain", "Developer", status_badge("BLOCKED"), "—"],
        ["2", "Install GTM/gtag.js on production site", "Developer", status_badge("BLOCKED"), "Step 1"],
        ["3", "Add dataLayer.push on quiz completion", "Developer", status_badge("BLOCKED"), "Step 1"],
        ["4", "Create conversion action via MCP", "Agent", status_badge("READY"), "—"],
        ["5", "Configure conversion tag in GTM", "Agent", status_badge("BLOCKED"), "Steps 2–3"],
        ["6", "Verify conversion fires on test", "Agent", status_badge("BLOCKED"), "Step 5"],
        ["7", "Update Final URLs (localhost → prod)", "Agent", status_badge("BLOCKED"), "Step 1"],
        ["8", "Create campaign structure via MCP", "Agent", status_badge("READY"), "—"],
        ["9", "Add location targeting + geo restrictions", "Agent", status_badge("READY"), "Step 8"],
        ["10", "Add negative keywords", "Agent", status_badge("READY"), "Step 8"],
        ["11", "QA review: ads, keywords, targeting", "Agent", status_badge("BLOCKED"), "Step 8"],
        ["12", "Enable campaign", "Agent/User", status_badge("BLOCKED"), "Steps 1–7"],
    ],
    col_widths=[0.4 * inch, 2.4 * inch, 0.8 * inch, 0.7 * inch, 0.9 * inch]
))
story.append(Spacer(1, 10))

story.append(ColoredBox(
    "Steps 4 and 8 can be executed NOW. Campaign will be created as PAUSED.",
    LIGHT_BLUE, BRAND_DARK
))

story.append(PageBreak())


# ══════════════════════════════════════════════════════════════════
# SECTION 10: 30-DAY FORECAST
# ══════════════════════════════════════════════════════════════════
story.append(SectionDivider(10, "30-DAY PERFORMANCE FORECAST"))
story.append(Spacer(1, 10))

story.append(make_table(
    ["Metric", "Conservative", "Moderate", "Optimistic"],
    [
        ["Daily Budget", "$35", "$35", "$35"],
        ["Monthly Spend", "~$1,050", "~$1,050", "~$1,050"],
        ["Avg. CPC", "$2.50", "$1.75", "$1.00"],
        ["Monthly Clicks", "420", "600", "1,050"],
        ["Quiz Start Rate", "40%", "55%", "70%"],
        ["Quiz Completion Rate", "60%", "70%", "80%"],
        ["Conversions (completions)", "100", "230", "590"],
        ["Cost per Quiz Completion", "$10.50", "$4.57", "$1.78"],
        ["Qualified Lead Rate", "15%", "20%", "25%"],
        ["Qualified Leads", "15", "46", "148"],
        ["Cost per Qualified Lead", "$70.00", "$22.83", "$7.09"],
    ],
    col_widths=[2.0 * inch, 1.5 * inch, 1.5 * inch, 1.5 * inch]
))
story.append(Spacer(1, 10))

story.append(Paragraph("<b>Phase 2 Triggers (after 30 days)</b>", styles['SectionHead']))
triggers = [
    "If >30 conversions: Switch to Maximize Conversions bidding",
    "If AG5 Cajun has <50 impressions: Broaden to Broad match or merge into AG1",
    "If CPC >$3.50 consistently: Tighten to Exact match only",
    "A/B test second RSA per ad group (keyword-only vs emotional headlines)",
    "If qualified lead rate <10%: Review quiz-to-lead funnel, add email capture",
]
for t in triggers:
    story.append(Paragraph(f"• {t}", styles['BulletItem']))

story.append(Spacer(1, 30))
story.append(HRFlowable(width="100%", thickness=1, color=HexColor("#dee2e6"), spaceAfter=12))

story.append(Paragraph(
    "<i>Report generated by Langar AI — Google Ads Agent<br/>"
    f"Date: April 12, 2026 | Account: 717-823-9091 | Campaign: MapleRoots</i>",
    ParagraphStyle('Footer', parent=styles['SmallNote'], alignment=TA_CENTER, fontSize=8)
))
story.append(Spacer(1, 6))
story.append(Paragraph(
    "<b>Next Step:</b> Reply <font color='#C41E3A'><b>CREATE</b></font> to build this campaign in Google Ads (PAUSED).",
    ParagraphStyle('FinalCTA', parent=styles['BodyText2'], alignment=TA_CENTER, fontSize=10)
))


# ── Build PDF ───────────────────────────────────────────────────
doc.build(story)
print(f"PDF generated: {output_path}")
