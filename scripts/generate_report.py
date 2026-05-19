#!/usr/bin/env python3
"""
BurnRate Report Generator
=========================
Reads docs/findings.md → generates a professional A4 PDF report.

Usage (from BurnRate root):
    python scripts/generate_report.py
    python scripts/generate_report.py --version 1.1
    python scripts/generate_report.py --output /path/to/report.pdf

Re-run whenever findings.md is updated to produce a new version.
Requirements: pip install reportlab pypdf
"""

import re
import sys
import argparse
from datetime import datetime
from pathlib import Path

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.colors import HexColor, white, black
    from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        PageBreak, HRFlowable, KeepTogether
    )
    from reportlab.pdfgen import canvas as rl_canvas
    from pypdf import PdfWriter, PdfReader
except ImportError as e:
    sys.exit(f"Missing dependency: {e}\nRun: pip install reportlab pypdf")

# ── Static config ─────────────────────────────────────────────────────────────
REPORT_TITLE    = "95–98%"
REPORT_SUBTITLE = "What My Claude Agent Sessions Actually Cost"
REPORT_TAGLINE  = ("Real token-burn data from agentic AI workflows.\n"
                   "Not estimates. Not vendor marketing. Ground-truth Anthropic API numbers.")
AUTHOR          = "Wilco de Tree"
WEBSITE         = "zerononsense.dev"
EMAIL           = "wilco.de.tree@a-insights.eu"

def C(h): return HexColor(h)

# Palette
BG       = C("#0A0C10")
WHITE    = C("#FFFFFF")
ACCENT   = C("#FF6542")
DARK     = C("#1C2128")
GRAY     = C("#656D76")
LGRAY    = C("#E8EAED")
ALT_ROW  = C("#F6F8FA")
HDARK    = C("#0D1117")
LBLUE    = C("#F0F2F4")

PAGE_W, PAGE_H = A4
MARGIN = 20 * mm
INNER_W = PAGE_W - 2 * MARGIN

# ── Static copy ───────────────────────────────────────────────────────────────
INTRO_TEXT = """\
The conventional wisdom about AI agent costs is roughly this: it’s expensive, context windows \
are the culprit, and you should probably optimize at some point. Vague, unactionable, and wrong \
in the specifics.

This report is the result of actually measuring. I built BurnRate — a token-burn observability \
tool — and ran it against real Cowork sessions and production pipeline data. No estimates, no \
calibration factors, no extrapolation from toy examples. Ground-truth numbers from the usage fields \
the Anthropic API embeds in every session.

What I found was worse than the conventional wisdom and more actionable."""

METHODOLOGY_TEXT = """\
Data sources: four Cowork JSONL session files containing exact per-turn Anthropic API usage \
fields, plus 33 days of Anthropic console CSV exports from a production n8n pipeline running \
Claude Haiku 4.5 daily.

The JSONL files contain exact per-turn counts: input_tokens, cache_creation_input_tokens, \
cache_read_input_tokens, output_tokens. No estimation required — these are the numbers \
Anthropic charges against.

Sessions measured: 186-turn session (4h 7m), 57-turn session (15m), 57-turn session (94m), \
124-turn session (21m). Total effective input across all four sessions: 26.3M tokens."""

ABOUT_TEXT = """\
Wilco de Tree is the founder of ZeroNonsense.dev, a Dutch AI advisory practice built around the \
principle that opinions should be earned through hands-on experiments. BurnRate is one of those \
experiments: a personal token-burn observability tool built to stop guessing and start measuring.

The findings in this report are from Phase 1 — four sessions of real data, not a model or a \
guess. More findings will follow as the dataset grows. Buyers of this report receive updates \
automatically as new data changes the picture."""

CTA_TEXT = "Questions, data, or disagreements: wilco.de.tree@a-insights.eu  ·  zerononsense.dev"

# ── Markdown helpers ──────────────────────────────────────────────────────────
def parse_md_table(lines):
    rows = []
    for line in lines:
        if re.match(r'\s*\|[-:\s|]+\|\s*$', line):
            continue
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        if any(cells):
            rows.append(cells)
    return rows

def strip_md(text):
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    text = re.sub(r'`(.+?)`', r'\1', text)
    return text.strip()

def md_to_para(text, style):
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'\*(.+?)\*', r'<i>\1</i>', text)
    text = re.sub(r'`(.+?)`', r'<font name="Courier" size="9">\1</font>', text)
    return Paragraph(text, style)

def parse_blocks(text):
    blocks = []
    lines = text.split('\n')
    i = 0
    while i < len(lines):
        line = lines[i]
        if re.match(r'^-{3,}$', line.strip()):
            i += 1
            continue
        if '|' in line and re.match(r'\s*\|', line):
            tbl = []
            while i < len(lines) and '|' in lines[i]:
                tbl.append(lines[i])
                i += 1
            rows = parse_md_table(tbl)
            if rows:
                blocks.append({'type': 'table', 'rows': rows})
            continue
        if re.match(r'\s*[-*]\s+', line):
            content = re.sub(r'^\s*[-*]\s+', '', line)
            blocks.append({'type': 'bullet', 'content': content})
            i += 1
            continue
        if re.match(r'\s*\d+\.\s+', line):
            content = re.sub(r'^\s*\d+\.\s+', '', line)
            blocks.append({'type': 'bullet', 'content': content})
            i += 1
            continue
        if line.strip() and not line.strip().startswith('#'):
            para_lines = []
            while i < len(lines) and lines[i].strip() and not lines[i].strip().startswith('#'):
                if '|' in lines[i] or re.match(r'\s*[-*]\s+', lines[i]):
                    break
                para_lines.append(lines[i].strip())
                i += 1
            content = ' '.join(para_lines)
            if content:
                blocks.append({'type': 'para', 'content': content})
            continue
        i += 1
    return blocks

def parse_findings(md_text):
    """Parse findings.md into structured sections dict."""
    sections = re.split(r'^(#{1,3} .+)$', md_text, flags=re.MULTILINE)
    result = {'findings': [], 'mitigation': None, 'open_questions': None}
    i = 0
    while i < len(sections):
        chunk = sections[i].strip()
        if not chunk:
            i += 1
            continue
        if chunk.startswith('#'):
            title = re.sub(r'^#+\s*', '', chunk)
            content = sections[i + 1] if i + 1 < len(sections) else ''
            blocks = parse_blocks(content)
            if re.match(r'Finding \d+', title, re.IGNORECASE):
                result['findings'].append({'title': title, 'blocks': blocks})
            elif 'Mitigation' in title:
                result['mitigation'] = {'title': title, 'blocks': blocks}
            elif 'Open Question' in title:
                result['open_questions'] = {'title': title, 'blocks': blocks}
            i += 2
        else:
            i += 1
    return result

# ── Styles ────────────────────────────────────────────────────────────────────
def make_styles():
    def S(name, **kw):
        return ParagraphStyle(name, **kw)
    base = dict(fontName='Helvetica', fontSize=10, leading=16, textColor=DARK, spaceAfter=6)
    return {
        'body':    S('Body', **base),
        'justify': S('Justify', **base, alignment=TA_JUSTIFY),
        'h1':      S('H1', fontName='Helvetica-Bold', fontSize=22, leading=28,
                      textColor=HDARK, spaceAfter=4, spaceBefore=16),
        'h2':      S('H2', fontName='Helvetica-Bold', fontSize=13, leading=18,
                      textColor=HDARK, spaceAfter=4, spaceBefore=12),
        'fnum':    S('FNum', fontName='Helvetica-Bold', fontSize=10, leading=14,
                      textColor=ACCENT, spaceAfter=2, spaceBefore=16),
        'ftitle':  S('FTitle', fontName='Helvetica-Bold', fontSize=17, leading=24,
                      textColor=HDARK, spaceAfter=6),
        'action':  S('Action', fontName='Helvetica-Bold', fontSize=10, leading=15,
                      textColor=ACCENT, spaceAfter=4, spaceBefore=6),
        'bullet':  S('Bullet', fontName='Helvetica', fontSize=10, leading=15,
                      textColor=DARK, spaceAfter=3, leftIndent=14),
        'small':   S('Small', fontName='Helvetica', fontSize=8, leading=12, textColor=GRAY),
        'about':   S('About', **base, alignment=TA_JUSTIFY),
        'cta':     S('CTA', fontName='Helvetica-Bold', fontSize=10, leading=16,
                      textColor=ACCENT, alignment=TA_CENTER),
        'qnum':    S('QNum', fontName='Helvetica-Bold', fontSize=10, leading=14,
                      textColor=GRAY, spaceAfter=2, spaceBefore=10),
        'th':      S('TH', fontName='Helvetica-Bold', fontSize=9, leading=13, textColor=HDARK),
        'td':      S('TD', fontName='Helvetica', fontSize=9, leading=13, textColor=DARK),
    }

# ── Cover page ────────────────────────────────────────────────────────────────
def build_cover(output_path, version, date_str):
    c = rl_canvas.Canvas(str(output_path), pagesize=A4)
    w, h = A4
    m = MARGIN

    c.setFillColor(BG)
    c.rect(0, 0, w, h, fill=1, stroke=0)

    # Header bar
    c.setFont('Helvetica-Bold', 9)
    c.setFillColor(GRAY)
    c.drawString(m, h - m - 2*mm, 'BURNRATE')
    c.setFont('Helvetica', 9)
    c.drawRightString(w - m, h - m - 2*mm, 'zerononsense.dev')
    c.setStrokeColor(C("#1E2329"))
    c.setLineWidth(0.5)
    c.line(m, h - m - 6*mm, w - m, h - m - 6*mm)

    # Big number
    c.setFont('Helvetica-Bold', 108)
    c.setFillColor(WHITE)
    c.drawCentredString(w / 2, h * 0.52, REPORT_TITLE)

    # Subtitle
    c.setFont('Helvetica-Bold', 20)
    c.setFillColor(ACCENT)
    c.drawCentredString(w / 2, h * 0.455, REPORT_SUBTITLE)

    # Divider
    c.setStrokeColor(ACCENT)
    c.setLineWidth(1.5)
    c.line(w / 2 - 40*mm, h * 0.42, w / 2 + 40*mm, h * 0.42)

    # Tagline
    c.setFont('Helvetica', 11)
    c.setFillColor(C("#9AA0A6"))
    for idx, line in enumerate(REPORT_TAGLINE.split('\n')):
        c.drawCentredString(w / 2, h * 0.385 - idx * 16, line)

    # Bottom meta
    c.setStrokeColor(C("#1E2329"))
    c.setLineWidth(0.5)
    c.line(m, m + 28*mm, w - m, m + 28*mm)
    c.setFont('Helvetica', 9)
    c.setFillColor(GRAY)
    c.drawString(m, m + 20*mm, f'By {AUTHOR}')
    c.drawCentredString(w / 2, m + 20*mm, f'v{version}  ·  {date_str}')
    c.drawRightString(w - m, m + 20*mm, WEBSITE)

    # Accent bottom strip
    c.setFillColor(ACCENT)
    c.rect(0, 0, w, 3.5, fill=1, stroke=0)

    c.save()

# ── Footer ────────────────────────────────────────────────────────────────────
def later_pages(canv, doc):
    w, h = A4
    canv.saveState()
    canv.setStrokeColor(LGRAY)
    canv.setLineWidth(0.5)
    canv.line(MARGIN, 14*mm, w - MARGIN, 14*mm)
    canv.setFont('Helvetica', 8)
    canv.setFillColor(GRAY)
    canv.drawString(MARGIN, 10*mm, 'BurnRate · zerononsense.dev')
    canv.drawRightString(w - MARGIN, 10*mm, f'Page {doc.page}')
    canv.restoreState()

# ── Block renderer ────────────────────────────────────────────────────────────
def render_blocks(story, blocks, styles):
    for block in blocks:
        if block['type'] == 'para':
            content = block['content']
            is_action = (content.startswith('**Action:**') or
                         content.startswith('**Implication:**') or
                         'Action:' in content[:12])
            story.append(md_to_para(content, styles['action'] if is_action else styles['justify']))

        elif block['type'] == 'bullet':
            story.append(Paragraph(f'•  {strip_md(block["content"])}', styles['bullet']))

        elif block['type'] == 'table':
            rows = block['rows']
            if not rows:
                continue
            col_count = max(len(r) for r in rows)
            col_w = INNER_W / col_count
            table_data = []
            for r_idx, row in enumerate(rows):
                style = styles['th'] if r_idx == 0 else styles['td']
                # Pad short rows
                padded = row + [''] * (col_count - len(row))
                table_data.append([Paragraph(strip_md(cell), style) for cell in padded])

            ts = TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), LBLUE),
                ('LINEBELOW', (0, 0), (-1, 0), 0.5, LGRAY),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [WHITE, ALT_ROW]),
                ('GRID', (0, 0), (-1, -1), 0.25, LGRAY),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ])
            story.append(Spacer(1, 3*mm))
            story.append(Table(table_data, colWidths=[col_w] * col_count,
                               style=ts, hAlign='LEFT', repeatRows=1))
            story.append(Spacer(1, 3*mm))

# ── Content PDF ───────────────────────────────────────────────────────────────
def build_content(output_path, sections, version, date_str):
    doc = SimpleDocTemplate(
        str(output_path), pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN + 4*mm, bottomMargin=MARGIN,
        title=f'{REPORT_TITLE}: {REPORT_SUBTITLE}', author=AUTHOR,
    )
    styles = make_styles()
    story = []

    # Page: The Setup
    story.append(Paragraph('The Setup', styles['h1']))
    story.append(HRFlowable(width=INNER_W, thickness=0.5, color=LGRAY, spaceAfter=6))
    for para in INTRO_TEXT.strip().split('\n\n'):
        story.append(Paragraph(para.strip(), styles['justify']))
        story.append(Spacer(1, 2*mm))

    story.append(Spacer(1, 5*mm))
    story.append(Paragraph('How The Data Was Collected', styles['h2']))
    for para in METHODOLOGY_TEXT.strip().split('\n\n'):
        story.append(Paragraph(para.strip(), styles['justify']))
        story.append(Spacer(1, 2*mm))
    story.append(PageBreak())

    # Findings (dynamic — reads however many are in findings.md)
    for i, finding in enumerate(sections['findings']):
        num_label = f'Finding {i + 1}'
        title = re.sub(r'^Finding\s*\d+:\s*', '', finding['title'], flags=re.IGNORECASE).strip()
        story.append(Paragraph(num_label, styles['fnum']))
        story.append(Paragraph(title, styles['ftitle']))
        story.append(HRFlowable(width=INNER_W, thickness=0.5, color=LGRAY, spaceAfter=4))
        story.append(Spacer(1, 2*mm))
        render_blocks(story, finding['blocks'], styles)
        if i < len(sections['findings']) - 1:
            story.append(PageBreak())

    story.append(PageBreak())

    # Mitigation
    if sections.get('mitigation'):
        story.append(Paragraph('What To Do About It', styles['h1']))
        story.append(HRFlowable(width=INNER_W, thickness=0.5, color=LGRAY, spaceAfter=6))
        story.append(Spacer(1, 2*mm))
        render_blocks(story, sections['mitigation']['blocks'], styles)
        story.append(PageBreak())

    # Open questions
    if sections.get('open_questions'):
        story.append(Paragraph("What We're Still Measuring", styles['h1']))
        story.append(HRFlowable(width=INNER_W, thickness=0.5, color=LGRAY, spaceAfter=6))
        story.append(Paragraph(
            "Intellectual honesty requires flagging what the data doesn't yet answer. "
            "These are the three open questions the current sample size can't resolve.",
            styles['justify']))
        story.append(Spacer(1, 3*mm))
        q_num = 1
        for block in sections['open_questions']['blocks']:
            if block['type'] == 'para':
                content = block['content']
                if re.match(r'\*\*Why', content) or content.startswith('Possible'):
                    story.append(md_to_para(content, styles['small']))
                else:
                    story.append(Paragraph(f'Q{q_num}.', styles['qnum']))
                    story.append(md_to_para(content, styles['justify']))
                    q_num += 1
            else:
                render_blocks(story, [block], styles)
        story.append(PageBreak())

    # About
    story.append(Paragraph('About', styles['h1']))
    story.append(HRFlowable(width=INNER_W, thickness=0.5, color=LGRAY, spaceAfter=6))
    story.append(Spacer(1, 3*mm))
    for para in ABOUT_TEXT.strip().split('\n\n'):
        story.append(Paragraph(para.strip(), styles['about']))
        story.append(Spacer(1, 2*mm))
    story.append(Spacer(1, 8*mm))
    story.append(Paragraph(CTA_TEXT, styles['cta']))

    doc.build(story, onLaterPages=later_pages)

# ── Merge ─────────────────────────────────────────────────────────────────────
def merge_pdfs(cover_path, content_path, output_path):
    writer = PdfWriter()
    for path in [cover_path, content_path]:
        for page in PdfReader(str(path)).pages:
            writer.add_page(page)
    with open(str(output_path), 'wb') as f:
        writer.write(f)

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description='Generate BurnRate PDF report from findings.md')
    parser.add_argument('--version', default='1.0', help='Report version (default: 1.0)')
    parser.add_argument('--output', default=None, help='Output PDF path')
    args = parser.parse_args()

    root = Path(__file__).parent.parent
    findings_path = root / 'docs' / 'findings.md'
    reports_dir = root / 'reports'
    reports_dir.mkdir(exist_ok=True)

    version = args.version
    date_str = datetime.now().strftime('%B %Y')
    slug = f'burnrate_report_v{version.replace(".", "_")}.pdf'
    output_path = Path(args.output) if args.output else reports_dir / slug

    if not findings_path.exists():
        sys.exit(f"Not found: {findings_path}")

    md_text = findings_path.read_text(encoding='utf-8')
    sections = parse_findings(md_text)

    print(f"Parsed {len(sections['findings'])} finding(s) from findings.md")

    tmp_dir = Path("/tmp/burnrate_report_tmp")
    tmp_dir.mkdir(exist_ok=True)
    cover_pdf = tmp_dir / 'cover.pdf'
    content_pdf = tmp_dir / 'content.pdf'

    print("Building cover page...")
    build_cover(cover_pdf, version, date_str)

    print("Building content pages...")
    build_content(content_pdf, sections, version, date_str)

    print("Merging pages...")
    merge_pdfs(cover_pdf, content_pdf, output_path)

    # Cleanup tmp
    cover_pdf.unlink(missing_ok=True)
    content_pdf.unlink(missing_ok=True)
    try:
        tmp_dir.rmdir()
    except OSError:
        pass

    print(f"\nDone: {output_path.name}")
    print(f"  Findings: {len(sections['findings'])}")
    print(f"  Mitigation table: {'yes' if sections.get('mitigation') else 'no'}")
    print(f"  Open questions: {'yes' if sections.get('open_questions') else 'no'}")

if __name__ == '__main__':
    main()
