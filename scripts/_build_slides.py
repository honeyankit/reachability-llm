"""Generate FalsePositive_SupplyChain_Honey.pptx — the final project deck.

Run: python3 scripts/_build_slides.py
Output: reports/FalsePositive_SupplyChain_Honey.pptx

Design system:
  - White background throughout (course requirement).
  - Navy + ice-blue + terracotta accent palette.
  - Calibri for body, Calibri Light for headers.
  - Visual motif: a thin 0.06" navy bar on the left edge of every content slide.
"""
from __future__ import annotations

from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt


SLIDES_PATH = Path(__file__).resolve().parents[1] / "reports" / "FalsePositive_SupplyChain_Honey.pptx"
VIDEO_URL_PLACEHOLDER = "https://youtu.be/REPLACE-WITH-YOUR-VIDEO-URL"

# Palette
NAVY = RGBColor(0x1E, 0x27, 0x61)
ICE = RGBColor(0xCA, 0xDC, 0xFC)
TERRA = RGBColor(0xB8, 0x50, 0x42)
GREY = RGBColor(0x4A, 0x4A, 0x4A)
LIGHT_GREY = RGBColor(0xEA, 0xEA, 0xEA)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)


# ─── helpers ────────────────────────────────────────────────────────────────

def add_left_bar(slide, prs):
    """Decorative navy bar down the left edge."""
    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(0),
                                 Inches(0.06), prs.slide_height)
    bar.fill.solid(); bar.fill.fore_color.rgb = NAVY
    bar.line.fill.background()


def add_footer(slide, prs, page_num: int, total: int):
    tb = slide.shapes.add_textbox(Inches(0.4), prs.slide_height - Inches(0.4),
                                  prs.slide_width - Inches(0.8), Inches(0.3))
    tf = tb.text_frame
    tf.margin_left = tf.margin_right = Pt(0)
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.LEFT
    r = p.add_run()
    r.text = "Ankit Kumar Honey  |  CSCI E-222  |  Spring 2026"
    r.font.size = Pt(9); r.font.color.rgb = GREY; r.font.name = "Calibri"

    # right side: slide number
    tb2 = slide.shapes.add_textbox(prs.slide_width - Inches(1.0), prs.slide_height - Inches(0.4),
                                   Inches(0.8), Inches(0.3))
    p = tb2.text_frame.paragraphs[0]
    p.alignment = PP_ALIGN.RIGHT
    r = p.add_run(); r.text = f"{page_num} / {total}"
    r.font.size = Pt(9); r.font.color.rgb = GREY; r.font.name = "Calibri"


def add_title(slide, text: str, top: float = 0.45):
    tb = slide.shapes.add_textbox(Inches(0.5), Inches(top), Inches(12.3), Inches(0.7))
    tf = tb.text_frame; tf.margin_left = Pt(0)
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.LEFT
    r = p.add_run(); r.text = text
    r.font.size = Pt(30); r.font.bold = True
    r.font.color.rgb = NAVY; r.font.name = "Calibri"


def add_subtitle(slide, text: str, top: float = 1.05):
    tb = slide.shapes.add_textbox(Inches(0.5), Inches(top), Inches(12.3), Inches(0.4))
    tf = tb.text_frame; tf.margin_left = Pt(0)
    p = tf.paragraphs[0]; p.alignment = PP_ALIGN.LEFT
    r = p.add_run(); r.text = text
    r.font.size = Pt(14); r.font.italic = True
    r.font.color.rgb = TERRA; r.font.name = "Calibri"


def add_textbox(slide, left, top, width, height, *,
                font_size: int = 14, color: RGBColor = GREY, bold: bool = False,
                italic: bool = False, align: int = PP_ALIGN.LEFT, name: str = "Calibri"):
    """Returns the text_frame; caller adds runs."""
    tb = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = Pt(2); tf.margin_right = Pt(2)
    tf.margin_top = Pt(2); tf.margin_bottom = Pt(2)
    p = tf.paragraphs[0]; p.alignment = align
    r = p.add_run()
    r.font.size = Pt(font_size); r.font.color.rgb = color
    r.font.bold = bold; r.font.italic = italic; r.font.name = name
    return tf, r


def add_bullets(slide, left, top, width, height, items: list[str], *,
                size: int = 14, color: RGBColor = GREY):
    tb = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
    tf = tb.text_frame; tf.word_wrap = True
    tf.margin_left = Pt(2); tf.margin_right = Pt(2)
    for i, item in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = PP_ALIGN.LEFT
        p.space_after = Pt(6)
        r = p.add_run()
        r.text = "•  " + item
        r.font.size = Pt(size); r.font.color.rgb = color; r.font.name = "Calibri"
    return tf


def add_stat(slide, left, top, value: str, label: str, *, value_color: RGBColor = NAVY):
    tb = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(3.0), Inches(1.5))
    tf = tb.text_frame; tf.margin_left = Pt(0)
    p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
    r = p.add_run(); r.text = value
    r.font.size = Pt(48); r.font.bold = True
    r.font.color.rgb = value_color; r.font.name = "Calibri"
    p2 = tf.add_paragraph(); p2.alignment = PP_ALIGN.CENTER
    r2 = p2.add_run(); r2.text = label
    r2.font.size = Pt(11); r2.font.color.rgb = GREY; r2.font.name = "Calibri"


def add_callout_card(slide, left, top, width, height, *, fill: RGBColor = ICE,
                     border: RGBColor = NAVY):
    card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(left), Inches(top),
                                  Inches(width), Inches(height))
    card.fill.solid(); card.fill.fore_color.rgb = fill
    card.line.color.rgb = border; card.line.width = Pt(0.75)
    card.shadow.inherit = False
    return card


def add_code_box(slide, left, top, width, height, lines: list[str]):
    card = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(left), Inches(top),
                                  Inches(width), Inches(height))
    card.fill.solid(); card.fill.fore_color.rgb = RGBColor(0x21, 0x29, 0x5C)
    card.line.fill.background()
    tb = slide.shapes.add_textbox(Inches(left + 0.15), Inches(top + 0.1),
                                  Inches(width - 0.3), Inches(height - 0.2))
    tf = tb.text_frame; tf.word_wrap = True
    tf.margin_left = Pt(0); tf.margin_right = Pt(0)
    for i, line in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = PP_ALIGN.LEFT
        p.space_after = Pt(0)
        r = p.add_run(); r.text = line
        r.font.size = Pt(10); r.font.color.rgb = WHITE; r.font.name = "Consolas"


def add_table(slide, left, top, width, height, rows: list[list[str]], *,
              header_row: bool = True, emphasize_last: bool = False):
    tbl = slide.shapes.add_table(len(rows), len(rows[0]),
                                 Inches(left), Inches(top),
                                 Inches(width), Inches(height)).table
    for ri, row in enumerate(rows):
        for ci, val in enumerate(row):
            cell = tbl.cell(ri, ci)
            cell.text = ""
            cell.margin_left = Pt(8); cell.margin_right = Pt(8)
            cell.margin_top = Pt(4); cell.margin_bottom = Pt(4)
            tf = cell.text_frame
            p = tf.paragraphs[0]
            p.alignment = PP_ALIGN.LEFT if ci == 0 else PP_ALIGN.CENTER
            r = p.add_run(); r.text = val
            r.font.name = "Calibri"; r.font.size = Pt(13)
            if header_row and ri == 0:
                r.font.bold = True; r.font.color.rgb = WHITE
                cell.fill.solid(); cell.fill.fore_color.rgb = NAVY
            elif emphasize_last and ri == len(rows) - 1:
                r.font.bold = True; r.font.color.rgb = NAVY
                cell.fill.solid(); cell.fill.fore_color.rgb = ICE
            else:
                r.font.color.rgb = GREY
                cell.fill.solid()
                cell.fill.fore_color.rgb = WHITE if ri % 2 == 1 else LIGHT_GREY
    return tbl


# ─── slide builders ─────────────────────────────────────────────────────────

def slide_title(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])  # blank
    # Top navy band
    band = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(0),
                              prs.slide_width, Inches(2.6))
    band.fill.solid(); band.fill.fore_color.rgb = NAVY; band.line.fill.background()

    # Eyebrow
    tb = s.shapes.add_textbox(Inches(0.6), Inches(0.5), Inches(10), Inches(0.4))
    tf = tb.text_frame; tf.margin_left = Pt(0)
    p = tf.paragraphs[0]
    r = p.add_run(); r.text = "CSCI E-222  |  FINAL PROJECT  |  SPRING 2026"
    r.font.size = Pt(13); r.font.bold = True
    r.font.color.rgb = ICE; r.font.name = "Calibri"
    r.font.italic = False

    # Title
    tb = s.shapes.add_textbox(Inches(0.6), Inches(1.0), Inches(12.0), Inches(2.0))
    tf = tb.text_frame; tf.word_wrap = True; tf.margin_left = Pt(0)
    p = tf.paragraphs[0]
    r = p.add_run(); r.text = "Reducing Alert Fatigue"
    r.font.size = Pt(44); r.font.bold = True; r.font.color.rgb = WHITE; r.font.name = "Calibri"
    p2 = tf.add_paragraph()
    r = p2.add_run()
    r.text = "LLM-Based False Positive Detection in Software\nSupply Chain Security Vulnerability Alerts"
    r.font.size = Pt(20); r.font.color.rgb = ICE; r.font.italic = True; r.font.name = "Calibri"

    # Author block
    tb = s.shapes.add_textbox(Inches(0.6), Inches(3.0), Inches(12), Inches(0.6))
    tf = tb.text_frame; tf.margin_left = Pt(0)
    p = tf.paragraphs[0]
    r = p.add_run(); r.text = "Ankit Kumar Honey"
    r.font.size = Pt(22); r.font.bold = True; r.font.color.rgb = NAVY; r.font.name = "Calibri"

    tb = s.shapes.add_textbox(Inches(0.6), Inches(3.55), Inches(12), Inches(0.4))
    tf = tb.text_frame; tf.margin_left = Pt(0)
    p = tf.paragraphs[0]
    r = p.add_run(); r.text = "Harvard Extension School · Foundations of Large Language Models"
    r.font.size = Pt(14); r.font.color.rgb = GREY; r.font.italic = True; r.font.name = "Calibri"

    # Stat row
    add_stat(s, 0.5, 4.6, "10,000", "alerts evaluated")
    add_stat(s, 3.7, 4.6, "F1 = 0.995", "full pipeline (test)", value_color=TERRA)
    add_stat(s, 6.9, 4.6, "Recall = 0.99", "only 2 of 212 TPs missed")
    add_stat(s, 10.1, 4.6, "0 FP", "false alarms raised")


def slide_problem(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    add_left_bar(s, prs)
    add_title(s, "The problem — alert fatigue is the bottleneck")
    add_subtitle(s, "Same CVE. Same package. Same CVSS. Same EPSS. Different real-world risk.")

    add_bullets(s, 0.6, 1.7, 6.4, 3.5, [
        "Dependabot alone surfaces millions of CVE alerts per day across GitHub.",
        "A large fraction are technically valid but functionally irrelevant — the vulnerable function is never reached by the consuming application.",
        "Developers learn to ignore alerts. Real threats slip through.",
        "Pure severity (CVSS) and exploit probability (EPSS) cannot resolve this — they describe the CVE, not the application.",
        "Course parallel: identical structure to fake-news classification — true vs. misleading-in-context.",
    ])

    # Code comparison cards
    add_callout_card(s, 7.2, 1.7, 5.8, 2.0, fill=RGBColor(0xEC, 0xF8, 0xEE),
                     border=RGBColor(0x4C, 0xAF, 0x50))
    add_textbox(s, 7.4, 1.8, 5.5, 0.3, font_size=11, bold=True,
                color=RGBColor(0x2E, 0x7D, 0x32))[1].text = "FALSE POSITIVE  —  unreachable"
    add_code_box(s, 7.4, 2.15, 5.5, 1.45, [
        "const _ = require('lodash');",
        "",
        "_.map(users, u =>",
        "    _.capitalize(u.name));",
    ])

    add_callout_card(s, 7.2, 3.85, 5.8, 2.0, fill=RGBColor(0xFD, 0xE7, 0xE7),
                     border=RGBColor(0xC6, 0x28, 0x28))
    add_textbox(s, 7.4, 3.95, 5.5, 0.3, font_size=11, bold=True,
                color=RGBColor(0xB7, 0x1C, 0x1C))[1].text = "TRUE POSITIVE  —  reachable + tainted"
    add_code_box(s, 7.4, 4.30, 5.5, 1.45, [
        "_.template(tpl, {",
        "    sourceURL: req.query.src",
        "})(data);",
        "",
    ])

    add_textbox(s, 0.6, 6.6, 12, 0.35, font_size=12, italic=True, color=TERRA)[1].text = \
        "Both pin lodash@4.17.20.  CVSS = 7.2.  EPSS = 0.0023.  Only reachability separates them."


def slide_solution_overview(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    add_left_bar(s, prs)
    add_title(s, "Solution — a four-stage classifier")
    add_subtitle(s, "Fuse rule baseline + RoBERTa + reachability into a single verdict")

    stages = [
        ("1", "Baselines", "EPSS-threshold rule\nTF-IDF + Logistic Reg.", "0.58 – 0.61 F1"),
        ("2", "RoBERTa", "Fine-tune roberta-base\non CVE descriptions", "AUC 0.83"),
        ("3", "Reachability", "Static call graph\n+ Flan-T5 reasoner\n+ CodeBERT+FAISS", "the core innovation"),
        ("4", "Combined", "Logistic Regression\non 775-d fused vector\n(768 + 5 + 2)", "F1 = 0.995"),
    ]
    for i, (num, name, desc, metric) in enumerate(stages):
        left = 0.6 + i * 3.15
        # circle with number
        circle = s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(left + 1.25), Inches(1.75),
                                    Inches(0.65), Inches(0.65))
        circle.fill.solid(); circle.fill.fore_color.rgb = NAVY if i < 3 else TERRA
        circle.line.fill.background()
        ctf = circle.text_frame; ctf.margin_top = Pt(0); ctf.margin_bottom = Pt(0)
        cp = ctf.paragraphs[0]; cp.alignment = PP_ALIGN.CENTER
        cr = cp.add_run(); cr.text = num
        cr.font.size = Pt(20); cr.font.bold = True; cr.font.color.rgb = WHITE; cr.font.name = "Calibri"

        # card
        add_callout_card(s, left, 2.6, 3.0, 3.4)
        add_textbox(s, left, 2.75, 3.0, 0.4, font_size=15, bold=True,
                    color=NAVY, align=PP_ALIGN.CENTER)[1].text = name
        # description
        tb = s.shapes.add_textbox(Inches(left + 0.2), Inches(3.25), Inches(2.6), Inches(2.0))
        tf = tb.text_frame; tf.word_wrap = True
        p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
        r = p.add_run(); r.text = desc
        r.font.size = Pt(11); r.font.color.rgb = GREY; r.font.name = "Calibri"
        # metric
        add_textbox(s, left, 5.45, 3.0, 0.4, font_size=12, bold=True,
                    color=TERRA, italic=True, align=PP_ALIGN.CENTER)[1].text = metric

    add_textbox(s, 0.6, 6.4, 12, 0.4, font_size=12, italic=True, color=GREY)[1].text = \
        "Each stage's output is concatenated into the next stage's input.  Only Stage 4 produces the final TP/FP verdict."


def slide_data(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    add_left_bar(s, prs)
    add_title(s, "Data — 10,000 real advisories")
    add_subtitle(s, "GitHub Advisory Database  ⨝  FIRST EPSS  ⨝  NVD CWE/CVSS")

    add_bullets(s, 0.6, 1.7, 6.5, 4.0, [
        "GitHub Advisory Database — OSV-Schema JSON, ~200K advisories, MIT-licensed.",
        "FIRST EPSS — daily CSV, exploitation probability per CVE.",
        "Joined on cve_id; merge is left-outer (missing EPSS → 0.001 tail).",
        "Class balancing: cap majority at 4× minority via uniform sampling.",
        "Stratified 80 / 10 / 10 train / val / test split, SEED = 42.",
        "Proxy label (EPSS + severity heuristic) — fully reproducible from src/reachability_llm/data/dataset.py.",
    ])

    # Right column: split breakdown
    add_callout_card(s, 7.6, 1.7, 5.4, 4.0)
    add_textbox(s, 7.8, 1.85, 5.0, 0.4, font_size=14, bold=True,
                color=NAVY)[1].text = "Final dataset composition"
    add_bullets(s, 7.8, 2.30, 5.0, 3.0, [
        "Advisories scanned:   15,000",
        "After build_dataset:  10,000",
        "TRUE_POSITIVE share:  21.14%",
        "FALSE_POSITIVE share: 78.86%",
        "Train / val / test:   7,999 / 999 / 1,002",
    ], size=12, color=GREY)

    add_textbox(s, 0.6, 6.4, 12, 0.4, font_size=11, italic=True, color=TERRA)[1].text = \
        "OSV-Schema 1.4: aliases is a list of strings, not a list of {\"value\":\"CVE-…\"} dicts. Four regression tests in tests/test_loaders.py."


def slide_stage1_baselines(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    add_left_bar(s, prs)
    add_title(s, "Stage 1 — baselines establish the floor")
    add_subtitle(s, "What you get with no LLM at all")

    add_callout_card(s, 0.6, 1.7, 6.0, 4.5)
    add_textbox(s, 0.85, 1.9, 5.5, 0.4, font_size=16, bold=True,
                color=NAVY)[1].text = "EPSS rule baseline"
    add_textbox(s, 0.85, 2.4, 5.5, 0.3, font_size=11, italic=True,
                color=TERRA)[1].text = "≈ the heuristic Dependabot operates today"
    add_code_box(s, 0.85, 2.8, 5.5, 0.7,
                 ["return (df['epss'] >= 0.01).astype(int)"])
    add_textbox(s, 0.85, 3.7, 5.5, 0.5, font_size=14,
                color=GREY)[1].text = "F1     = 0.580"
    add_textbox(s, 0.85, 4.15, 5.5, 0.5, font_size=14,
                color=GREY)[1].text = "Precision = 0.617"
    add_textbox(s, 0.85, 4.55, 5.5, 0.5, font_size=14,
                color=GREY)[1].text = "Recall    = 0.547"
    add_textbox(s, 0.85, 5.05, 5.5, 0.5, font_size=14, bold=True,
                color=NAVY)[1].text = "ROC-AUC = 0.758"

    add_callout_card(s, 7.0, 1.7, 6.0, 4.5)
    add_textbox(s, 7.25, 1.9, 5.5, 0.4, font_size=16, bold=True,
                color=NAVY)[1].text = "TF-IDF  +  Logistic Regression"
    add_textbox(s, 7.25, 2.4, 5.5, 0.3, font_size=11, italic=True,
                color=TERRA)[1].text = "bag-of-words over the CVE description"
    add_code_box(s, 7.25, 2.8, 5.5, 0.7,
                 ["TfidfVectorizer(max_features=20000, ngram=(1,2))"])
    add_textbox(s, 7.25, 3.7, 5.5, 0.5, font_size=14,
                color=GREY)[1].text = "F1     = 0.607"
    add_textbox(s, 7.25, 4.15, 5.5, 0.5, font_size=14,
                color=GREY)[1].text = "Precision = 0.555"
    add_textbox(s, 7.25, 4.55, 5.5, 0.5, font_size=14,
                color=GREY)[1].text = "Recall    = 0.670"
    add_textbox(s, 7.25, 5.05, 5.5, 0.5, font_size=14, bold=True,
                color=NAVY)[1].text = "ROC-AUC = 0.851"

    add_textbox(s, 0.6, 6.4, 12, 0.4, font_size=12, italic=True, color=GREY)[1].text = \
        "Both baselines hover around 0.6 F1 — they capture surface signal but cannot see the call graph."


def slide_stage2_roberta(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    add_left_bar(s, prs)
    add_title(s, "Stage 2 — fine-tune RoBERTa on CVE descriptions")
    add_subtitle(s, "roberta-base · 3 epochs · 1,500 steps · ~95 s on A100")

    add_bullets(s, 0.6, 1.7, 6.5, 4.0, [
        "Architecture: roberta-base (110M params, 768-d hidden) + sequence-classification head, 2 labels.",
        "Hyperparameters: batch=16, lr=2e-5, weight-decay=0.01, warmup-ratio=0.1, fp16=True on CUDA.",
        "load_best_model_at_end=True, metric_for_best_model='f1'.",
        "Validation F1 climbs 0.497 → 0.515 → 0.583 across 3 epochs.",
        "Training loss 0.43 → 0.30; model still improving — would gain from longer training.",
        "Extract 768-d [CLS] embedding post-train for Stage-4 fusion.",
    ])

    # Mini-table of epoch metrics
    add_table(s, 7.3, 1.7, 5.7, 2.0, [
        ["Epoch", "Train loss", "Val F1", "Val AUC"],
        ["1", "0.435", "0.497", "0.794"],
        ["2", "0.331", "0.515", "0.830"],
        ["3", "0.300", "0.583", "0.839"],
    ])

    add_callout_card(s, 7.3, 4.0, 5.7, 2.0, fill=ICE)
    add_textbox(s, 7.55, 4.2, 5.3, 0.4, font_size=15, bold=True,
                color=NAVY)[1].text = "Test-set verdict"
    add_textbox(s, 7.55, 4.6, 5.3, 0.4, font_size=13,
                color=GREY)[1].text = "F1 = 0.593  |  Precision = 0.578"
    add_textbox(s, 7.55, 4.95, 5.3, 0.4, font_size=13,
                color=GREY)[1].text = "Recall = 0.608  |  AUC = 0.828"
    add_textbox(s, 7.55, 5.4, 5.3, 0.5, font_size=11, italic=True,
                color=TERRA)[1].text = "RoBERTa alone beats EPSS rule on AUC,\nbut F1 is stuck in the noisy middle band."


def slide_stage3_reachability(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    add_left_bar(s, prs)
    add_title(s, "Stage 3 — the core innovation: reachability")
    add_subtitle(s, "Static call graph + Flan-T5 reasoner + CodeBERT/FAISS fallback")

    # 3-column layout
    layers = [
        ("Static layer", "NetworkX + AST",
         ["Python: ast.NodeVisitor resolves import aliases.",
          "JavaScript: regex over require/import; strips comments.",
          "Forward search from entry-points to vulnerable symbol.",
          "Up to 5 paths, max length 12."]),
        ("Semantic layer", "google/flan-t5-large",
         ["Prompt: CVE + symbol + static verdict + path code.",
          "Outputs YES/NO + one-sentence rationale.",
          "Calibrates confidence by static / LLM agreement.",
          "Rule-based fallback if transformers unavailable."]),
        ("Scale layer", "CodeBERT + FAISS",
         ["For 1M-LOC monorepos where static graph fails.",
          "Chunk to ~25-line windows; MiniLM-L6 embeddings.",
          "FAISS-IP index; top-k chunks fed to reasoner.",
          "Validated retrieval: VULN sim 0.46 vs SAFE sim 0.13."]),
    ]
    for i, (header, sub, points) in enumerate(layers):
        left = 0.5 + i * 4.3
        add_callout_card(s, left, 1.65, 4.1, 4.3)
        add_textbox(s, left + 0.15, 1.8, 3.8, 0.4, font_size=15, bold=True,
                    color=NAVY)[1].text = header
        add_textbox(s, left + 0.15, 2.2, 3.8, 0.35, font_size=10, italic=True,
                    color=TERRA, name="Consolas")[1].text = sub
        add_bullets(s, left + 0.15, 2.65, 3.8, 3.2, points, size=11)

    add_textbox(s, 0.6, 6.4, 12, 0.4, font_size=12, italic=True, color=GREY)[1].text = \
        "The static layer is deterministic and reliable. The LLM is the contextualiser — and the weakest link (see §11)."


def slide_lodash_example(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    add_left_bar(s, prs)
    add_title(s, "Worked example — CVE-2021-23337 (lodash)")
    add_subtitle(s, "Two synthetic apps, both pin lodash@4.17.20")

    # SAFE
    add_callout_card(s, 0.6, 1.7, 6.0, 4.5, fill=RGBColor(0xEC, 0xF8, 0xEE),
                     border=RGBColor(0x4C, 0xAF, 0x50))
    add_textbox(s, 0.85, 1.85, 5.5, 0.4, font_size=16, bold=True,
                color=RGBColor(0x2E, 0x7D, 0x32))[1].text = "SAFE app"
    add_code_box(s, 0.85, 2.3, 5.5, 1.0, [
        "users.map(u =>",
        "    _.capitalize(u.name));",
        "_.groupBy(result, 'dept');",
    ])
    add_textbox(s, 0.85, 3.45, 5.5, 0.3, font_size=12, bold=True,
                color=NAVY)[1].text = "Static call graph"
    add_textbox(s, 0.85, 3.75, 5.5, 0.4, font_size=12,
                color=GREY)[1].text = "17 nodes, 16 edges"
    add_textbox(s, 0.85, 4.10, 5.5, 0.4, font_size=12, color=GREY,
                name="Consolas")[1].text = "_.template NOT in graph"
    add_textbox(s, 0.85, 4.65, 5.5, 0.3, font_size=12, bold=True,
                color=NAVY)[1].text = "Flan-T5 verdict"
    add_textbox(s, 0.85, 4.95, 5.5, 0.4, font_size=14, bold=True,
                color=RGBColor(0x2E, 0x7D, 0x32))[1].text = "✓ FALSE_POSITIVE  (conf 0.90)"
    add_textbox(s, 0.85, 5.5, 5.5, 0.4, font_size=11, italic=True,
                color=GREY)[1].text = "Correct"

    # VULN
    add_callout_card(s, 7.0, 1.7, 6.0, 4.5, fill=RGBColor(0xFD, 0xE7, 0xE7),
                     border=RGBColor(0xC6, 0x28, 0x28))
    add_textbox(s, 7.25, 1.85, 5.5, 0.4, font_size=16, bold=True,
                color=RGBColor(0xB7, 0x1C, 0x1C))[1].text = "VULN app"
    add_code_box(s, 7.25, 2.3, 5.5, 1.0, [
        "_.template(tpl, {",
        "  sourceURL: req.query.src",
        "})(data);",
    ])
    add_textbox(s, 7.25, 3.45, 5.5, 0.3, font_size=12, bold=True,
                color=NAVY)[1].text = "Static call graph"
    add_textbox(s, 7.25, 3.75, 5.5, 0.4, font_size=12,
                color=GREY)[1].text = "9 nodes, 8 edges  →  reachable=True"
    add_textbox(s, 7.25, 4.10, 5.5, 0.4, font_size=12, color=GREY,
                name="Consolas")[1].text = "module → _.template  ✓"
    add_textbox(s, 7.25, 4.65, 5.5, 0.3, font_size=12, bold=True,
                color=NAVY)[1].text = "Flan-T5 verdict"
    add_textbox(s, 7.25, 4.95, 5.5, 0.4, font_size=14, bold=True,
                color=RGBColor(0xC6, 0x28, 0x28))[1].text = "✗ FALSE_POSITIVE  (conf 0.80)"
    add_textbox(s, 7.25, 5.5, 5.5, 0.4, font_size=11, italic=True,
                color=GREY)[1].text = "Wrong! Static layer correct, LLM fails."

    add_textbox(s, 0.6, 6.4, 12, 0.4, font_size=12, italic=True, color=TERRA)[1].text = \
        "The static call graph nails both apps. Flan-T5-large is below the capability threshold for taint reasoning — honest finding."


def slide_stage4_fusion(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    add_left_bar(s, prs)
    add_title(s, "Stage 4 — fuse everything into 775-d")
    add_subtitle(s, "768 RoBERTa [CLS]  +  5 structured  +  2 reachability  →  Logistic Regression")

    # Diagram boxes
    add_callout_card(s, 0.7, 2.0, 3.4, 2.0, fill=ICE)
    add_textbox(s, 0.85, 2.15, 3.1, 0.4, font_size=15, bold=True,
                color=NAVY, align=PP_ALIGN.CENTER)[1].text = "RoBERTa [CLS]"
    add_textbox(s, 0.85, 2.55, 3.1, 0.4, font_size=30, bold=True,
                color=NAVY, align=PP_ALIGN.CENTER)[1].text = "768"
    add_textbox(s, 0.85, 3.25, 3.1, 0.4, font_size=11, italic=True,
                color=GREY, align=PP_ALIGN.CENTER)[1].text = "Stage-2 embeddings"

    add_callout_card(s, 4.5, 2.0, 3.4, 2.0, fill=ICE)
    add_textbox(s, 4.65, 2.15, 3.1, 0.4, font_size=15, bold=True,
                color=NAVY, align=PP_ALIGN.CENTER)[1].text = "Structured"
    add_textbox(s, 4.65, 2.55, 3.1, 0.4, font_size=30, bold=True,
                color=NAVY, align=PP_ALIGN.CENTER)[1].text = "5"
    add_textbox(s, 4.65, 3.25, 3.1, 0.4, font_size=10, italic=True,
                color=GREY, align=PP_ALIGN.CENTER)[1].text = "CVSS, EPSS, age, fix, ecosystem"

    add_callout_card(s, 8.3, 2.0, 3.4, 2.0, fill=RGBColor(0xFD, 0xE7, 0xE7),
                     border=TERRA)
    add_textbox(s, 8.45, 2.15, 3.1, 0.4, font_size=15, bold=True,
                color=TERRA, align=PP_ALIGN.CENTER)[1].text = "Reachability"
    add_textbox(s, 8.45, 2.55, 3.1, 0.4, font_size=30, bold=True,
                color=TERRA, align=PP_ALIGN.CENTER)[1].text = "2"
    add_textbox(s, 8.45, 3.25, 3.1, 0.4, font_size=11, italic=True,
                color=GREY, align=PP_ALIGN.CENTER)[1].text = "static + LLM reachable"

    # Arrows to head
    for x in (2.4, 6.2, 10.0):
        ar = s.shapes.add_shape(MSO_SHAPE.DOWN_ARROW, Inches(x - 0.15), Inches(4.1),
                                Inches(0.3), Inches(0.5))
        ar.fill.solid(); ar.fill.fore_color.rgb = NAVY; ar.line.fill.background()

    # Head
    add_callout_card(s, 2.5, 4.75, 7.4, 1.2, fill=NAVY, border=NAVY)
    add_textbox(s, 2.5, 4.9, 7.4, 0.5, font_size=22, bold=True,
                color=WHITE, align=PP_ALIGN.CENTER)[1].text = "Class-balanced Logistic Regression"
    add_textbox(s, 2.5, 5.40, 7.4, 0.4, font_size=12, italic=True,
                color=ICE, align=PP_ALIGN.CENTER)[1].text = "775 features → P(TRUE_POSITIVE)"

    add_textbox(s, 0.6, 6.25, 12, 0.5, font_size=12, italic=True, color=TERRA)[1].text = \
        "Note: reachability features for the 10K training set are synthesised from labels with 15% noise (cell 6) — see Limitations."


def slide_results_table(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    add_left_bar(s, prs)
    add_title(s, "Results — 1,002-alert held-out test set")
    add_subtitle(s, "Each stage's marginal contribution to F1")

    add_table(s, 0.6, 1.7, 12.4, 3.5, [
        ["Model", "F1", "Precision", "Recall", "ROC-AUC"],
        ["EPSS-threshold rule (≥ 0.01)", "0.580", "0.617", "0.547", "0.758"],
        ["TF-IDF + Logistic Regression", "0.607", "0.555", "0.670", "0.851"],
        ["RoBERTa fine-tune (3 epochs)", "0.593", "0.578", "0.608", "0.828"],
        ["Full pipeline (775-d fusion)", "0.995", "1.000", "0.991", "1.000"],
    ], emphasize_last=True)

    # Big stat callout
    add_callout_card(s, 0.6, 5.4, 6.0, 1.5)
    add_textbox(s, 0.6, 5.55, 6.0, 0.4, font_size=14, bold=True,
                color=NAVY, align=PP_ALIGN.CENTER)[1].text = "F1 lift over RoBERTa alone"
    add_textbox(s, 0.6, 5.95, 6.0, 0.6, font_size=32, bold=True,
                color=TERRA, align=PP_ALIGN.CENTER)[1].text = "+0.40 F1"

    add_callout_card(s, 7.0, 5.4, 6.0, 1.5)
    add_textbox(s, 7.0, 5.55, 6.0, 0.4, font_size=14, bold=True,
                color=NAVY, align=PP_ALIGN.CENTER)[1].text = "False alarms eliminated"
    add_textbox(s, 7.0, 5.95, 6.0, 0.6, font_size=32, bold=True,
                color=TERRA, align=PP_ALIGN.CENTER)[1].text = "100%"


def slide_confusion(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    add_left_bar(s, prs)
    add_title(s, "Confusion matrix — full pipeline")
    add_subtitle(s, "2 misses on 212 true positives.  0 false alarms on 790 negatives.")

    # Matrix grid
    cells = [
        (3.5, 1.9, "", "", WHITE, GREY),
        (6.3, 1.9, "Predicted FP", "", LIGHT_GREY, NAVY),
        (9.1, 1.9, "Predicted TP", "", LIGHT_GREY, NAVY),
        (3.5, 3.0, "Actual FP", "n = 790", LIGHT_GREY, NAVY),
        (6.3, 3.0, "790", "true neg.", ICE, NAVY),
        (9.1, 3.0, "0", "false pos.", RGBColor(0xEC, 0xF8, 0xEE), RGBColor(0x2E, 0x7D, 0x32)),
        (3.5, 4.5, "Actual TP", "n = 212", LIGHT_GREY, NAVY),
        (6.3, 4.5, "2", "false neg.", RGBColor(0xFD, 0xE7, 0xE7), RGBColor(0xB7, 0x1C, 0x1C)),
        (9.1, 4.5, "210", "true pos.", ICE, NAVY),
    ]
    for x, y, big, small, fill, color in cells:
        box = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y),
                                 Inches(2.6), Inches(1.4))
        box.fill.solid(); box.fill.fore_color.rgb = fill
        box.line.color.rgb = GREY; box.line.width = Pt(0.5)
        if big:
            tb = s.shapes.add_textbox(Inches(x + 0.1), Inches(y + 0.15),
                                      Inches(2.4), Inches(0.7))
            tf = tb.text_frame; tf.margin_left = Pt(0)
            p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
            r = p.add_run(); r.text = big
            r.font.size = Pt(34) if big.isdigit() else Pt(14)
            r.font.bold = True; r.font.color.rgb = color; r.font.name = "Calibri"
            if small:
                tb2 = s.shapes.add_textbox(Inches(x + 0.1), Inches(y + 0.95),
                                           Inches(2.4), Inches(0.4))
                tf2 = tb2.text_frame; tf2.margin_left = Pt(0)
                p2 = tf2.paragraphs[0]; p2.alignment = PP_ALIGN.CENTER
                r = p2.add_run(); r.text = small
                r.font.size = Pt(11); r.font.italic = True
                r.font.color.rgb = GREY; r.font.name = "Calibri"

    add_textbox(s, 0.6, 6.3, 12, 0.5, font_size=12, italic=True, color=TERRA)[1].text = \
        "Recall = 0.991 — only two TPs missed.  Precision = 1.000 — zero false alarms.  F1 = 0.995."


def slide_strengths_limits(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    add_left_bar(s, prs)
    add_title(s, "What worked — and what did not")
    add_subtitle(s, "Honest accounting before we promise this in production")

    add_callout_card(s, 0.6, 1.7, 6.0, 4.5, fill=RGBColor(0xEC, 0xF8, 0xEE),
                     border=RGBColor(0x4C, 0xAF, 0x50))
    add_textbox(s, 0.85, 1.85, 5.5, 0.4, font_size=16, bold=True,
                color=RGBColor(0x2E, 0x7D, 0x32))[1].text = "✓ Worked"
    add_bullets(s, 0.85, 2.35, 5.5, 3.8, [
        "End-to-end pipeline reproducible from fresh Colab in ~5 min.",
        "Static call graph correctly distinguishes SAFE vs VULN lodash apps.",
        "0.42-point F1 lift from RoBERTa alone to full pipeline confirms reachability is the dominant signal.",
        "CodeBERT + FAISS scales: 3.5× sim gap between vulnerable and safe code.",
        "15 unit tests; CI-friendly module layout; pip-installable.",
    ], size=12)

    add_callout_card(s, 7.0, 1.7, 6.0, 4.5, fill=RGBColor(0xFD, 0xE7, 0xE7),
                     border=RGBColor(0xC6, 0x28, 0x28))
    add_textbox(s, 7.25, 1.85, 5.5, 0.4, font_size=16, bold=True,
                color=RGBColor(0xB7, 0x1C, 0x1C))[1].text = "✗ Did not work / limitations"
    add_bullets(s, 7.25, 2.35, 5.5, 3.8, [
        "Flan-T5-large returned wrong verdict on VULN lodash — taint reasoning is beyond its capability.",
        "0.995 F1 is an UPPER BOUND — reachability features for the 10K set are synthesised with 15% noise.",
        "Regex JS parser misses dynamic dispatch and eval (≈85-90% coverage).",
        "VULN_SYMBOL_MAP curated for 10 CVEs; production needs ~10K.",
        "Proxy labels correlate with EPSS by construction — inflates the EPSS-rule baseline ceiling.",
    ], size=12)


def slide_future_work(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    add_left_bar(s, prs)
    add_title(s, "Future work — concrete next steps")
    add_subtitle(s, "Each item below addresses a specific limitation from the previous slide")

    items = [
        ("Replace regex JS parser with tree-sitter",
         "AST-level accuracy. Closes the dynamic-dispatch and TS-generics gaps."),
        ("Swap Flan-T5-large for Qwen-2.5-Coder-7B or Llama-3-8B-Instruct",
         "Larger instruction-tuned models with few-shot taint examples. Direct fix for the VULN lodash miss."),
        ("Add lightweight static taint analysis",
         "Track sources (req.query, req.body, env) to sinks (exec, eval, template sourceURL). Removes the LLM dependency for the easy taint cases."),
        ("Build a real reachability oracle",
         "Sample 200-500 advisories with public patch commits → mine the vulnerable symbol → label reachability against a real consumer-repo corpus. Converts the 0.995 upper bound into a defensible production number."),
        ("Calibrated confidence model",
         "Return reachable / unreachable / unknown with thresholded probabilities, not a hard boolean. Surface only the uncertain band to human analysts."),
        ("LLM-extracted symbol map for 10K+ CVEs",
         "Prompt for vulnerable symbol from patch diff; cache; manual review of low-confidence extractions."),
    ]
    for i, (head, sub) in enumerate(items):
        row_top = 1.7 + i * 0.82
        # bullet circle
        circle = s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(0.65), Inches(row_top + 0.05),
                                    Inches(0.35), Inches(0.35))
        circle.fill.solid(); circle.fill.fore_color.rgb = NAVY
        circle.line.fill.background()
        ctf = circle.text_frame; ctf.margin_top = Pt(0); ctf.margin_bottom = Pt(0)
        cp = ctf.paragraphs[0]; cp.alignment = PP_ALIGN.CENTER
        cr = cp.add_run(); cr.text = str(i + 1)
        cr.font.size = Pt(13); cr.font.bold = True
        cr.font.color.rgb = WHITE; cr.font.name = "Calibri"
        # title
        add_textbox(s, 1.15, row_top, 12, 0.4, font_size=13, bold=True,
                    color=NAVY)[1].text = head
        # sub
        add_textbox(s, 1.15, row_top + 0.35, 12, 0.4, font_size=11, italic=True,
                    color=GREY)[1].text = sub


def slide_reproducibility(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    add_left_bar(s, prs)
    add_title(s, "Reproducibility — clone, run, get the same numbers")
    add_subtitle(s, "All code public.  All datasets public.  All seeds fixed.")

    add_textbox(s, 0.6, 1.7, 12, 0.4, font_size=13, bold=True,
                color=NAVY)[1].text = "Option A — Google Colab (recommended)"
    add_code_box(s, 0.6, 2.15, 12.4, 0.95, [
        "1. Open notebooks/FalsePositive_SupplyChain_Honey.ipynb via the GitHub badge",
        "2. Runtime → Change runtime type → A100 GPU",
        "3. Runtime → Run all  (≈ 5 min in synthetic mode, ≈ 25 min in real mode on A100)",
    ])

    add_textbox(s, 0.6, 3.3, 12, 0.4, font_size=13, bold=True,
                color=NAVY)[1].text = "Option B — local"
    add_code_box(s, 0.6, 3.75, 12.4, 1.2, [
        "git clone https://github.com/honeyankit/reachability-llm",
        "cd reachability-llm",
        "python -m venv .venv && source .venv/bin/activate",
        "pip install -r requirements.txt",
        "pytest -q                          # 15 tests, ~3 seconds",
    ])

    add_textbox(s, 0.6, 5.2, 12, 0.4, font_size=13, bold=True,
                color=NAVY)[1].text = "Datasets"
    add_bullets(s, 0.6, 5.55, 12.5, 1.0, [
        "github/advisory-database  —  shallow-clone (~400 MB), auto-downloaded on first run",
        "FIRST EPSS  —  daily CSV, auto-downloaded; cached to Drive in Colab",
    ], size=12)


def slide_video(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    # Match template style: title centered + URL
    band = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(0),
                              prs.slide_width, prs.slide_height)
    band.fill.solid(); band.fill.fore_color.rgb = NAVY; band.line.fill.background()

    tb = s.shapes.add_textbox(Inches(0.5), Inches(2.0), Inches(12.3), Inches(1.0))
    tf = tb.text_frame; tf.margin_left = Pt(0)
    p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
    r = p.add_run(); r.text = "Video Presentation"
    r.font.size = Pt(44); r.font.bold = True; r.font.color.rgb = WHITE; r.font.name = "Calibri"

    tb = s.shapes.add_textbox(Inches(0.5), Inches(3.2), Inches(12.3), Inches(0.6))
    tf = tb.text_frame; tf.margin_left = Pt(0)
    p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
    r = p.add_run(); r.text = "Watch the 10-minute walkthrough"
    r.font.size = Pt(20); r.font.color.rgb = ICE; r.font.italic = True; r.font.name = "Calibri"

    # URL card
    card = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(2.5), Inches(4.3),
                              Inches(8.3), Inches(1.2))
    card.fill.solid(); card.fill.fore_color.rgb = WHITE; card.line.color.rgb = ICE
    card.line.width = Pt(1.5)

    tb = s.shapes.add_textbox(Inches(2.5), Inches(4.50), Inches(8.3), Inches(0.5))
    tf = tb.text_frame; tf.margin_left = Pt(0)
    p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
    r = p.add_run(); r.text = "Video presentation:"
    r.font.size = Pt(14); r.font.color.rgb = GREY; r.font.name = "Calibri"

    tb = s.shapes.add_textbox(Inches(2.5), Inches(4.85), Inches(8.3), Inches(0.55))
    tf = tb.text_frame; tf.margin_left = Pt(0)
    p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
    r = p.add_run(); r.text = VIDEO_URL_PLACEHOLDER
    r.font.size = Pt(16); r.font.bold = True; r.font.color.rgb = NAVY; r.font.name = "Consolas"

    # Footer credit
    tb = s.shapes.add_textbox(Inches(0.5), Inches(6.5), Inches(12.3), Inches(0.4))
    tf = tb.text_frame
    p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
    r = p.add_run(); r.text = "@AnkitKumarHoney  |  CSCI E-222  |  Spring 2026"
    r.font.size = Pt(11); r.font.color.rgb = ICE; r.font.italic = True; r.font.name = "Calibri"


# ─── main ───────────────────────────────────────────────────────────────────

BUILDERS = [
    slide_title,                 # 1
    slide_problem,               # 2
    slide_solution_overview,     # 3
    slide_data,                  # 4
    slide_stage1_baselines,      # 5
    slide_stage2_roberta,        # 6
    slide_stage3_reachability,   # 7
    slide_lodash_example,        # 8
    slide_stage4_fusion,         # 9
    slide_results_table,         # 10
    slide_confusion,             # 11
    slide_strengths_limits,      # 12
    slide_future_work,           # 13
    slide_reproducibility,       # 14
    slide_video,                 # 15
]


def main() -> None:
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)

    total = len(BUILDERS)
    for i, builder in enumerate(BUILDERS, 1):
        builder(prs)
        # Add footer to non-title, non-video slides
        if i not in (1, total):
            add_footer(prs.slides[-1], prs, page_num=i, total=total)

    SLIDES_PATH.parent.mkdir(parents=True, exist_ok=True)
    prs.save(SLIDES_PATH)
    print(f"wrote {SLIDES_PATH}  ({total} slides)")


if __name__ == "__main__":
    main()
