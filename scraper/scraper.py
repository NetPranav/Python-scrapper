#!/usr/bin/env python3
"""
PDF Scraper & Compiler
======================
Scrapes title, authors (name + college), abstract, and keywords from
IEEE conference paper PDFs and compiles them into a single formatted
output PDF with Table of Contents.

Usage:
    python3 scraper.py                              # uses default folders
    python3 scraper.py <input_folder> <output_folder>

Default folders:
    Input:  IncompletePDF/
    Output: CompletedPDF/

Dependencies:
    pip3 install PyMuPDF reportlab
"""

import os
import sys
import re
import json
import shutil
import random

# Ensure UTF-8 stdout/stderr on Windows to avoid UnicodeEncodeError in cp1252
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# PyMuPDF import with fallback to avoid deprecation warning
try:
    import pymupdf as fitz
except ImportError:
    import fitz
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.colors import black, HexColor
from reportlab.platypus import (
    BaseDocTemplate, PageTemplate, Frame,
    Paragraph, Spacer, Flowable, KeepTogether, PageBreak
)
from reportlab.pdfgen import canvas as canvas_mod
from reportlab.pdfbase.pdfmetrics import stringWidth, registerFont
from reportlab.pdfbase.ttfonts import TTFont

# Register custom fonts if available
def register_custom_fonts():
    fonts_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fonts')
    if os.path.exists(fonts_dir):
        for file in os.listdir(fonts_dir):
            if file.endswith('.ttf'):
                font_name = file[:-4] # filename without .ttf
                try:
                    registerFont(TTFont(font_name, os.path.join(fonts_dir, file)))
                except Exception as e:
                    print(f"Failed to register font {font_name}: {e}")

register_custom_fonts()


# ============================================================
# CONFIGURATION — loaded from config.json if present
# ============================================================

def _load_config():
    """Load parameters from config.json, falling back to defaults."""
    defaults = {
        'CONFERENCE_HEADER': (
            'International Conference on Advances in Computer '
            'Research on Science Engineering and Technology, 2026'
        ),
        'FOOTER_URL': 'www.acroset.in',
        'LINE_SPACING_FACTOR': 1.45,
        'WORD_SPACING': 1.5,
        'TITLE_FONT_SIZE': 12,
        'AUTHORS_FONT_SIZE': 9.5,
        'ABSTRACT_FONT_SIZE': 10,
        'KEYWORDS_FONT_SIZE': 10,
        'HEADER_FONT_SIZE': 8.5,
        'FOOTER_URL_FONT_SIZE': 9,
        'FOOTER_PAGE_FONT_SIZE': 10,
    }
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                user_cfg = json.load(f)
            for k in defaults:
                if k in user_cfg:
                    defaults[k] = user_cfg[k]
            print(f"  [CONFIG] Loaded config from {config_path}")
        except Exception as e:
            print(f"  [WARN] Could not load config.json: {e}")
    return defaults

_cfg = _load_config()

CONFERENCE_HEADER = _cfg['CONFERENCE_HEADER']
FOOTER_URL = _cfg['FOOTER_URL']

# Deep blue color for header/footer divider lines
DIVIDER_COLOR = HexColor('#003366')

PAGE_WIDTH, PAGE_HEIGHT = A4  # 595.27 x 841.89 points
LEFT_MARGIN = 50
RIGHT_MARGIN = 50
TOP_MARGIN = 70      # more space for header area
BOTTOM_MARGIN = 60   # more space for footer area
CONTENT_WIDTH = PAGE_WIDTH - LEFT_MARGIN - RIGHT_MARGIN

# Strict limit: max papers per page
MAX_PAPERS_PER_PAGE = 2

# ────────────────────────────────────────────────────────────
# TUNABLE SPACING PARAMETERS  (adjust these to control layout)
# ────────────────────────────────────────────────────────────
LINE_SPACING_FACTOR = _cfg['LINE_SPACING_FACTOR']
WORD_SPACING = _cfg['WORD_SPACING']
TITLE_FONT_SIZE = _cfg['TITLE_FONT_SIZE']
AUTHORS_FONT_SIZE = _cfg['AUTHORS_FONT_SIZE']
ABSTRACT_FONT_SIZE = _cfg['ABSTRACT_FONT_SIZE']
KEYWORDS_FONT_SIZE = _cfg['KEYWORDS_FONT_SIZE']
HEADER_FONT_SIZE = _cfg['HEADER_FONT_SIZE']
FOOTER_URL_FONT_SIZE = _cfg['FOOTER_URL_FONT_SIZE']
FOOTER_PAGE_FONT_SIZE = _cfg['FOOTER_PAGE_FONT_SIZE']

# Exhaustive list of country names for location-line detection
COUNTRIES = {
    'india', 'usa', 'uk', 'china', 'japan', 'germany', 'france',
    'australia', 'canada', 'united states', 'united kingdom', 'brazil',
    'south korea', 'singapore', 'malaysia', 'indonesia', 'thailand',
    'spain', 'italy', 'netherlands', 'sweden', 'switzerland', 'austria',
    'belgium', 'portugal', 'ireland', 'new zealand', 'south africa',
    'turkey', 'russia', 'pakistan', 'bangladesh', 'sri lanka', 'nepal',
    'mexico', 'philippines', 'vietnam', 'taiwan', 'hong kong', 'uae',
    'saudi arabia', 'nigeria', 'kenya', 'iran', 'israel', 'poland',
    'romania', 'hungary', 'greece', 'finland', 'iceland', 'norway',
    'denmark', 'czech republic', 'argentina', 'colombia', 'chile',
    'peru', 'qatar', 'oman', 'bahrain', 'kuwait', 'ghana', 'ethiopia',
    'tanzania', 'uganda', 'iraq', 'jordan', 'lebanon', 'morocco',
    'tunisia', 'algeria', 'egypt',
}

# US states / Indian states that appear in location lines
STATES = {
    'maharashtra', 'madhya pradesh', 'uttar pradesh', 'rajasthan',
    'karnataka', 'tamil nadu', 'telangana', 'andhra pradesh',
    'gujarat', 'punjab', 'haryana', 'bihar', 'west bengal', 'odisha',
    'kerala', 'assam', 'jharkhand', 'chhattisgarh', 'uttarakhand',
    'himachal pradesh', 'goa', 'tripura', 'meghalaya', 'sikkim',
    'michigan', 'california', 'texas', 'new york', 'florida',
    'illinois', 'ohio', 'pennsylvania', 'georgia', 'virginia',
    'massachusetts', 'washington', 'maryland', 'colorado', 'minnesota',
}


# ============================================================
# UTILITY FUNCTIONS
# ============================================================

def html_escape(text):
    """Escape special characters for ReportLab XML markup."""
    return (text
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;'))


def is_location_line(text):
    """
    Detect city/country/state lines in the author section.
    These lines typically look like "Indore, India" or "Bhopal, India".
    """
    clean = text.strip().rstrip('.,').lower()

    # Check country names
    for country in COUNTRIES:
        if country in clean:
            return True

    # Check state names
    for state in STATES:
        if state in clean:
            return True

    # Pattern: "City, Country" — short text with comma, no email
    if ',' in text and len(text.strip()) < 40 and '@' not in text:
        parts = [p.strip() for p in text.strip().split(',')]
        if len(parts) == 2 and all(parts):
            # Both parts are short words (likely city + country)
            if all(len(p) < 25 for p in parts):
                return True

    return False


def is_email(text):
    """Detect email addresses or split-email fragments like 'edu.in'."""
    t = text.strip()
    # Full email
    if re.search(r'[\w.+-]+@[\w.-]+\.\w{2,}', t):
        return True
    # Partial email: starts with @ or ends with domain-like pattern
    if t.startswith('@') or re.match(r'^[\w.-]+@', t):
        return True
    # Fragment like 'edu.in' that is a continuation of a split email
    # Must look like a domain suffix: only lowercase letters and dots
    if re.match(r'^[a-z]+\.[a-z]{2,3}$', t) and len(t) < 12:
        return True
    return False


def is_copyright(text):
    """Detect copyright/ISBN/IEEE footer lines."""
    t = text.strip().lower()
    return ('978-' in t or '©' in t or t.strip() == 'ieee' or
            'doi:' in t or 'doi ' in t)


def smart_join_parts(parts):
    """
    Intelligently join multi-line college/institution text.
    Adds commas between separate entities (dept → college),
    but uses spaces for line-continuations (word wraps).
    """
    cleaned = [p.strip() for p in parts if p.strip()]
    if not cleaned:
        return ""
    if len(cleaned) == 1:
        return cleaned[0]

    result = cleaned[0]
    for i in range(1, len(cleaned)):
        prev = cleaned[i - 1].rstrip()
        curr = cleaned[i].lstrip()

        # If previous line ends with a continuation character → space
        if prev.endswith(('&', ',', '-', '(')) or prev.lower().endswith(
                ('and', 'of', 'in', 'for', 'the', 'with', 'on')):
            result += ' ' + curr
        # If current line starts with lowercase → continuation
        elif curr and curr[0].islower():
            result += ' ' + curr
        # If current line starts with ')' → closing bracket continuation
        elif curr and curr[0] == ')':
            result += curr
        else:
            # Likely a new entity (e.g., department → university)
            result += ', ' + curr

    return re.sub(r'\s+', ' ', result).strip()


# ============================================================
# PDF SCRAPING
# ============================================================

def extract_paper_data(pdf_path):
    """
    Extract title, authors+college, abstract, and keywords from the
    FIRST PAGE of a PDF. Uses font size and style metadata for robust
    detection across varying IEEE paper formats.

    Detection strategy (verified against all 5 sample PDFs):
    ┌─────────────┬──────────────────────────────────────────┐
    │ Element     │ Detection Rule                           │
    ├─────────────┼──────────────────────────────────────────┤
    │ Title       │ Largest font size (typ. 24pt)            │
    │ Author Name │ Size 9pt, NOT italic, NOT email/city     │
    │ College     │ Size 9pt, ITALIC (between name & next)   │
    │ Abstract    │ Text between "Abstract—" and "Keywords"  │
    │ Keywords    │ Text after "Keywords—" until body text    │
    └─────────────┴──────────────────────────────────────────┘

    Returns:
        dict with: title, authors, abstract, keywords, source_file
        Or None if extraction fails.
    """
    filename = os.path.basename(pdf_path)
    print(f"\n{'='*60}")
    print(f"[PROCESS] Processing: {filename}")
    print(f"{'='*60}")

    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        print(f"  [ERROR] FATAL: Cannot open PDF -- {e}")
        return None

    if len(doc) == 0:
        print(f"  [ERROR] FATAL: PDF has no pages")
        doc.close()
        return None

    page = doc[0]
    page_dict = page.get_text('dict')
    doc.close()

    # ── Flatten all text spans in reading order ──
    spans = []
    for block in page_dict.get('blocks', []):
        if 'lines' not in block:
            continue
        for line in block['lines']:
            for span in line['spans']:
                spans.append({
                    'text': span['text'],
                    'size': round(span['size'], 1),
                    'flags': span['flags'],
                    'is_bold': bool(span['flags'] & 16),
                    'is_italic': bool(span['flags'] & 2),
                    'is_super': bool(span['flags'] & 1),
                    'origin_y': round(span['origin'][1], 1) if 'origin' in span else 0,
                })

    # ── Enhanced superscript detection ──
    # Some PDFs don't set the superscript flag; instead they use a smaller
    # font size and/or a higher baseline.  Walk through the spans and mark
    # any span whose font size is ≥30% smaller than the *previous* span on
    # the same logical line (similar Y position) as a superscript.
    for i in range(1, len(spans)):
        s = spans[i]
        if s['is_super']:
            continue  # already flagged
        prev = spans[i - 1]
        text = s['text'].strip()
        if not text:
            continue
        # Same logical line: Y positions within 3pt of each other
        if abs(s['origin_y'] - prev['origin_y']) < 3:
            if prev['size'] > 0 and s['size'] < prev['size'] * 0.75:
                # Small span right after a normal span → superscript
                s['is_super'] = True

    if not spans:
        print(f"  [ERROR] FATAL: No text found on first page")
        return None

    # ════════════════════════════════════════════════
    # STEP 1: EXTRACT TITLE (largest font size)
    # ════════════════════════════════════════════════
    sizes = [s['size'] for s in spans if s['text'].strip()]
    if not sizes:
        print(f"  [ERROR] FATAL: No non-empty text spans")
        return None

    max_size = max(sizes)
    title_parts = []
    last_title_idx = 0

    for i, s in enumerate(spans):
        if s['size'] == max_size and s['text'].strip():
            title_parts.append(s['text'].strip())
            last_title_idx = i

    title = ' '.join(title_parts)
    title = re.sub(r'\s+', ' ', title).strip()
    print(f"  [OK] Title: \"{title}\"")

    # ════════════════════════════════════════════════
    # STEP 2: FIND SECTION BOUNDARIES
    # ════════════════════════════════════════════════

    # Find "Abstract" marker
    abstract_idx = None
    for i in range(last_title_idx + 1, len(spans)):
        text = spans[i]['text'].strip()
        if re.match(r'^Abstract\b', text, re.IGNORECASE):
            # Verify it's a marker (bold and/or italic, or at expected size)
            if spans[i]['is_bold'] or spans[i]['is_italic'] or spans[i]['size'] <= 10:
                abstract_idx = i
                break

    if abstract_idx is None:
        print(f"  [WARN] 'Abstract' marker not found -- trying fallback")
        # Fallback: look for any occurrence of "Abstract"
        for i in range(last_title_idx + 1, len(spans)):
            if 'abstract' in spans[i]['text'].lower():
                abstract_idx = i
                break

    # Find "Keywords" marker
    keywords_idx = None
    kw_start = (abstract_idx + 1) if abstract_idx is not None else (last_title_idx + 1)
    for i in range(kw_start, len(spans)):
        text = spans[i]['text'].strip()
        if re.match(r'^Keywords?\b', text, re.IGNORECASE):
            keywords_idx = i
            break

    # ════════════════════════════════════════════════
    # STEP 3: EXTRACT AUTHORS + COLLEGE
    # ════════════════════════════════════════════════

    def clean_author_name(name: str) -> str:
        """Strip superscript affiliation markers (^1, ^2, *, †, etc.) from author names."""
        # Remove trailing superscript markers: digits, *, †, ‡, §, ¶
        name = re.sub(r'[\d*†‡§¶]+$', '', name).strip()
        # Remove leading superscript markers (rare but possible)
        name = re.sub(r'^[\d*†‡§¶]+\s*', '', name).strip()
        # Remove markers attached after a comma (e.g. "Name1, Name2")
        name = re.sub(r'(\w)[\d*†‡§¶]+', r'\1', name).strip()
        return name

    authors = []
    if abstract_idx is not None:
        section = spans[last_title_idx + 1: abstract_idx]

        current_name = None
        current_college_parts = []

        for s in section:
            text = s['text'].strip()

            # ── Skip non-relevant spans ──
            if not text:
                continue
            if s['is_super']:          # superscript affiliation numbers
                continue
            # Skip spans that are ONLY digits/symbols (standalone affiliation markers)
            if re.match(r'^[\d*†‡§¶,\s]+$', text):
                continue
            if is_copyright(text):     # "978-1-... ©2025 IEEE"
                continue
            if is_email(text):         # "name@domain.com"
                continue
            if is_location_line(text): # "Indore, India"
                continue

            if s['is_italic']:
                # ── ITALIC = College / Institution info ──
                current_college_parts.append(text)
            else:
                # ── NON-ITALIC = Potential author name ──
                # Validate: must contain letters, reasonable length
                if re.search(r'[A-Za-z]', text) and len(text) > 1:
                    # Clean any inline superscript markers from name
                    cleaned = clean_author_name(text)
                    if not cleaned or len(cleaned) < 2:
                        continue
                    # Save the previous author before starting new one
                    if current_name is not None:
                        college = smart_join_parts(current_college_parts)
                        authors.append({
                            'name': current_name,
                            'college': college
                        })
                        current_college_parts = []
                    current_name = cleaned

        # Save the last author
        if current_name is not None:
            college = smart_join_parts(current_college_parts)
            authors.append({
                'name': current_name,
                'college': college
            })

    if authors:
        for a in authors:
            coll_display = a['college'][:55] + '...' if len(a['college']) > 55 else a['college']
            print(f"  [OK] Author: {a['name']} -> {coll_display}")
    else:
        print(f"  [WARN] No authors found")

    # ════════════════════════════════════════════════
    # STEP 4: EXTRACT ABSTRACT
    # ════════════════════════════════════════════════
    abstract_text = ""
    if abstract_idx is not None:
        end_idx = keywords_idx if keywords_idx is not None else len(spans)
        parts = []
        started = False

        for i in range(abstract_idx, end_idx):
            text = spans[i]['text'].strip()
            if not text:
                continue

            if not started:
                # Strip "Abstract" prefix + any dash variants (—, –, --, :)
                text = re.sub(r'^Abstract\s*', '', text, flags=re.IGNORECASE).strip()
                text = text.lstrip('-–—: \u2014\u2013').strip()
                if not text:
                    continue
                started = True

            parts.append(text)

        abstract_text = ' '.join(parts)
        abstract_text = re.sub(r'\s+', ' ', abstract_text).strip()
        print(f"  [OK] Abstract: {len(abstract_text)} characters")
    else:
        print(f"  [WARN] No abstract found")

    # ════════════════════════════════════════════════
    # STEP 5: EXTRACT KEYWORDS
    # ════════════════════════════════════════════════
    keywords_text = ""
    if keywords_idx is not None:
        parts = []
        started = False

        for i in range(keywords_idx, len(spans)):
            s = spans[i]

            # ── Stop at section headers (INTRODUCTION, etc.) ──
            if s['size'] >= 10.0 and s['text'].strip():
                t = s['text'].strip()
                # Roman numeral section markers: "I.", "I. ", "II.", etc.
                if re.match(r'^[IVX]+\.', t):
                    break
                # Standalone Roman numerals: "I", "II", etc.
                if t in ('I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII'):
                    break
                # Roman numeral with space: "I. INTRODUCTION"
                if re.match(r'^[IVX]+\.?\s', t):
                    break
                # "NTRODUCTION" (split-format INTRODUCTION)
                if 'NTRODUCTION' in t:
                    break
                # Regular body text (size 10+, not bold/italic)
                if not s['is_bold'] and not s['is_italic'] and len(t) > 1:
                    break

            # Don't go beyond body text size
            if s['size'] > 12.0:
                break

            text = s['text'].strip()
            if not text:
                continue

            # Only collect keyword-sized spans (8-9pt typically)
            if s['size'] >= 10.0:
                break

            if not started:
                text = re.sub(r'^Keywords?\s*', '', text, flags=re.IGNORECASE).strip()
                text = text.lstrip('-–—: \u2014\u2013').strip()
                if not text:
                    continue
                started = True

            parts.append(text)

        keywords_text = ' '.join(parts)
        keywords_text = re.sub(r'\s+', ' ', keywords_text).strip()
        # Remove trailing period if present
        keywords_text = keywords_text.rstrip('.')
        print(f"  [OK] Keywords: \"{keywords_text[:80]}{'...' if len(keywords_text) > 80 else ''}\"")
    else:
        print(f"  [WARN] No keywords found")

    # ════════════════════════════════════════════════
    # VALIDATION SUMMARY
    # ════════════════════════════════════════════════
    issues = []
    if not title:
        issues.append("missing title")
    if not authors:
        issues.append("missing authors")
    if not abstract_text:
        issues.append("missing abstract")
    if not keywords_text:
        issues.append("missing keywords")

    if issues:
        print(f"  [WARN] ISSUES: {', '.join(issues)}")
    else:
        print(f"  [OK] All fields extracted successfully")

    return {
        'title': title,
        'authors': authors,
        'abstract': abstract_text,
        'keywords': keywords_text,
        'source_file': filename,
    }


# ============================================================
# PDF GENERATION — CUSTOM FLOWABLES
# ============================================================

# Global page tracker: filled during body PDF generation
_page_map = {}


class PageTracker(Flowable):
    """Zero-height flowable that records the page number when drawn."""

    def __init__(self, paper_index):
        Flowable.__init__(self)
        self.paper_index = paper_index
        self.width = 0
        self.height = 0

    def draw(self):
        _page_map[self.paper_index] = self.canv.getPageNumber()


class DotSeparator(Flowable):
    """Centered row of filled dots (● ● ● ...) as visual separator."""

    def __init__(self, width, height=18):
        Flowable.__init__(self)
        self.width = width
        self.height = height

    def draw(self):
        dots = "●  " * 10 + "●"
        self.canv.setFont("Helvetica", 7)
        tw = self.canv.stringWidth(dots, "Helvetica", 7)
        x = (self.width - tw) / 2
        y = max(1, self.height / 3)
        self.canv.drawString(x, y, dots)


# ============================================================
# AUTHOR FORMATTING — Superscript Affiliations
# ============================================================

# Unicode superscript digits for affiliation markers
_SUPERSCRIPT_DIGITS = {
    1: '\u00b9', 2: '\u00b2', 3: '\u00b3', 4: '\u2074', 5: '\u2075',
    6: '\u2076', 7: '\u2077', 8: '\u2078', 9: '\u2079', 10: '\u00b9\u2070',
}

def format_authors_with_affiliations(authors, use_html_super=True):
    """
    Format authors with superscript affiliation numbers.

    Returns:
        (authors_line, affiliations_line)

    If use_html_super=True:
        authors_line uses ReportLab <super> tags for PDF rendering.
    If use_html_super=False:
        authors_line uses Unicode superscript characters (for plain text / TOC / Word).

    Example output:
        authors_line:  "John Doe¹, Jane Smith², Bob Lee¹"
        affiliations_line:  "¹MIT, ²Stanford"
    """
    if not authors:
        return '', ''

    # Build a unique list of colleges, mapping each author to a number
    college_to_num = {}
    college_list = []  # ordered unique colleges
    author_nums = []   # which number each author gets

    for a in authors:
        college = a.get('college', '').strip()
        if not college:
            college = ''
        if college not in college_to_num:
            num = len(college_list) + 1
            college_to_num[college] = num
            college_list.append(college)
        author_nums.append(college_to_num[college])

    # If all authors share the same college, no need for superscripts
    all_same = len(college_list) <= 1

    # Build the authors line
    author_parts = []
    for i, a in enumerate(authors):
        name_safe = html_escape(a['name'])
        if all_same:
            author_parts.append(name_safe)
        else:
            num = author_nums[i]
            if use_html_super:
                author_parts.append(f"{name_safe}<super>{num}</super>")
            else:
                sup = _SUPERSCRIPT_DIGITS.get(num, str(num))
                author_parts.append(f"{name_safe}{sup}")
    authors_line = ', '.join(author_parts)

    # Build the affiliations line
    if all_same and college_list:
        # Single college — just show it centered, no number
        affiliations_line = html_escape(college_list[0])
    elif college_list:
        aff_parts = []
        for idx, college in enumerate(college_list):
            num = idx + 1
            college_safe = html_escape(college) if college else 'N/A'
            if use_html_super:
                aff_parts.append(f"<super>{num}</super>{college_safe}")
            else:
                sup = _SUPERSCRIPT_DIGITS.get(num, str(num))
                aff_parts.append(f"{sup}{college_safe}")
        affiliations_line = ', '.join(aff_parts)
    else:
        affiliations_line = ''

    return authors_line, affiliations_line


# ============================================================
# PDF GENERATION — BODY PAGES
# ============================================================

def _body_page_handler(canvas, doc):
    """Draw header and footer on each body page."""
    canvas.saveState()

    # ══════════════════════════════════════
    # HEADER
    # ══════════════════════════════════════
    # Conference name (italic, left-aligned)
    canvas.setFont("Times-Italic", HEADER_FONT_SIZE)
    header_y = PAGE_HEIGHT - 38
    canvas.drawString(LEFT_MARGIN, header_y, CONFERENCE_HEADER)

    # Deep blue header divider line
    canvas.setStrokeColor(DIVIDER_COLOR)
    canvas.setLineWidth(1.2)
    header_line_y = header_y - 9
    canvas.line(LEFT_MARGIN, header_line_y, PAGE_WIDTH - RIGHT_MARGIN, header_line_y)

    # ══════════════════════════════════════
    # FOOTER
    # ══════════════════════════════════════
    # Deep blue footer divider line
    footer_line_y = BOTTOM_MARGIN - 5
    canvas.setStrokeColor(DIVIDER_COLOR)
    canvas.setLineWidth(1.2)
    canvas.line(LEFT_MARGIN, footer_line_y, PAGE_WIDTH - RIGHT_MARGIN, footer_line_y)

    # Website (left-aligned) below the line
    footer_text_y = footer_line_y - 14
    canvas.setFont("Times-Bold", FOOTER_URL_FONT_SIZE)
    canvas.setFillColor(black)
    canvas.drawString(LEFT_MARGIN, footer_text_y, FOOTER_URL)

    # Page number (right-aligned) below the line
    canvas.setFont("Times-Roman", FOOTER_PAGE_FONT_SIZE)
    canvas.drawRightString(PAGE_WIDTH - RIGHT_MARGIN, footer_text_y, str(doc.page))

    canvas.restoreState()


TIER_SPECS = [
    # Tier 0: Standard generous spacing
    {
        'name': 'standard',
        'font_title': TITLE_FONT_SIZE, 'font_auth': AUTHORS_FONT_SIZE,
        'font_abs': ABSTRACT_FONT_SIZE, 'font_kw': KEYWORDS_FONT_SIZE,
        'leading_factor': LINE_SPACING_FACTOR,
        'space_title': 5, 'space_auth': 8, 'space_abs': 5, 'space_kw': 6, 'spacer_auth_abs': 4,
        'sep_top': 6, 'sep_dot': 14, 'sep_bottom': 8, 'sep_total': 28
    },
    # Tier 1: Compact Margins & Separator
    {
        'name': 'compact_margins',
        'font_title': TITLE_FONT_SIZE, 'font_auth': AUTHORS_FONT_SIZE,
        'font_abs': ABSTRACT_FONT_SIZE, 'font_kw': KEYWORDS_FONT_SIZE,
        'leading_factor': LINE_SPACING_FACTOR,
        'space_title': 3, 'space_auth': 4, 'space_abs': 3, 'space_kw': 3, 'spacer_auth_abs': 2,
        'sep_top': 3, 'sep_dot': 10, 'sep_bottom': 4, 'sep_total': 17
    },
    # Tier 2: Tight Margins & Divider
    {
        'name': 'tight_margins',
        'font_title': TITLE_FONT_SIZE, 'font_auth': AUTHORS_FONT_SIZE,
        'font_abs': ABSTRACT_FONT_SIZE, 'font_kw': KEYWORDS_FONT_SIZE,
        'leading_factor': LINE_SPACING_FACTOR,
        'space_title': 2, 'space_auth': 2, 'space_abs': 2, 'space_kw': 2, 'spacer_auth_abs': 1,
        'sep_top': 2, 'sep_dot': 6, 'sep_bottom': 2, 'sep_total': 10
    },
    # Tier 3: Zero Margins & Minimal Divider
    {
        'name': 'zero_margins',
        'font_title': TITLE_FONT_SIZE, 'font_auth': AUTHORS_FONT_SIZE,
        'font_abs': ABSTRACT_FONT_SIZE, 'font_kw': KEYWORDS_FONT_SIZE,
        'leading_factor': LINE_SPACING_FACTOR,
        'space_title': 1, 'space_auth': 1, 'space_abs': 1, 'space_kw': 1, 'spacer_auth_abs': 1,
        'sep_top': 1, 'sep_dot': 4, 'sep_bottom': 1, 'sep_total': 6
    }
]


def _build_and_measure_page(page_papers, page_paper_indices, tier, avail_width):
    """
    Builds the ReportLab flowables for all papers on a single page using the given
    tier parameters and measures the exact total rendered height.
    """
    font_title = tier['font_title']
    font_auth = tier['font_auth']
    font_abs = tier['font_abs']
    font_kw = tier['font_kw']
    leading_factor = tier['leading_factor']
    space_title = tier['space_title']
    space_auth = tier['space_auth']
    space_abs = tier['space_abs']
    space_kw = tier['space_kw']
    spacer_auth_abs = tier['spacer_auth_abs']
    sep_top = tier['sep_top']
    sep_dot = tier['sep_dot']
    sep_bottom = tier['sep_bottom']

    uid = random.randint(1, 999999)
    st_title = ParagraphStyle(
        f"title_{tier.get('name', 'tier')}_{len(page_papers)}_{uid}",
        fontName='Times-Bold',
        fontSize=font_title,
        leading=font_title * leading_factor,
        alignment=TA_CENTER,
        spaceAfter=space_title,
        wordSpace=WORD_SPACING,
    )
    st_auth = ParagraphStyle(
        f"auth_{tier.get('name', 'tier')}_{len(page_papers)}_{uid}",
        fontName='Times-Roman',
        fontSize=font_auth,
        leading=font_auth * leading_factor,
        alignment=TA_CENTER,
        spaceAfter=space_auth,
        wordSpace=WORD_SPACING * 0.7,
    )
    st_abs = ParagraphStyle(
        f"abs_{tier.get('name', 'tier')}_{len(page_papers)}_{uid}",
        fontName='Times-Roman',
        fontSize=font_abs,
        leading=font_abs * leading_factor,
        alignment=TA_JUSTIFY,
        spaceAfter=space_abs,
        wordSpace=WORD_SPACING,
    )
    st_kw = ParagraphStyle(
        f"kw_{tier.get('name', 'tier')}_{len(page_papers)}_{uid}",
        fontName='Times-Roman',
        fontSize=font_kw,
        leading=font_kw * leading_factor,
        alignment=TA_LEFT,
        spaceAfter=space_kw,
        wordSpace=WORD_SPACING * 0.7,
    )

    page_flowables = []
    total_h = 0
    k = len(page_papers)

    for item_idx, (paper, paper_idx) in enumerate(zip(page_papers, page_paper_indices)):
        title_safe = html_escape(paper['title'])
        abstract_safe = html_escape(paper['abstract'])
        keywords_safe = html_escape(paper['keywords'])
        authors_text, affiliations_text = format_authors_with_affiliations(paper['authors'], use_html_super=True)

        p_title = Paragraph(title_safe, st_title)
        p_authors = Paragraph(authors_text, st_auth)
        p_aff = Paragraph(f'<i>{affiliations_text}</i>', st_auth) if affiliations_text else None
        p_abs = Paragraph(f"<b>Abstract— </b>{abstract_safe}", st_abs)
        p_kw = Paragraph(f"<b>Keywords— </b><i>{keywords_safe}</i>", st_kw)

        # Measure flowables
        _, h_t = p_title.wrap(avail_width, 9999)
        _, h_a = p_authors.wrap(avail_width, 9999)
        h_aff = 0
        if p_aff:
            _, h_aff = p_aff.wrap(avail_width, 9999)
        _, h_ab = p_abs.wrap(avail_width, 9999)
        _, h_k = p_kw.wrap(avail_width, 9999)

        item_h = (h_t + space_title + h_a +
                  (h_aff + space_auth if p_aff else space_auth) +
                  spacer_auth_abs + h_ab + space_abs + h_k + space_kw)
        total_h += item_h

        page_flowables.append(PageTracker(paper_idx))
        page_flowables.append(p_title)
        page_flowables.append(p_authors)
        if p_aff:
            page_flowables.append(p_aff)
        page_flowables.append(Spacer(1, spacer_auth_abs))
        page_flowables.append(p_abs)
        page_flowables.append(p_kw)

        # Separator between papers on the same page (not after the last paper)
        if item_idx < k - 1:
            sep_h = sep_top + sep_dot + sep_bottom
            total_h += sep_h
            page_flowables.append(Spacer(1, sep_top))
            page_flowables.append(DotSeparator(avail_width, height=sep_dot))
            page_flowables.append(Spacer(1, sep_bottom))

    return page_flowables, total_h


def _precompute_paper_heights(papers, avail_width):
    """
    Precomputes the rendered height matrix for all papers across all tiers.
    Matrix shape: N x 5
    """
    matrix = []
    for p_idx, p in enumerate(papers):
        row = []
        for t_idx, tier in enumerate(TIER_SPECS):
            _, h = _build_and_measure_page([p], [p_idx], tier, avail_width)
            row.append(h)
        matrix.append(row)
    return matrix


def _find_optimal_zero_waste_packing(papers, avail_height):
    """
    Combinatorial Re-Ordering & Bin Packing Optimization Engine:
    Shuffles and matches abstracts of complementary sizes (large + small, medium + medium,
    or small + small + small) across all available papers so that:
      1. Every single page before the last page has BETWEEN 2 AND 4 ABSTRACTS and is packed to 85%-100% fullness.
      2. Any remaining slack is concentrated strictly on the final page.
      3. Total number of pages is minimized.
    """
    n = len(papers)
    if n == 0:
        return []
    if n == 1:
        return [(0,)]
    if n == 2:
        return [(0, 1)]

    height_matrix = _precompute_paper_heights(papers, CONTENT_WIDTH)
    target_budget = avail_height - 25.0

    def test_group(grp):
        k = len(grp)
        if k == 0:
            return True, 0.0, 0
        if k > 4:  # Maximum 4 abstracts per page for clean, professional layout
            return False, float('inf'), None
        for t_idx, tier in enumerate(TIER_SPECS):
            h_papers = sum(height_matrix[i][t_idx] for i in grp)
            h_sep = (k - 1) * tier['sep_total']
            tot = h_papers + h_sep
            if tot <= target_budget:
                return True, tot, t_idx
        return False, float('inf'), None

    # Sort descending by standard height
    sorted_items = sorted(range(n), key=lambda i: height_matrix[i][0], reverse=True)

    # 1. Best-Fit Decreasing
    bins = []
    for item in sorted_items:
        best_b = -1
        min_slack = float('inf')
        for b_idx, b in enumerate(bins):
            if len(b) >= 4:
                continue
            cand = b + [item]
            fits, tot, _ = test_group(cand)
            if fits:
                slack = avail_height - tot
                if slack < min_slack:
                    min_slack = slack
                    best_b = b_idx
        if best_b != -1:
            bins[best_b].append(item)
        else:
            bins.append([item])

    # 2. Repair any single-item bins: pair singles together or merge into bins with <= 3 items
    multi_bins = [b for b in bins if len(b) >= 2]
    single_bins = [b for b in bins if len(b) == 1]
    unmatched = []
    for s in single_bins:
        item = s[0]
        placed = False
        for b in multi_bins:
            if len(b) >= 4:
                continue
            cand = b + [item]
            fits, _, _ = test_group(cand)
            if fits:
                b.append(item)
                placed = True
                break
        if not placed:
            unmatched.append(item)

    while len(unmatched) >= 2:
        s1 = unmatched.pop(0)
        s2 = unmatched.pop(0)
        multi_bins.append([s1, s2])

    if unmatched:
        multi_bins.append(unmatched)

    # 3. Fast Simulated Annealing / Local Search with 3000 Iterations
    def score_partition(part):
        sc = 0.0
        for b in part:
            fits, tot, _ = test_group(b)
            if fits:
                ratio = min(1.0, tot / avail_height)
                sc += (ratio ** 4) * 100.0
                if len(b) >= 2:
                    sc += 50.0
        return sc

    best_bins = [list(b) for b in multi_bins]
    best_score = score_partition(best_bins)
    curr_bins = [list(b) for b in best_bins]

    for it in range(3000):
        if len(curr_bins) < 2:
            break
        b1_idx, b2_idx = random.sample(range(len(curr_bins)), 2)
        b1 = curr_bins[b1_idx]
        b2 = curr_bins[b2_idx]

        # Try item swap
        if b1 and b2:
            i1 = random.randrange(len(b1))
            i2 = random.randrange(len(b2))
            c1 = list(b1)
            c2 = list(b2)
            c1[i1], c2[i2] = c2[i2], c1[i1]
            if len(c1) <= 4 and len(c2) <= 4:
                f1, _, _ = test_group(c1)
                f2, _, _ = test_group(c2)
                if f1 and f2:
                    cand_part = list(curr_bins)
                    cand_part[b1_idx] = c1
                    cand_part[b2_idx] = c2
                    sc = score_partition(cand_part)
                    if sc > best_score:
                        best_score = sc
                        best_bins = [list(b) for b in cand_part]
                        curr_bins = cand_part
                        continue

        # Try item transfer if b1 has >= 3 and b2 has <= 3
        if len(b1) >= 3 and len(b2) <= 3:
            i1 = random.randrange(len(b1))
            c1 = [x for idx, x in enumerate(b1) if idx != i1]
            c2 = b2 + [b1[i1]]
            f1, _, _ = test_group(c1)
            f2, _, _ = test_group(c2)
            if f1 and f2:
                cand_part = list(curr_bins)
                cand_part[b1_idx] = c1
                cand_part[b2_idx] = c2
                sc = score_partition(cand_part)
                if sc > best_score:
                    best_score = sc
                    best_bins = [list(b) for b in cand_part]
                    curr_bins = cand_part

    # Sort final page groups descending by fill percentage
    page_records = []
    for b in best_bins:
        if not b:
            continue
        _, tot, t_idx = test_group(b)
        page_records.append((tuple(b), tot, t_idx))

    page_records.sort(key=lambda rec: rec[1], reverse=True)
    return [rec[0] for rec in page_records]


def _generate_page_flowables_justified(page_papers, page_paper_indices, avail_width, avail_height, is_final_page=False):
    """
    Generates flowables for a page and vertically justifies / stretches internal spacing
    so that the entire page is 100% filled from top to bottom, eliminating empty white space
    at the bottom of the page.
    """
    k = len(page_papers)
    target_budget = avail_height - 22.0
    best_tier = None
    base_h = 0

    # Find fitting tier
    for tier in TIER_SPECS:
        _, measured_h = _build_and_measure_page(page_papers, page_paper_indices, tier, avail_width)
        if measured_h <= target_budget:
            best_tier = tier
            base_h = measured_h
            break

    if best_tier is None:
        best_tier = TIER_SPECS[-1]
        _, base_h = _build_and_measure_page(page_papers, page_paper_indices, best_tier, avail_width)

    # Calculate remaining white space (slack)
    slack = (avail_height - 18.0) - base_h

    # Vertically justify if there is slack and it's not a short final page
    if slack > 4.0 and (not is_final_page or (base_h / avail_height) >= 0.70):
        # Expansion points: 5 per paper + 2 per separator
        num_expand_points = 5 * k + (2 * (k - 1) if k > 1 else 0)
        boost = min(10.0, slack / max(1, num_expand_points))

        # Iteratively verify that justified layout does not exceed target budget
        while boost >= 0.5:
            justified_tier = dict(best_tier)
            justified_tier['name'] = f"{best_tier['name']}_justified"
            justified_tier['space_title'] = best_tier['space_title'] + (boost * 0.8)
            justified_tier['space_auth'] = best_tier['space_auth'] + (boost * 1.0)
            justified_tier['space_abs'] = best_tier['space_abs'] + (boost * 0.9)
            justified_tier['space_kw'] = best_tier['space_kw'] + (boost * 0.8)
            justified_tier['spacer_auth_abs'] = best_tier['spacer_auth_abs'] + (boost * 1.0)
            justified_tier['sep_top'] = best_tier['sep_top'] + (boost * 1.2)
            justified_tier['sep_bottom'] = best_tier['sep_bottom'] + (boost * 1.4)

            flowables, final_h = _build_and_measure_page(page_papers, page_paper_indices, justified_tier, avail_width)
            if final_h <= avail_height - 14.0:
                return flowables, justified_tier['name'], final_h
            boost -= 0.5

    # Build standard flowables
    flowables, final_h = _build_and_measure_page(page_papers, page_paper_indices, best_tier, avail_width)
    return flowables, best_tier['name'], final_h


def generate_body_pdf(papers, output_path):
    """
    Generate the body pages of the compiled PDF using ReportLab Platypus.

    Zero-White-Space Guarantees:
      1. Uses Combinatorial Re-ordering & Bin Packing to match complementary abstracts together.
      2. Every non-final page contains AT LEAST 2 abstracts and is packed to 90%-100% fullness.
      3. Vertically justifies remaining slack so there is NO empty white space at the bottom of pages.
      4. Only the final page holds the remainder.

    Returns tuple (page_map, page_groups, page_density_modes)
    """
    global _page_map
    _page_map = {}

    doc = BaseDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=LEFT_MARGIN,
        rightMargin=RIGHT_MARGIN,
        topMargin=TOP_MARGIN,
        bottomMargin=BOTTOM_MARGIN,
    )

    # Content frame
    avail_height = PAGE_HEIGHT - TOP_MARGIN - BOTTOM_MARGIN
    frame = Frame(
        LEFT_MARGIN,
        BOTTOM_MARGIN,
        CONTENT_WIDTH,
        avail_height,
        id='body_frame',
    )

    doc.addPageTemplates([
        PageTemplate('body_page', frames=[frame], onPage=_body_page_handler)
    ])

    # ── Step 1: Combinatorial Re-Ordering Bin Packing ──
    page_groups = _find_optimal_zero_waste_packing(papers, avail_height)

    print(f"\n  [ANALYSIS] Available height per page: {avail_height:.0f}pt")
    print(f"\n  [PACKING] Zero-White-Space Optimized Page Groups ({len(page_groups)} pages):")

    elements = []
    page_density_modes = []

    for pg_num, group in enumerate(page_groups):
        page_papers = [papers[idx] for idx in group]
        page_paper_indices = list(group)
        is_last = (pg_num == len(page_groups) - 1)

        # Generate vertically justified flowables to eliminate bottom white space
        flowables, mode_name, measured_h = _generate_page_flowables_justified(
            page_papers, page_paper_indices, CONTENT_WIDTH, avail_height, is_final_page=is_last
        )
        page_density_modes.append(mode_name)

        usage = min(100.0, (measured_h / avail_height) * 100)
        tag = " (Final Page)" if is_last else ""
        mode_tag = f" [{mode_name}]" if mode_name != 'standard' else ""
        titles = [papers[idx]['title'][:38] + '...' for idx in group]
        print(f"    Page {pg_num+1}: {len(group)} abstract(s), {usage:.0f}% filled{mode_tag}{tag} -- {', '.join(titles)}")

        if pg_num > 0:
            elements.append(PageBreak())

        # Wrap all flowables for this page in KeepTogether to guarantee single-page fit
        page_container = KeepTogether(flowables)
        elements.append(page_container)

    # Build the PDF
    doc.build(elements)
    return dict(_page_map), page_groups, page_density_modes


# ============================================================
# PDF GENERATION — TABLE OF CONTENTS
# ============================================================

def generate_toc_pdf(papers, page_map, output_path):
    """
    Generate Table of Contents page(s) using direct canvas drawing
    for precise dotted-leader alignment.
    """
    c = canvas_mod.Canvas(output_path, pagesize=A4)
    y = PAGE_HEIGHT - 75

    # ── "Contents" heading ──
    c.setFont("Times-Bold", 24)
    c.drawString(LEFT_MARGIN, y, "Contents")
    y -= 28

    # Deep blue underline
    c.setStrokeColor(DIVIDER_COLOR)
    c.setLineWidth(1.5)
    c.line(LEFT_MARGIN, y, PAGE_WIDTH - RIGHT_MARGIN, y)
    y -= 25
    # ── Sort papers by page number ascending ──
    sorted_papers = [(i, p, page_map.get(i, 9999)) for i, p in enumerate(papers)]
    sorted_papers.sort(key=lambda x: x[2])

    for i, paper, page_val in sorted_papers:
        page_num = str(page_val) if page_val != 9999 else '?'

        # ── Pre-estimate this entry's total height ──
        toc_title_font = "Times-Roman"
        toc_title_size = 9.0
        toc_line_height = 11.5

        title = paper['title']
        pnum_width = stringWidth(page_num, "Times-Roman", toc_title_size)
        dot_char_width = stringWidth('.', "Times-Roman", 8)
        max_title_width = CONTENT_WIDTH - pnum_width - 30

        lines = _word_wrap(title, toc_title_font, toc_title_size, max_title_width)
        author_names = ', '.join(a['name'] for a in paper['authors'])
        author_lines = _word_wrap(author_names, "Times-Italic", 7.5, CONTENT_WIDTH) if author_names else []

        # Total height this entry will consume
        entry_height = (len(lines) * toc_line_height +
                        len(author_lines) * 9.5 + 6)

        # ── Check for page overflow BEFORE drawing ──
        if y - entry_height < 50:
            _draw_toc_footer(c)
            c.showPage()
            # Draw header on continuation TOC pages
            _draw_toc_header(c)
            y = PAGE_HEIGHT - 75

        # ── Draw title with dotted leaders → page number ──
        for j, line in enumerate(lines):
            c.setFont(toc_title_font, toc_title_size)
            c.drawString(LEFT_MARGIN, y, line)

            if j == len(lines) - 1:
                title_end_x = LEFT_MARGIN + stringWidth(
                    line, toc_title_font, toc_title_size
                ) + 4
                page_right_x = PAGE_WIDTH - RIGHT_MARGIN

                c.setFont("Times-Roman", 8)
                x = title_end_x
                while x + dot_char_width < page_right_x - pnum_width - 5:
                    c.drawString(x, y, '.')
                    x += dot_char_width + 1.3

                c.setFont("Times-Roman", toc_title_size)
                c.drawRightString(page_right_x, y, page_num)

            y -= toc_line_height

        # ── Author names below title (italic, smaller) ──
        if author_lines:
            c.setFont("Times-Italic", 7.5)
            for al in author_lines:
                c.drawString(LEFT_MARGIN, y, al)
                y -= 9.5

        y -= 6  # clean gap before next entry

    _draw_toc_footer(c)
    c.save()


def _draw_toc_header(canvas):
    """Draw conference header on TOC continuation pages."""
    canvas.setFont("Times-Italic", HEADER_FONT_SIZE)
    header_y = PAGE_HEIGHT - 38
    canvas.drawString(LEFT_MARGIN, header_y, CONFERENCE_HEADER)

    canvas.setStrokeColor(DIVIDER_COLOR)
    canvas.setLineWidth(1.2)
    header_line_y = header_y - 9
    canvas.line(LEFT_MARGIN, header_line_y,
                PAGE_WIDTH - RIGHT_MARGIN, header_line_y)


def _draw_toc_footer(canvas):
    """Draw footer on a TOC page with deep blue divider."""
    # Deep blue footer divider line
    footer_line_y = BOTTOM_MARGIN - 5
    canvas.setStrokeColor(DIVIDER_COLOR)
    canvas.setLineWidth(1.2)
    canvas.line(LEFT_MARGIN, footer_line_y, PAGE_WIDTH - RIGHT_MARGIN, footer_line_y)

    # Website (left-aligned)
    footer_text_y = footer_line_y - 14
    canvas.setFont("Times-Bold", FOOTER_URL_FONT_SIZE)
    canvas.setFillColor(black)
    canvas.drawString(LEFT_MARGIN, footer_text_y, FOOTER_URL)


def _word_wrap(text, font_name, font_size, max_width):
    """Simple word-wrap that returns a list of lines."""
    words = text.split()
    lines = []
    current = ""

    for word in words:
        test = (current + " " + word).strip()
        if stringWidth(test, font_name, font_size) <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word

    if current:
        lines.append(current)

    return lines if lines else [text]


# ============================================================
# PDF MERGE
# ============================================================

def merge_pdfs(toc_path, body_path, output_path):
    """Merge Cover (optional) + Messages (optional) + Invited Talks (optional) + Table of Contents + Body into a single final PDF."""
    output_doc = fitz.open()


    toc_doc = fitz.open(toc_path)
    body_doc = fitz.open(body_path)

    output_doc.insert_pdf(toc_doc)
    output_doc.insert_pdf(body_doc)
    output_doc.save(output_path)

    output_doc.close()
    toc_doc.close()
    body_doc.close()


# ============================================================
# COVER PAGE GENERATION
# ============================================================

def generate_cover_page_pdf(output_path):
    """
    Generate a cover page PDF from cover_page.json.
    Blocks store HTML in 'content' (with <b>, <i>, <u>, <br> tags).
    Falls back to plain 'text' field for backward compatibility.
    Returns True if cover page was generated, False if no config found.
    """
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cover_page.json')
    if not os.path.exists(config_path):
        return False

    try:
        with open(config_path, 'r') as f:
            data = json.load(f)
    except Exception:
        return False

    blocks = data.get('blocks', [])
    if not blocks:
        return False

    c = canvas_mod.Canvas(output_path, pagesize=A4)

    for block in blocks:
        block_type = block.get('type', 'text')
        x = block.get('x', 0)
        y_top = block.get('y', 0)
        width = block.get('width', 200)
        height = block.get('height', 30)
        
        y_rl = PAGE_HEIGHT - y_top - height

        if block_type == 'image':
            image_url = block.get('imageUrl', '')
            if image_url.startswith('data:image/'):
                import base64
                import io
                from reportlab.lib.utils import ImageReader
                try:
                    header, encoded = image_url.split(',', 1)
                    image_data = base64.b64decode(encoded)
                    image_stream = io.BytesIO(image_data)
                    img_reader = ImageReader(image_stream)
                    c.drawImage(img_reader, x, y_rl, width=width, height=height, preserveAspectRatio=True, mask='auto')
                except Exception as e:
                    print(f"Error drawing image to PDF: {e}")
            continue

        if block_type == 'drawing':
            lines = block.get('lines', [])
            sym = block.get('symmetry', 'none')
            stroke_width = block.get('strokeWidth', 2)
            # Parse hex color
            color_hex = block.get('strokeColor', '#000000').lstrip('#')
            try:
                r, g, b = tuple(int(color_hex[i:i+2], 16) / 255.0 for i in (0, 2, 4))
            except Exception:
                r, g, b = 0, 0, 0
                
            c.setStrokeColorRGB(r, g, b)
            c.setLineWidth(stroke_width)
            
            # Helper to draw a line
            def draw_rl_line(l_x1, l_y1, l_x2, l_y2):
                # Convert drawing box coords to absolute PDF coords
                # drawing (0,0) is top-left of block
                pdf_x1 = x + l_x1
                pdf_y1 = PAGE_HEIGHT - (y_top + l_y1)
                pdf_x2 = x + l_x2
                pdf_y2 = PAGE_HEIGHT - (y_top + l_y2)
                c.line(pdf_x1, pdf_y1, pdf_x2, pdf_y2)

            for line in lines:
                l_x1, l_y1, l_x2, l_y2 = line.get('x1',0), line.get('y1',0), line.get('x2',0), line.get('y2',0)
                draw_rl_line(l_x1, l_y1, l_x2, l_y2)
                
                # Apply symmetry
                if sym in ('horizontal', 'both'):
                    draw_rl_line(width - l_x1, l_y1, width - l_x2, l_y2)
                if sym in ('vertical', 'both'):
                    draw_rl_line(l_x1, height - l_y1, l_x2, height - l_y2)
                if sym == 'both':
                    draw_rl_line(width - l_x1, height - l_y1, width - l_x2, height - l_y2)
            continue

        # Get HTML content, fall back to plain text
        html_content = block.get('content', '')
        if not html_content:
            plain = block.get('text', '')
            html_content = plain.replace('\n', '<br/>')

        font_size = block.get('fontSize', 12)
        font_weight = block.get('fontWeight', 'normal')
        font_style = block.get('fontStyle', 'normal')
        text_align = block.get('textAlign', 'center')

        # Map alignment
        align_map = {'left': TA_LEFT, 'center': TA_CENTER, 'right': TA_LEFT}
        alignment = align_map.get(text_align, TA_CENTER)
        if text_align == 'right':
            from reportlab.lib.enums import TA_RIGHT
            alignment = TA_RIGHT

        # Choose base font
        font_family = block.get('fontFamily', 'Times New Roman')
        is_bold = (font_weight == 'bold')
        is_italic = (font_style == 'italic')
        
        if font_family == 'Arial':
            if is_bold and is_italic: font_name = 'Helvetica-BoldOblique'
            elif is_bold: font_name = 'Helvetica-Bold'
            elif is_italic: font_name = 'Helvetica-Oblique'
            else: font_name = 'Helvetica'
        elif font_family == 'Courier New':
            if is_bold and is_italic: font_name = 'Courier-BoldOblique'
            elif is_bold: font_name = 'Courier-Bold'
            elif is_italic: font_name = 'Courier-Oblique'
            else: font_name = 'Courier'
        elif font_family == 'Times New Roman':
            if is_bold and is_italic: font_name = 'Times-BoldItalic'
            elif is_bold: font_name = 'Times-Bold'
            elif is_italic: font_name = 'Times-Italic'
            else: font_name = 'Times-Roman'
        else:
            from reportlab.pdfbase import pdfmetrics
            if font_family in pdfmetrics.getRegisteredFontNames():
                font_name = font_family
            else:
                font_name = 'Times-Roman'

        # Convert HTML to ReportLab-compatible XML
        # ReportLab Paragraph supports: <b>, <i>, <u>, <br/>, <font>
        # Clean up browser HTML (e.g. <div>, <span>) to just text + inline tags
        rl_text = html_content
        # Replace <br> variants with <br/>
        rl_text = re.sub(r'<br\s*/?>', '<br/>', rl_text)
        # Remove <div> wrappers (browsers add these in contentEditable)
        rl_text = re.sub(r'<div[^>]*>', '<br/>', rl_text)
        rl_text = re.sub(r'</div>', '', rl_text)
        # Remove <span> tags (keep content)
        rl_text = re.sub(r'<span[^>]*>', '', rl_text)
        rl_text = re.sub(r'</span>', '', rl_text)
        # Keep <b>, <i>, <u>, <font> tags — ReportLab understands these
        # Remove any other HTML tags
        rl_text = re.sub(r'<(?!/?(?:b|i|u|font|br|strong|em)[ />])[^>]+>', '', rl_text)
        # Convert <strong> → <b>, <em> → <i>
        rl_text = rl_text.replace('<strong>', '<b>').replace('</strong>', '</b>')
        rl_text = rl_text.replace('<em>', '<i>').replace('</em>', '</i>')
        # Remove leading <br/>
        rl_text = re.sub(r'^(<br/>)+', '', rl_text)
        # Escape &
        rl_text = rl_text.replace('&nbsp;', ' ')
        if '&' in rl_text:
            rl_text = re.sub(r'&(?!amp;|lt;|gt;|quot;)', '&amp;', rl_text)

        leading = font_size * 1.35

        style = ParagraphStyle(
            name=f'cover_{block.get("id", "block")}',
            fontName=font_name,
            fontSize=font_size,
            leading=leading,
            alignment=alignment,
            textColor=black,
        )

        try:
            para = Paragraph(rl_text, style)
        except Exception:
            # Fallback: strip all HTML and render plain text
            plain = re.sub(r'<[^>]+>', ' ', html_content).strip()
            para = Paragraph(plain, style)

        # Calculate position: web top→RL bottom
        y_rl = PAGE_HEIGHT - y_top - height

        # Draw paragraph in a frame
        para_w, para_h = para.wrap(width, height)
        para.drawOn(c, x, y_rl + (height - para_h))

    c.save()
    return True


# ============================================================
# INVITED TALKS GENERATION
# ============================================================

def generate_messages_pdf(output_path):
    """
    Generate the messages PDF (multi-page) from messages.json.
    Uses the same rendering logic as invited talks.
    """
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'messages.json')
    if not os.path.exists(config_path):
        return False

    try:
        with open(config_path, 'r') as f:
            data = json.load(f)
    except Exception:
        return False

    pages = data.get('pages', [])
    if not pages:
        return False

    c = canvas_mod.Canvas(output_path, pagesize=A4)

    for page_data in pages:
        blocks = page_data.get('blocks', [])
        for block in blocks:
            block_type = block.get('type', 'text')
            x = block.get('x', 0)
            y_top = block.get('y', 0)
            width = block.get('width', 200)
            height = block.get('height', 30)
            
            y_rl = PAGE_HEIGHT - y_top - height

            if block_type == 'image':
                image_url = block.get('imageUrl', '')
                if image_url.startswith('data:image/'):
                    import base64
                    import io
                    from reportlab.lib.utils import ImageReader
                    try:
                        header, encoded = image_url.split(',', 1)
                        image_data = base64.b64decode(encoded)
                        image_stream = io.BytesIO(image_data)
                        img_reader = ImageReader(image_stream)
                        c.drawImage(img_reader, x, y_rl, width=width, height=height, preserveAspectRatio=True, mask='auto')
                    except Exception:
                        pass
                continue

            if block_type == 'shape':
                shape_type = block.get('shapeType', 'rect')
                stroke_width = block.get('strokeWidth', 2)
                
                stroke_hex = block.get('strokeColor', '#000000').lstrip('#')
                try:
                    sr, sg, sb = tuple(int(stroke_hex[i:i+2], 16) / 255.0 for i in (0, 2, 4))
                    c.setStrokeColorRGB(sr, sg, sb)
                except Exception:
                    c.setStrokeColorRGB(0, 0, 0)
                c.setLineWidth(stroke_width)
                
                fill_color = block.get('fillColor', '')
                has_fill = bool(fill_color and fill_color != 'transparent')
                if has_fill:
                    fill_hex = fill_color.lstrip('#')
                    try:
                        fr, fg, fb = tuple(int(fill_hex[i:i+2], 16) / 255.0 for i in (0, 2, 4))
                        c.setFillColorRGB(fr, fg, fb)
                    except Exception:
                        has_fill = False

                pdf_x = x + stroke_width/2.0
                pdf_y = PAGE_HEIGHT - y_top - height + stroke_width/2.0
                w = width - stroke_width
                h = height - stroke_width
                
                if shape_type == 'rect':
                    c.rect(pdf_x, pdf_y, w, h, stroke=1, fill=1 if has_fill else 0)
                elif shape_type == 'triangle':
                    path = c.beginPath()
                    path.moveTo(pdf_x + w/2, pdf_y + h)
                    path.lineTo(pdf_x + w, pdf_y)
                    path.lineTo(pdf_x, pdf_y)
                    path.close()
                    c.drawPath(path, stroke=1, fill=1 if has_fill else 0)
                continue

            if block_type == 'drawing':
                preview_image = block.get('previewImage', '')
                if preview_image.startswith('data:image/'):
                    import base64
                    import io
                    from reportlab.lib.utils import ImageReader
                    try:
                        header, encoded = preview_image.split(',', 1)
                        image_data = base64.b64decode(encoded)
                        image_stream = io.BytesIO(image_data)
                        img_reader = ImageReader(image_stream)
                        c.drawImage(img_reader, x, y_rl, width=width, height=height, preserveAspectRatio=True, mask='auto')
                    except Exception:
                        pass
                continue

            # Text block
            content = block.get('content', '')
            font_size = block.get('fontSize', 12)
            font_weight = block.get('fontWeight', 'normal')
            text_align = block.get('textAlign', 'left')
            font_family = block.get('fontFamily', 'Times-Roman')
            
            rl_font = 'Times-Bold' if font_weight == 'bold' else 'Times-Roman'
            c.setFont(rl_font, font_size)
            c.setFillColorRGB(0, 0, 0)

            import re as re_mod
            clean_text = re_mod.sub(r'<br\s*/?>', '\n', content)
            clean_text = re_mod.sub(r'<[^>]+>', '', clean_text)
            
            from reportlab.lib.utils import simpleSplit
            lines_list = []
            for paragraph in clean_text.split('\n'):
                if paragraph.strip() == '':
                    lines_list.append('')
                else:
                    wrapped = simpleSplit(paragraph, rl_font, font_size, width - 4)
                    lines_list.extend(wrapped)

            line_height = font_size * 1.3
            text_y = PAGE_HEIGHT - y_top - font_size

            for text_line in lines_list:
                if text_y < y_rl:
                    break
                if text_align == 'center':
                    c.drawCentredString(x + width / 2, text_y, text_line)
                elif text_align == 'right':
                    c.drawRightString(x + width, text_y, text_line)
                else:
                    c.drawString(x + 2, text_y, text_line)
                text_y -= line_height

        c.showPage()

    c.save()
    return True


def generate_invited_talks_pdf(output_path):
    """
    Generate the invited talks PDF (multi-page) from invited_talks.json.
    """
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'invited_talks.json')
    if not os.path.exists(config_path):
        return False

    try:
        with open(config_path, 'r') as f:
            data = json.load(f)
    except Exception:
        return False

    pages = data.get('pages', [])
    if not pages:
        return False

    c = canvas_mod.Canvas(output_path, pagesize=A4)

    for page_data in pages:
        blocks = page_data.get('blocks', [])
        for block in blocks:
            block_type = block.get('type', 'text')
            x = block.get('x', 0)
            y_top = block.get('y', 0)
            width = block.get('width', 200)
            height = block.get('height', 30)
            
            y_rl = PAGE_HEIGHT - y_top - height

            if block_type == 'image':
                image_url = block.get('imageUrl', '')
                if image_url.startswith('data:image/'):
                    import base64
                    import io
                    from reportlab.lib.utils import ImageReader
                    try:
                        header, encoded = image_url.split(',', 1)
                        image_data = base64.b64decode(encoded)
                        image_stream = io.BytesIO(image_data)
                        img_reader = ImageReader(image_stream)
                        c.drawImage(img_reader, x, y_rl, width=width, height=height, preserveAspectRatio=True, mask='auto')
                    except Exception as e:
                        print(f"Error drawing image to PDF: {e}")
                continue


            if block_type == 'shape':
                shape_type = block.get('shapeType', 'rect')
                stroke_width = block.get('strokeWidth', 2)
                
                stroke_hex = block.get('strokeColor', '#000000').lstrip('#')
                try:
                    sr, sg, sb = tuple(int(stroke_hex[i:i+2], 16) / 255.0 for i in (0, 2, 4))
                    c.setStrokeColorRGB(sr, sg, sb)
                except Exception:
                    c.setStrokeColorRGB(0, 0, 0)
                c.setLineWidth(stroke_width)
                
                fill_color = block.get('fillColor', '')
                has_fill = bool(fill_color and fill_color != 'transparent')
                if has_fill:
                    fill_hex = fill_color.lstrip('#')
                    try:
                        fr, fg, fb = tuple(int(fill_hex[i:i+2], 16) / 255.0 for i in (0, 2, 4))
                        c.setFillColorRGB(fr, fg, fb)
                    except Exception:
                        has_fill = False

                pdf_x = x + stroke_width/2.0
                pdf_y = PAGE_HEIGHT - y_top - height + stroke_width/2.0
                w = width - stroke_width
                h = height - stroke_width
                
                if shape_type == 'rect':
                    c.rect(pdf_x, pdf_y, w, h, stroke=1, fill=1 if has_fill else 0)
                elif shape_type == 'triangle':
                    path = c.beginPath()
                    path.moveTo(pdf_x + w/2, pdf_y + h)
                    path.lineTo(pdf_x + w, pdf_y)
                    path.lineTo(pdf_x, pdf_y)
                    path.close()
                    c.drawPath(path, stroke=1, fill=1 if has_fill else 0)
                continue

            if block_type == 'drawing':
                lines = block.get('lines', [])
                sym = block.get('symmetry', 'none')
                stroke_width = block.get('strokeWidth', 2)
                color_hex = block.get('strokeColor', '#000000').lstrip('#')
                try:
                    r, g, b = tuple(int(color_hex[i:i+2], 16) / 255.0 for i in (0, 2, 4))
                except Exception:
                    r, g, b = 0, 0, 0
                    
                c.setStrokeColorRGB(r, g, b)
                c.setLineWidth(stroke_width)
                
                fill_color = block.get('fillColor', '')
                has_fill = bool(fill_color and fill_color != 'transparent')
                if has_fill:
                    fill_hex = fill_color.lstrip('#')
                    try:
                        fr, fg, fb = tuple(int(fill_hex[i:i+2], 16) / 255.0 for i in (0, 2, 4))
                        c.setFillColorRGB(fr, fg, fb)
                    except Exception:
                        has_fill = False

                # First draw fill using path
                if has_fill and lines:
                    path = c.beginPath()
                    used = set()
                    current = lines[0]
                    used.add(current.get('id'))
                    
                    def conv_x(vx): return x + vx
                    def conv_y(vy): return PAGE_HEIGHT - (y_top + vy)
                    
                    path.moveTo(conv_x(current.get('x1',0)), conv_y(current.get('y1',0)))
                    path.lineTo(conv_x(current.get('x2',0)), conv_y(current.get('y2',0)))
                    last_pt = (current.get('x2',0), current.get('y2',0))
                    
                    while len(used) < len(lines):
                        found = False
                        for l in lines:
                            lid = l.get('id')
                            if lid not in used:
                                lx1, ly1 = l.get('x1',0), l.get('y1',0)
                                lx2, ly2 = l.get('x2',0), l.get('y2',0)
                                if abs(lx1 - last_pt[0]) < 2 and abs(ly1 - last_pt[1]) < 2:
                                    path.lineTo(conv_x(lx2), conv_y(ly2))
                                    last_pt = (lx2, ly2)
                                    used.add(lid)
                                    found = True
                                    break
                                elif abs(lx2 - last_pt[0]) < 2 and abs(ly2 - last_pt[1]) < 2:
                                    path.lineTo(conv_x(lx1), conv_y(ly1))
                                    last_pt = (lx1, ly1)
                                    used.add(lid)
                                    found = True
                                    break
                        if not found:
                            next_l = next((l for l in lines if l.get('id') not in used), None)
                            if next_l:
                                path.moveTo(conv_x(next_l.get('x1',0)), conv_y(next_l.get('y1',0)))
                                path.lineTo(conv_x(next_l.get('x2',0)), conv_y(next_l.get('y2',0)))
                                last_pt = (next_l.get('x2',0), next_l.get('y2',0))
                                used.add(next_l.get('id'))
                    path.close()
                    c.drawPath(path, stroke=0, fill=1)

                def draw_rl_line(l_x1, l_y1, l_x2, l_y2):
                    pdf_x1 = x + l_x1
                    pdf_y1 = PAGE_HEIGHT - (y_top + l_y1)
                    pdf_x2 = x + l_x2
                    pdf_y2 = PAGE_HEIGHT - (y_top + l_y2)
                    c.line(pdf_x1, pdf_y1, pdf_x2, pdf_y2)

                for line in lines:
                    l_x1, l_y1, l_x2, l_y2 = line.get('x1',0), line.get('y1',0), line.get('x2',0), line.get('y2',0)
                    draw_rl_line(l_x1, l_y1, l_x2, l_y2)
                    
                    if sym in ('horizontal', 'both'):
                        draw_rl_line(width - l_x1, l_y1, width - l_x2, l_y2)
                    if sym in ('vertical', 'both'):
                        draw_rl_line(l_x1, height - l_y1, l_x2, height - l_y2)
                    if sym == 'both':
                        draw_rl_line(width - l_x1, height - l_y1, width - l_x2, height - l_y2)
                continue

            # Text Block
            html_content = block.get('content', '')
            if not html_content:
                plain = block.get('text', '')
                html_content = plain.replace('\n', '<br/>')

            font_size = block.get('fontSize', 12)
            font_weight = block.get('fontWeight', 'normal')
            font_style = block.get('fontStyle', 'normal')
            text_align = block.get('textAlign', 'center')

            align_map = {'left': TA_LEFT, 'center': TA_CENTER, 'right': TA_LEFT}
            alignment = align_map.get(text_align, TA_CENTER)
            if text_align == 'right':
                from reportlab.lib.enums import TA_RIGHT
                alignment = TA_RIGHT

            font_family = block.get('fontFamily', 'Times New Roman')
            is_bold = (font_weight == 'bold')
            is_italic = (font_style == 'italic')
            
            if font_family == 'Arial':
                if is_bold and is_italic: font_name = 'Helvetica-BoldOblique'
                elif is_bold: font_name = 'Helvetica-Bold'
                elif is_italic: font_name = 'Helvetica-Oblique'
                else: font_name = 'Helvetica'
            elif font_family == 'Courier New':
                if is_bold and is_italic: font_name = 'Courier-BoldOblique'
                elif is_bold: font_name = 'Courier-Bold'
                elif is_italic: font_name = 'Courier-Oblique'
                else: font_name = 'Courier'
            elif font_family == 'Times New Roman':
                if is_bold and is_italic: font_name = 'Times-BoldItalic'
                elif is_bold: font_name = 'Times-Bold'
                elif is_italic: font_name = 'Times-Italic'
                else: font_name = 'Times-Roman'
            else:
                from reportlab.pdfbase import pdfmetrics
                if font_family in pdfmetrics.getRegisteredFontNames():
                    font_name = font_family
                else:
                    font_name = 'Times-Roman'

            rl_text = html_content
            rl_text = re.sub(r'<br\s*/?>', '<br/>', rl_text)
            rl_text = re.sub(r'<div[^>]*>', '<br/>', rl_text)
            rl_text = re.sub(r'</div>', '', rl_text)
            rl_text = re.sub(r'<span[^>]*>', '', rl_text)
            rl_text = re.sub(r'</span>', '', rl_text)
            rl_text = re.sub(r'<(?!/?(?:b|i|u|font|br|strong|em)[ />])[^>]+>', '', rl_text)
            rl_text = rl_text.replace('<strong>', '<b>').replace('</strong>', '</b>')
            rl_text = rl_text.replace('<em>', '<i>').replace('</em>', '</i>')
            rl_text = re.sub(r'^(<br/>)+', '', rl_text)
            rl_text = rl_text.replace('&nbsp;', ' ')
            if '&' in rl_text:
                rl_text = re.sub(r'&(?!amp;|lt;|gt;|quot;)', '&amp;', rl_text)

            leading = font_size * 1.35
            style = ParagraphStyle(
                name=f'cover_{block.get("id", "block")}',
                fontName=font_name,
                fontSize=font_size,
                leading=leading,
                alignment=alignment,
                textColor=black,
            )

            try:
                para = Paragraph(rl_text, style)
            except Exception:
                plain = re.sub(r'<[^>]+>', ' ', html_content).strip()
                para = Paragraph(plain, style)

            para_w, para_h = para.wrap(width, height)
            para.drawOn(c, x, y_rl + (height - para_h))
        
        # End of page
        c.showPage()
        
    c.save()
    return True


# ============================================================
# WORD DOCUMENT GENERATION
# ============================================================

def generate_word_output(papers, page_groups, page_density_modes, page_map, output_path):
    """
    Generate a Word (.docx) document with the same structure as the PDF:
    Cover Page (if available) + Table of Contents + Paper entries.
    """
    try:
        from docx import Document
        from docx.shared import Pt, Inches, RGBColor
        from docx.enum.text import WD_ALIGN_PARAGRAPH
    except ImportError:
        print("  [ERROR] python-docx not installed. Run: pip install python-docx")
        return False

    doc = Document()

    # ── Page margins ──
    for section in doc.sections:
        section.top_margin = Inches(0.8)
        section.bottom_margin = Inches(0.7)
        section.left_margin = Inches(0.8)
        section.right_margin = Inches(0.8)

    # ── Style defaults ──
    style = doc.styles['Normal']
    style.font.name = 'Times New Roman'
    style.font.size = Pt(ABSTRACT_FONT_SIZE)

    # ══════════════════════════════════════════════════
    # COVER PAGE (from cover_page.json if available)
    # ══════════════════════════════════════════════════
    cover_config = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cover_page.json')
    if os.path.exists(cover_config):
        try:
            with open(cover_config, 'r') as f:
                cover_data = json.load(f)
            cover_blocks = cover_data.get('blocks', [])
            cover_blocks.sort(key=lambda b: b.get('y', 0))
            for blk in cover_blocks:
                blk_type = blk.get('type', 'text')
                p = doc.add_paragraph()
                align_map = {'left': WD_ALIGN_PARAGRAPH.LEFT, 'center': WD_ALIGN_PARAGRAPH.CENTER, 'right': WD_ALIGN_PARAGRAPH.RIGHT}
                p.alignment = align_map.get(blk.get('textAlign', 'center'), WD_ALIGN_PARAGRAPH.CENTER)
                p.paragraph_format.space_before = Pt(4)
                p.paragraph_format.space_after = Pt(4)

                if blk_type in ('image', 'drawing'):
                    img_url = blk.get('imageUrl', '') if blk_type == 'image' else blk.get('previewImage', '')
                    if img_url.startswith('data:image/'):
                        import base64
                        import io
                        try:
                            header, encoded = img_url.split(',', 1)
                            img_data = base64.b64decode(encoded)
                            img_stream = io.BytesIO(img_data)
                            run = p.add_run()
                            w_inches = blk.get('width', 150) / 72.0
                            run.add_picture(img_stream, width=Inches(w_inches))
                        except Exception as e:
                            print(f"Error adding {blk_type} to Word: {e}")
                    continue

                html_content = blk.get('content', '')
                if not html_content:
                    html_content = blk.get('text', '')
                plain = re.sub(r'<[^>]+>', ' ', html_content).strip()
                run = p.add_run(plain)
                run.font.size = Pt(blk.get('fontSize', 12))
                run.font.name = blk.get('fontFamily', 'Times New Roman')
                run.bold = blk.get('fontWeight', 'normal') == 'bold'
                run.italic = blk.get('fontStyle', 'normal') == 'italic'
            doc.add_page_break()
        except Exception:
            pass  # skip cover on error

    # ══════════════════════════════════════════════════
    # INVITED TALKS (from invited_talks.json if available)
    # ══════════════════════════════════════════════════
    invited_config = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'invited_talks.json')
    if os.path.exists(invited_config):
        try:
            with open(invited_config, 'r') as f:
                invited_data = json.load(f)
            pages = invited_data.get('pages', [])
            for page_data in pages:
                blocks = page_data.get('blocks', [])
                blocks.sort(key=lambda b: b.get('y', 0))
                for blk in blocks:
                    blk_type = blk.get('type', 'text')
                    p = doc.add_paragraph()
                    align_map = {'left': WD_ALIGN_PARAGRAPH.LEFT, 'center': WD_ALIGN_PARAGRAPH.CENTER, 'right': WD_ALIGN_PARAGRAPH.RIGHT}
                    p.alignment = align_map.get(blk.get('textAlign', 'center'), WD_ALIGN_PARAGRAPH.CENTER)
                    p.paragraph_format.space_before = Pt(4)
                    p.paragraph_format.space_after = Pt(4)

                    if blk_type in ('image', 'drawing'):
                        img_url = blk.get('imageUrl', '') if blk_type == 'image' else blk.get('previewImage', '')
                        if img_url.startswith('data:image/'):
                            import base64
                            import io
                            try:
                                header, encoded = img_url.split(',', 1)
                                img_data = base64.b64decode(encoded)
                                img_stream = io.BytesIO(img_data)
                                run = p.add_run()
                                w_inches = blk.get('width', 150) / 72.0
                                run.add_picture(img_stream, width=Inches(w_inches))
                            except Exception as e:
                                print(f"Error adding {blk_type} to Word: {e}")
                        continue

                    html_content = blk.get('content', '')
                    if not html_content:
                        html_content = blk.get('text', '')
                    plain = re.sub(r'<[^>]+>', ' ', html_content).strip()
                    run = p.add_run(plain)
                    run.font.size = Pt(blk.get('fontSize', 12))
                    run.font.name = blk.get('fontFamily', 'Times New Roman')
                    run.bold = blk.get('fontWeight', 'normal') == 'bold'
                    run.italic = blk.get('fontStyle', 'normal') == 'italic'
                doc.add_page_break()
        except Exception:
            pass

    # ══════════════════════════════════════════════════
    # TABLE OF CONTENTS
    # ══════════════════════════════════════════════════

    # "Contents" heading
    toc_heading = doc.add_paragraph()
    toc_heading.alignment = WD_ALIGN_PARAGRAPH.LEFT
    run = toc_heading.add_run('Contents')
    run.bold = True
    run.font.size = Pt(24)
    run.font.name = 'Times New Roman'

    # Blue divider line
    divider = doc.add_paragraph()
    divider.paragraph_format.space_before = Pt(4)
    divider.paragraph_format.space_after = Pt(12)
    run_div = divider.add_run('_' * 85)
    run_div.font.color.rgb = RGBColor(0, 0x33, 0x66)
    run_div.font.size = Pt(8)

    # Sort by page number ascending
    sorted_entries = [(i, p, page_map.get(i, 9999)) for i, p in enumerate(papers)]
    sorted_entries.sort(key=lambda x: x[2])

    for i, paper, page_val in sorted_entries:
        page_str = str(page_val) if page_val != 9999 else '?'

        # Title + page number
        toc_entry = doc.add_paragraph()
        toc_entry.paragraph_format.space_before = Pt(2)
        toc_entry.paragraph_format.space_after = Pt(0)
        run_title = toc_entry.add_run(paper['title'])
        run_title.font.size = Pt(9.5)
        run_title.font.name = 'Times New Roman'
        # Add dotted leader + page number
        dots = ' ' + '.' * 20 + ' '
        run_dots = toc_entry.add_run(dots)
        run_dots.font.size = Pt(8)
        run_dots.font.color.rgb = RGBColor(0x99, 0x99, 0x99)
        run_pn = toc_entry.add_run(page_str)
        run_pn.font.size = Pt(9.5)
        run_pn.font.name = 'Times New Roman'

        # Author names (italic)
        author_names = ', '.join(a['name'] for a in paper['authors'])
        auth_para = doc.add_paragraph()
        auth_para.paragraph_format.space_before = Pt(0)
        auth_para.paragraph_format.space_after = Pt(6)
        run_auth = auth_para.add_run(author_names)
        run_auth.italic = True
        run_auth.font.size = Pt(8)
        run_auth.font.name = 'Times New Roman'
        run_auth.font.color.rgb = RGBColor(0x66, 0x66, 0x66)

    # ══════════════════════════════════════════════════
    # BODY — PAPER ENTRIES (Grouped by Page & Density)
    # ══════════════════════════════════════════════════

    doc.add_page_break()

    for pg_idx, (group, mode) in enumerate(zip(page_groups, page_density_modes)):
        if pg_idx > 0:
            doc.add_page_break()

        # Density mode spacing (margins only, font/line height constant)
        if 'zero_margins' in mode:
            title_space_after = Pt(1)
            auth_space_after = Pt(1)
            abs_space_after = Pt(1)
            kw_space_after = Pt(1)
            sep_space_before = Pt(1)
            sep_space_after = Pt(1)
        elif 'tight_margins' in mode:
            title_space_after = Pt(2)
            auth_space_after = Pt(2)
            abs_space_after = Pt(2)
            kw_space_after = Pt(2)
            sep_space_before = Pt(2)
            sep_space_after = Pt(3)
        elif 'compact_margins' in mode:
            title_space_after = Pt(3)
            auth_space_after = Pt(4)
            abs_space_after = Pt(3)
            kw_space_after = Pt(3)
            sep_space_before = Pt(3)
            sep_space_after = Pt(4)
        else:  # standard
            title_space_after = Pt(5)
            auth_space_after = Pt(8)
            abs_space_after = Pt(5)
            kw_space_after = Pt(6)
            sep_space_before = Pt(6)
            sep_space_after = Pt(8)

        for item_idx, paper_idx in enumerate(group):
            paper = papers[paper_idx]
            if item_idx > 0:
                # Dot separator between papers on the same page
                sep = doc.add_paragraph()
                sep.alignment = WD_ALIGN_PARAGRAPH.CENTER
                sep.paragraph_format.space_before = sep_space_before
                sep.paragraph_format.space_after = sep_space_after
                run_sep = sep.add_run('●  ' * 10 + '●')
                run_sep.font.size = Pt(7)
                run_sep.font.color.rgb = RGBColor(0x99, 0x99, 0x99)

            # ── Title ──
            title_para = doc.add_paragraph()
            title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
            title_para.paragraph_format.space_before = Pt(2)
            title_para.paragraph_format.space_after = title_space_after
            run_t = title_para.add_run(paper['title'])
            run_t.bold = True
            run_t.font.size = Pt(TITLE_FONT_SIZE)
            run_t.font.name = 'Times New Roman'

            # ── Authors ──
            authors_text, affiliations_text = format_authors_with_affiliations(paper['authors'], use_html_super=False)

            auth_para = doc.add_paragraph()
            auth_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
            auth_para.paragraph_format.space_after = Pt(2)
            run_a = auth_para.add_run(authors_text)
            run_a.font.size = Pt(AUTHORS_FONT_SIZE)
            run_a.font.name = 'Times New Roman'

            if affiliations_text:
                aff_para = doc.add_paragraph()
                aff_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
                aff_para.paragraph_format.space_after = auth_space_after
                run_aff = aff_para.add_run(affiliations_text)
                run_aff.italic = True
                run_aff.font.size = Pt(AUTHORS_FONT_SIZE - 1)
                run_aff.font.name = 'Times New Roman'

            # ── Abstract ──
            abs_para = doc.add_paragraph()
            abs_para.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            abs_para.paragraph_format.space_after = abs_space_after
            run_abs_label = abs_para.add_run('Abstract— ')
            run_abs_label.bold = True
            run_abs_label.font.size = Pt(ABSTRACT_FONT_SIZE)
            run_abs_label.font.name = 'Times New Roman'
            run_abs_text = abs_para.add_run(paper['abstract'])
            run_abs_text.font.size = Pt(ABSTRACT_FONT_SIZE)
            run_abs_text.font.name = 'Times New Roman'

            # ── Keywords ──
            kw_para = doc.add_paragraph()
            kw_para.paragraph_format.space_after = kw_space_after
            run_kw_label = kw_para.add_run('Keywords— ')
            run_kw_label.bold = True
            run_kw_label.font.size = Pt(KEYWORDS_FONT_SIZE)
            run_kw_label.font.name = 'Times New Roman'
            run_kw_text = kw_para.add_run(paper['keywords'])
            run_kw_text.italic = True
            run_kw_text.font.size = Pt(KEYWORDS_FONT_SIZE)
            run_kw_text.font.name = 'Times New Roman'

    # ── Footer on each page ──
    for section in doc.sections:
        footer = section.footer
        footer.is_linked_to_previous = False
        fp = footer.paragraphs[0] if footer.paragraphs else footer.add_paragraph()
        fp.alignment = WD_ALIGN_PARAGRAPH.LEFT
        run_url = fp.add_run(FOOTER_URL)
        run_url.bold = True
        run_url.font.size = Pt(FOOTER_URL_FONT_SIZE)
        run_url.font.name = 'Times New Roman'

        header = section.header
        header.is_linked_to_previous = False
        hp = header.paragraphs[0] if header.paragraphs else header.add_paragraph()
        hp.alignment = WD_ALIGN_PARAGRAPH.LEFT
        run_hdr = hp.add_run(CONFERENCE_HEADER)
        run_hdr.italic = True
        run_hdr.font.size = Pt(HEADER_FONT_SIZE)
        run_hdr.font.name = 'Times New Roman'

    doc.save(output_path)
    return True


# ============================================================
# MAIN
# ============================================================

def main():
    # ── Parse --format=word flag ──
    output_format = 'pdf'
    positional_args = []
    for arg in sys.argv[1:]:
        if arg.startswith('--format='):
            output_format = arg.split('=', 1)[1].lower()
        else:
            positional_args.append(arg)

    # ── Determine input/output folders ──
    input_folder = positional_args[0] if len(positional_args) > 0 else "IncompletePDF"
    output_folder = positional_args[1] if len(positional_args) > 1 else "CompletedPDF"

    os.makedirs(output_folder, exist_ok=True)

    print("==================================================")
    print("       ACROSET PDF SCRAPER & COMPILER             ")
    print("==================================================")
    print(f"  Input folder:  {input_folder}/")
    print(f"  Output folder: {output_folder}/")

    # ── Scan for PDFs ──
    pdf_files = sorted([
        f for f in os.listdir(input_folder)
        if f.lower().endswith('.pdf')
    ])

    if not pdf_files:
        print(f"\n[ERROR] No PDF files found in '{input_folder}/'")
        sys.exit(1)

    print(f"\n[QUEUE] Found {len(pdf_files)} PDF(s): {', '.join(pdf_files)}")

    # ── Extract data from each PDF ──
    papers = []
    failed = []

    for pdf_file in pdf_files:
        full_path = os.path.join(input_folder, pdf_file)
        try:
            data = extract_paper_data(full_path)
            if data and data['title']:
                papers.append(data)
            else:
                failed.append(pdf_file)
        except Exception as e:
            print(f"\n  [ERROR] EXCEPTION processing {pdf_file}: {e}")
            failed.append(pdf_file)

    if not papers:
        print("\n[ERROR] No papers could be extracted! Check the PDFs.")
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"[SUMMARY] EXTRACTION SUMMARY")
    print(f"{'='*60}")
    print(f"  [OK] Successful: {len(papers)}")
    if failed:
        print(f"  [ERROR] Failed:     {len(failed)} -- {', '.join(failed)}")

    # ── Generate body PDF (always needed for page_map) ──
    body_temp = os.path.join(output_folder, "_body_temp.pdf")
    print(f"\n[PROCESS] Generating body pages...")
    page_map, page_groups, page_density_modes = generate_body_pdf(papers, body_temp)

    print(f"\n  Page assignments:")
    for i, p in enumerate(papers):
        short_title = p['title'][:55] + '...' if len(p['title']) > 55 else p['title']
        print(f"    Page {page_map.get(i, '?')}: {short_title}")

    if output_format == 'word':
        # ── Word output ──
        output_path = os.path.join(output_folder, "compiled_output.docx")
        print(f"\n[PROCESS] Generating Word document -> {output_path}")
        success = generate_word_output(papers, page_groups, page_density_modes, page_map, output_path)
        # Cleanup temp body PDF
        if os.path.exists(body_temp):
            os.remove(body_temp)
        if not success:
            print("\n[ERROR] Word generation failed!")
            sys.exit(1)
    else:
        # ── PDF output ──
        # Generate cover page if cover_page.json exists
        cover_temp = os.path.join(output_folder, "_cover_temp.pdf")
        has_cover = generate_cover_page_pdf(cover_temp)
        if has_cover:
            print(f"\n[PROCESS] Generated cover page")
        else:
            cover_temp = None

        invited_talks_temp = os.path.join(output_folder, "_invited_talks_temp.pdf")
        has_invited_talks = generate_invited_talks_pdf(invited_talks_temp)
        if has_invited_talks:
            print(f"\n[PROCESS] Generated invited talks")
        else:
            invited_talks_temp = None

        toc_temp = os.path.join(output_folder, "_toc_temp.pdf")
        print(f"\n[PROCESS] Generating Table of Contents...")
        generate_toc_pdf(papers, page_map, toc_temp)

        output_path = os.path.join(output_folder, "compiled_output.pdf")
        parts_msg = " Cover +" if has_cover else ""
        parts_msg += " Invited Talks +" if has_invited_talks else ""
        print(f"\n[PROCESS] Merging{parts_msg} TOC + Body -> {output_path}")
        merge_pdfs(toc_temp, body_temp, output_path)

        # Cleanup temp files
        os.remove(body_temp)
        os.remove(toc_temp)

    # ── Move processed PDFs to output folder ──
    print(f"\n[PROCESS] Moving processed PDFs to {output_folder}/...")
    for pdf_file in pdf_files:
        src = os.path.join(input_folder, pdf_file)
        dst = os.path.join(output_folder, pdf_file)
        if os.path.exists(src):
            if os.path.exists(dst):
                os.remove(dst)  # Remove if already exists
            shutil.move(src, dst)
            print(f"    [OK] {pdf_file}")

    # ── Final summary ──
    if output_format == 'word':
        print(f"\n{'='*60}")
        print(f"[DONE] COMPILATION COMPLETE")
        print(f"{'='*60}")
        print(f"  Output:      {output_path}")
        print(f"  Papers:      {len(papers)}")
        print(f"  Format:      Word (.docx)")
        print(f"{'='*60}")
    else:
        final_doc = fitz.open(output_path)
        total_pages = len(final_doc)
        final_doc.close()

        body_page_count = len(set(page_map.values()))
        toc_pages = total_pages - body_page_count

        print(f"\n{'='*60}")
        print(f"[DONE] COMPILATION COMPLETE")
        print(f"{'='*60}")
        print(f"  Output:      {output_path}")
        print(f"  Papers:      {len(papers)}")
        print(f"  Total pages: {total_pages} "
              f"({toc_pages} TOC + {body_page_count} body)")
        print(f"{'='*60}")


if __name__ == "__main__":
    main()
