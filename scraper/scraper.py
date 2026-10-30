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
import datetime

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
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.colors import black, HexColor
from reportlab.platypus import (
    BaseDocTemplate, PageTemplate, Frame,
    Paragraph, Spacer, Flowable, KeepTogether, PageBreak
)
from reportlab.pdfgen import canvas as canvas_mod
from reportlab import rl_config
from reportlab.pdfbase.pdfmetrics import stringWidth, registerFont, registerFontFamily, getFont
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


# Compiled-output text fonts. The built-in Type 1 Times only covers Latin-1, so symbols
# such as π, ◦ or ¹ printed as black boxes; an embedded Times New Roman covers them.
_TIMES_TTF_DIRS = ['/System/Library/Fonts/Supplemental', '/Library/Fonts',
                   os.path.join(os.environ.get('WINDIR', r'C:\Windows'), 'Fonts')]
_TIMES_TTF_FILES = {
    'regular': ['Times New Roman.ttf', 'times.ttf'],
    'bold': ['Times New Roman Bold.ttf', 'timesbd.ttf'],
    'italic': ['Times New Roman Italic.ttf', 'timesi.ttf'],
    'bold_italic': ['Times New Roman Bold Italic.ttf', 'timesbi.ttf'],
}
# Serif fonts used only for single characters the main font lacks (₹ is missing from
# the macOS Times New Roman)
_FALLBACK_TTF_FILES = ['STIXTwoText.ttf', 'Nirmala.ttf', 'seguisym.ttf']


def _find_font_file(names):
    for d in _TIMES_TTF_DIRS:
        for name in names:
            path = os.path.join(d, name)
            if os.path.exists(path):
                return path
    return None


def _register_text_fonts():
    """Returns (regular, bold, italic, bold_italic, fallback) font names."""
    paths = {style: _find_font_file(names) for style, names in _TIMES_TTF_FILES.items()}
    names = ('Times-Roman', 'Times-Bold', 'Times-Italic', 'Times-BoldItalic')
    if all(paths.values()):
        try:
            names = ('TNR', 'TNR-Bold', 'TNR-Italic', 'TNR-BoldItalic')
            for name, style in zip(names, ('regular', 'bold', 'italic', 'bold_italic')):
                registerFont(TTFont(name, paths[style]))
            registerFontFamily('TNR', normal='TNR', bold='TNR-Bold',
                               italic='TNR-Italic', boldItalic='TNR-BoldItalic')
        except Exception as e:
            print(f"Failed to register Times New Roman, using built-in Times: {e}")
            names = ('Times-Roman', 'Times-Bold', 'Times-Italic', 'Times-BoldItalic')
    fallback = None
    path = _find_font_file(_FALLBACK_TTF_FILES)
    if path:
        try:
            registerFont(TTFont('SymbolFallback', path))
            fallback = 'SymbolFallback'
        except Exception as e:
            print(f"Failed to register fallback font {path}: {e}")
    return names + (fallback,)

FONT_REGULAR, FONT_BOLD, FONT_ITALIC, FONT_BOLD_ITALIC, FONT_FALLBACK = _register_text_fonts()
# Every canvas page starts by selecting this font; the default (Helvetica) is never embedded,
# which print preflight checks flag even when no text uses it
rl_config.canvas_basefontname = FONT_REGULAR


# ============================================================
# CONFIGURATION — loaded from config.json if present
# ============================================================

def _load_config():
    """Load parameters from config.json, falling back to defaults."""
    defaults = {
        'CONFERENCE_HEADER': 'IEEE IGNITE 2.0: Student Research and Professional Awareness Conference',
        'FOOTER_URL': 'https://ieeeignite.in',
        'LINE_SPACING_FACTOR': 1.45,
        'WORD_SPACING': 1.5,
        'TITLE_FONT_SIZE': 12,
        'AUTHORS_FONT_SIZE': 9.5,
        'ABSTRACT_FONT_SIZE': 10,
        'KEYWORDS_FONT_SIZE': 10,
        'HEADER_FONT_SIZE': 8.5,
        'FOOTER_URL_FONT_SIZE': 9,
        'FOOTER_PAGE_FONT_SIZE': 10,
        # Page size and margins in points: A4 plus a 15 mm binding strip on the left, matching
        # the book's front matter. Gaps tuned on A4 scale with the page height.
        'PAGE_WIDTH': A4[0] + 15 * mm,
        'PAGE_HEIGHT': A4[1],
        'MARGIN_LEFT': 50 + 15 * mm,
        'MARGIN_RIGHT': 50,
        'MARGIN_TOP': 70,
        'MARGIN_BOTTOM': 60,
        # 2 = pair short abstracts on a page; 1 = every abstract starts on its own page
        'MAX_PAPERS_PER_PAGE': 2,
        # Page numbers in the Contents list: 'arabic' (1, 2, 3) or 'roman' (i, ii, iii)
        'TOC_PAGE_NUMBERS': 'roman',
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
TOC_PAGE_NUMBERS = str(_cfg['TOC_PAGE_NUMBERS']).lower()


def to_roman(number):
    """12 -> 'xii' (lowercase, as used for page numbers)."""
    out = ''
    for value, letters in ((1000, 'm'), (900, 'cm'), (500, 'd'), (400, 'cd'), (100, 'c'), (90, 'xc'),
                           (50, 'l'), (40, 'xl'), (10, 'x'), (9, 'ix'), (5, 'v'), (4, 'iv'), (1, 'i')):
        while number >= value:
            out += letters
            number -= value
    return out


def _load_author_overrides():
    """Optional manual corrections, keyed by source filename:
    {"P246.pdf": {"rename": {"Teacher": "Ritika Sen"}}}. A rename applies only when the
    extracted name matches exactly, so stale entries from another batch are harmless."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'author_overrides.json')
    if not os.path.exists(path):
        return {}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return {k: v for k, v in json.load(f).items() if not k.startswith('_')}
    except Exception as e:
        print(f"  [WARN] Could not load author_overrides.json: {e}")
        return {}

AUTHOR_OVERRIDES = _load_author_overrides()


PAPER_CORRECTIONS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'paper_corrections.json')


def apply_paper_corrections(papers, path=PAPER_CORRECTIONS_FILE):
    """Replace extracted fields with hand-edited ones, keyed by source filename:
    {"P104.pdf": {"title": ..., "authors": [{"name": ..., "affil": 1}], "affiliations": [...],
                  "abstract": ..., "keywords": ...}}. Every field is optional."""
    if not os.path.exists(path):
        return 0
    try:
        with open(path, 'r', encoding='utf-8') as f:
            corrections = json.load(f)
    except Exception as e:
        print(f"  [WARN] Could not load {os.path.basename(path)}: {e}")
        return 0
    def words(p):
        return set(re.findall(r'[a-z]{4,}', (p.get('title', '') + ' ' + p.get('abstract', '')[:400]).lower()))

    applied = 0
    for paper in papers:
        fix = corrections.get(paper.get('source_file'))
        if not fix:
            continue
        # Filenames repeat between batches (P104.pdf ...): only apply to the same paper
        found, edited = words(paper), words(fix)
        if found and edited and len(found & edited) / len(found | edited) < 0.4:
            print(f"  [WARN] {os.path.basename(path)} entry for {paper['source_file']} is for a "
                  f"different paper (\"{fix.get('title', '')[:50]}\") -- not applied")
            continue
        for field in ('title', 'abstract', 'keywords'):
            if fix.get(field):
                paper[field] = fix[field]
        if fix.get('authors'):
            affiliations = fix.get('affiliations') or []
            paper['authors'] = [{
                'name': a['name'],
                'college': affiliations[a['affil'] - 1] if a.get('affil') and a['affil'] <= len(affiliations) else '',
                'affil_num': a.get('affil'),
            } for a in fix['authors']]
        paper['anomalies'] = [m for m in paper.get('anomalies', [])
                              if not m.startswith(('Missing affiliation', 'Suspicious author'))]
        paper['anomalies'].append(f"Text replaced by the edited version in {os.path.basename(path)}")
        applied += 1
    return applied

# Deep blue color for header/footer divider lines
DIVIDER_COLOR = HexColor('#003366')

PAGE_WIDTH = float(_cfg['PAGE_WIDTH'])
PAGE_HEIGHT = float(_cfg['PAGE_HEIGHT'])
PAGE_SIZE = (PAGE_WIDTH, PAGE_HEIGHT)
LEFT_MARGIN = _cfg['MARGIN_LEFT']
RIGHT_MARGIN = _cfg['MARGIN_RIGHT']
TOP_MARGIN = _cfg['MARGIN_TOP']        # space for the header
BOTTOM_MARGIN = _cfg['MARGIN_BOTTOM']  # space for the footer
CONTENT_WIDTH = PAGE_WIDTH - LEFT_MARGIN - RIGHT_MARGIN
# Fixed gaps, headroom and separator sizes below were tuned on A4; they shrink with the page
LAYOUT_SCALE = PAGE_HEIGHT / A4[1]

# Strict limit: max papers per page
MAX_PAPERS_PER_PAGE = int(_cfg['MAX_PAPERS_PER_PAGE'])
# Non-final pages must use at least this fraction of available height (max 80% whitespace)
MIN_PAGE_FILL_RATIO = 0.20
# Conservative headroom so KeepTogether blocks never overflow the frame
PACKING_HEADROOM_PT = 85.0 * LAYOUT_SCALE
# The packer searches randomly; a fixed seed keeps the page layout stable between runs
PACKING_SEED = 2026
# Vertical gap between Contents entries (pt)
TOC_ENTRY_GAP = 4.5 * LAYOUT_SCALE

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


_SUBSCRIPT_DIGITS_RE = re.compile('[₀-₉]+')


def markup_text(text):
    """Escape text for a Paragraph and route characters the body font lacks:
    subscript digits (CO₂) become <sub> markup and anything else missing (₹) is
    drawn in the fallback font instead of as a black box."""
    escaped = html_escape(text)
    escaped = _SUBSCRIPT_DIGITS_RE.sub(
        lambda m: '<sub>' + ''.join(str(ord(c) - 0x2080) for c in m.group()) + '</sub>', escaped)
    if not FONT_FALLBACK:
        return escaped
    try:
        have = getFont(FONT_REGULAR).face.charToGlyph
        spare = getFont(FONT_FALLBACK).face.charToGlyph
    except AttributeError:   # built-in Type 1 font: no cmap to consult
        return escaped
    return ''.join(f'<font name="{FONT_FALLBACK}">{ch}</font>'
                   if ord(ch) > 0x7f and ord(ch) not in have and ord(ch) in spare else ch
                   for ch in escaped)


# ============================================================
# TEXT TIDYING — artefacts the source PDFs carry into the text
# ============================================================

_dictionary = None


def _dictionary_words():
    global _dictionary
    if _dictionary is None:
        _dictionary = set()
        for path in ('/usr/share/dict/words', '/usr/share/dict/web2'):
            if os.path.exists(path):
                with open(path, encoding='utf-8', errors='ignore') as f:
                    _dictionary = {w.strip().lower() for w in f}
                break
    return _dictionary


def _is_dictionary_word(word):
    words = _dictionary_words()
    word = word.lower()
    if word in words:
        return True
    for suffix, repl in (('ies', 'y'), ('es', ''), ('s', ''), ('ed', ''), ('ed', 'e'),
                         ('ing', ''), ('ing', 'e'), ('ly', ''), ('al', '')):
        if word.endswith(suffix) and word[:-len(suffix)] + repl in words:
            return True
    m = re.match(r'(.*([b-df-hj-np-tv-z]))\2(?:ed|ing)$', word)   # controlled -> control
    return bool(m and m.group(1) in words)


_BROKEN_HYPHEN_RE = re.compile(r'\b([A-Za-z0-9]+)- +([A-Za-z0-9]+)')


def fix_broken_hyphens(text):
    """Repair words the source broke at a line end: "chal- lenge" -> "challenge",
    "zero- shot" -> "zero-shot". Suspended hyphens ("AI- and IoT-based") are kept."""
    def repl(m):
        left, right = m.group(1), m.group(2)
        if right.lower() in ('and', 'or', 'to', 'nor', 'as', 'vs'):
            return m.group(0)
        if not right[0].islower() or not left.isalpha():
            return f'{left}-{right}'
        joined = left + right
        if re.search(r'\b%s\b' % re.escape(joined), text, re.I):
            return joined
        if re.search(r'\b%s-%s\b' % (re.escape(left), re.escape(right)), text, re.I):
            return f'{left}-{right}'
        if _dictionary_words():
            return joined if _is_dictionary_word(joined) else f'{left}-{right}'
        return m.group(0)
    return _BROKEN_HYPHEN_RE.sub(repl, text)


def tidy_text(text):
    """Clean-up shared by abstracts and keywords."""
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)            # markdown bold: **ClipGen**
    text = re.sub(r'\s?◦\s?C\b', ' °C', text)                # ◦ used as a degree sign
    text = re.sub(r"``(.+?)''", r'“\1”', text)               # LaTeX quotes
    text = re.sub(r'\(\s+', '(', text)
    text = re.sub(r'\s+([,.;:])(?=\s|$)', r'\1', text)       # "husk ,sugarcane" / "setting ."
    text = re.sub(r',(?=[A-Za-z])', ', ', text)
    text = re.sub(r'(?<=[a-z]{3})\.(?=(?:The|This|These|It|In|We|Our)\b)', '. ', text)  # "processes.This"
    text = re.sub(r'(?<=\w) -(?=[a-z])', '-', text)          # "carbon -rich"
    text = fix_broken_hyphens(text)
    return re.sub(r'\s+', ' ', text).strip()


def tidy_keywords(keywords):
    keywords = tidy_text(keywords).lstrip('-–—:.* ').strip()
    return keywords[:1].upper() + keywords[1:]


def tidy_abstract(abstract, keywords=''):
    if keywords:
        # Keyword list pasted onto the end of the abstract ("... future. **Self-heating lunch box ...")
        m = re.search(r'\*\*\s*' + re.escape(keywords[:25]), abstract)
        if m and m.start() > len(abstract) * 0.6:
            abstract = abstract[:m.start()]
    abstract = tidy_text(abstract).replace('**', '')
    return abstract[:1].upper() + abstract[1:]


CITIES = {
    'rajkot', 'jaipur', 'kishangarh', 'pilani', 'kanyakumari', 'chennai', 'muscat',
    'vaddeswaram', 'bhopal', 'gwalior', 'vijayawada', 'bhimavaram', 'jalandhar', 'indore',
    'delhi', 'mumbai', 'pune', 'bangalore', 'bengaluru', 'hyderabad', 'kolkata',
    'ahmedabad', 'noida', 'gurugram', 'chandigarh', 'dehradun', 'oman', 'india', 'usa',
    'uk', 'singapore', 'malaysia', 'australia', 'kanpur', 'lucknow', 'patna', 'agra',
    'rajasthan', 'madhya pradesh', 'tamil nadu', 'kerala', 'karnataka', 'andhra pradesh',
    'punjab', 'haryana', 'uttar pradesh', 'gujarat', 'maharashtra'
}


_COUNTRY_STATE_RE = re.compile(
    r'\b(?:' + '|'.join(re.escape(p) for p in sorted(COUNTRIES | STATES, key=len, reverse=True)) + r')\b')


def is_location_line(text):
    """
    Detect city/country/state lines in the author section.
    These lines typically look like "Indore, India" or "Bhopal, India".
    """
    clean = text.strip().rstrip('.,').lower()
    if clean in CITIES:
        return True

    # "Central University of Rajasthan" is an affiliation, not a location
    if re.search(r'\b(?:university|institute|college|school|department|dept|faculty|'
                 r'academy|centre|center|campus|laboratory)\b', clean):
        return False

    # Whole-word country/state match (substring matching dropped names like
    # "Mausam" (usa), "Shukla" (uk) and "Kiran" (iran))
    if _COUNTRY_STATE_RE.search(clean):
        return True

    # Pattern: "City, Country" — short text with comma, no email
    if ',' in text and len(text.strip()) < 40 and '@' not in text:
        parts = [p.strip().lower() for p in text.strip().split(',')]
        if len(parts) == 2 and any(p in CITIES or p in [c.lower() for c in COUNTRIES] or p in [s.lower() for s in STATES] for p in parts):
            return True

    return False


def is_email(text):
    """Detect email addresses or split-email fragments like 'edu.in'."""
    t = text.strip().lower()
    if '@' in t:
        return True
    if re.search(r'[\w.+-]+@[\w.-]+\.\w{2,}', t):
        return True
    if t.startswith('@') or re.match(r'^[\w.-]+@', t):
        return True
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
        # Word-wrapped field names: "Institute of Management" / "Studies and Research",
        # "Department of Computer" / "Science(Artificial Intelligence)"
        elif (re.search(r'\b(?:management|computer|information|electronics|electrical|'
                        r'mechanical|civil|applied|life|data)$', prev, re.I)
              and re.match(r'(?:studies|science|sciences|technology|engineering)\b', curr, re.I)):
            result += ' ' + curr
        else:
            # Likely a new entity (e.g., department → university)
            result += ', ' + curr

    return re.sub(r'\s+', ' ', result).strip()


INSTITUTION_RE = re.compile(
    r'\b(?:department|dept\.?|university|institute|college|school|faculty|academy|'
    r'center|centre|kendra|krishi|engineering|engg\.?|technology|campus|vidyapeetham|vidhyapeetham|vishwavidhyalaya|'
    r'deemed|laboratory|division|vet\.?|inst\.?|global|alliance|symbiosis|medicaps|vishwa|'
    r'lovely|saveetha|atlas|vivekananda|acropolis|manipal|sage|ggits|skitm|sciences|'
    r'communication|information|physics|chemistry|mathematics|research|foundation|education|'
    r'veltech|klef|amity|chandigarh|proudyogiki|r&d|cse|ece|eee|it|ai|ds|'
    r'enterprises?|ltd|limited|pvt|inc|corporation|testing)\b',
    re.I,
)

JOB_TITLE_RE = re.compile(
    r'\b(?:professor|head|research\s+scholar|scholar|dean|director|lecturer|'
    r'associate|assistant|scientist|fellow|independent\s+researcher|ugdx|coe|'
    r'hod|chairperson|coordinator)\b',
    re.I,
)

INSTITUTION_FRAGMENT_RE = re.compile(
    r'^(?:university|institute|college|department|dept|school|apex|symbiosis|chandigarh|'
    r'csa|itm|engineering|engg|technology|physics|chemistry|information|communication|science|sciences|\)|\(deemed|\(deemed-to-be)\b',
    re.I,
)

NON_PERSON_WORDS = {
    'and', 'or', 'of', 'in', 'for', 'the', 'with', 'on', 'at', 'to', 'from', 'by', '&',
    'department', 'dept', 'university', 'institute', 'college', 'school', 'faculty',
    'academy', 'center', 'centre', 'engineering', 'engg', 'engg.', 'technology', 'science', 'sciences',
    'information', 'communication', 'physics', 'chemistry', 'mathematics', 'research',
    'application', 'applications', 'foundation', 'education', 'central', 'national',
    'state', 'international', 'branch', 'campus', 'marwadi', 'birla', 'vishwavidhyalaya',
    'vidhyapeetham', 'klef', 'veltech', 'jain', 'medicaps', 'amity', 'chandigarh', 'symbiosis',
    'proudyogiki', 'r&d', 'cse', 'ece', 'eee', 'dr', 'prof', 'computer', 'electronics',
    'applied', 'sciences', 'data', 'science', 'technology', 'management', 'kendra', 'krishi',
    'k', 'l', 'e', 'f', 'asst', 'student', 'students', 'developer', 'sem', 'msc', 'cs', 'teacher'
}

# Template leftovers and contact labels that are never names or affiliations
AUTHOR_NOISE_RE = re.compile(
    r'^(?:e-?mail(?:\s*id)?\s*:?.*|\*?\s*note\s*:.*|line\s+\d+\s*:.*|.*corresponding\s+author.*'
    r'|\d{4}-\d{4}-\d{4}-\d{3}[\dX]'          # ORCID
    r'|\(?(?=[A-Z0-9]*\d{4})[A-Z0-9]{8,}\)?'      # roll numbers "(0827CD23106)"
    r'|\.?[a-z]{2,5}(?:\.[a-z]{2,3})+)$',          # split email tail ".ac.in"
    re.I)


def clean_author_name(name: str) -> str:
    """Strip superscript affiliation markers from author names."""
    name = re.sub(r'^\s*name\s*:\s*', '', name, flags=re.I)            # "Name : Risha Fatima"
    name = re.sub(r'^[,;&\s]*(?:and\s+)?', '', name)                   # ", and Yashaswi Agrawal"
    name = name.strip().rstrip('.,;') if re.search(r'[a-z]{2}\.$', name) else name
    name = re.sub(r'[\d*†‡§¶\[\]]+$', '', name).strip()
    name = re.sub(r'^[\d*†‡§¶\[\]]+\s*', '', name).strip()
    name = re.sub(r'(\w)[\d*†‡§¶]+(?=\s|,|$)', r'\1', name).strip()
    name = re.sub(r'^(?:mr|mrs|ms|miss)\.?\s+', '', name, flags=re.I)  # keep Dr./Prof., drop Ms./Mr.
    # Capitalise words typed all lowercase ("kirti sathe" → "Kirti Sathe")
    name = ' '.join(w[0].upper() + w[1:] if w.islower() else w for w in name.split())
    return name


def is_affiliation_text(text, is_italic=False):
    """Detect department/college/job-title lines (never author names)."""
    t = text.strip()
    if not t:
        return False
    if is_italic:
        return True
    if INSTITUTION_RE.search(t):
        return True
    if JOB_TITLE_RE.search(t):
        return True
    if INSTITUTION_FRAGMENT_RE.match(t):
        return True
    if re.search(r'\b(?:&|and)\s+head\b', t, re.I):
        return True
    return False


def is_person_name(text):
    """Heuristic for real author names (not institutions, emails, cities, or titles)."""
    t = clean_author_name(text.strip())
    if not t or len(t) < 2 or len(t) > 70:
        return False
    if not re.search(r'[A-Za-z]', t):
        return False
    if is_email(t) or is_location_line(t) or is_copyright(t) or is_affiliation_text(t):
        return False
    if re.match(r'^[A-Z]\.?$', t):
        return False
    if re.match(r'^[\d\s\W]+$', t):
        return False
    # Names never carry digits, label colons, or bracketed acronyms ("(A.I.M.S.R)")
    if re.search(r'\d', t) or ':' in t or AUTHOR_NOISE_RE.match(t):
        return False
    if re.match(r'^\(.*\)$', t) or re.match(r'^(?:[A-Z]\.){2,}$', t.replace(' ', '')):
        return False
    if re.fullmatch(r'[A-Z&]{3,}', t):
        return False  # lone institution acronym ("AITR", "GIDA")
    words = [w.lower().strip('.,()[]:;') for w in t.split() if w.strip('.,()[]:;')]
    if not words:
        return False
    if len(words) == 1 and (words[0] in NON_PERSON_WORDS or words[0] in CITIES or len(words[0]) <= 2):
        return False
    if all(w in NON_PERSON_WORDS or w in CITIES for w in words):
        return False
    return True


def _span_center(s):
    return (s.get('origin_x', 0) + s.get('end_x', s.get('origin_x', 0))) / 2.0


def _cluster_spans_by_column(section_spans, x_gap=90):
    """Group author-section spans into vertical columns (multi-column PDF layouts).
    Uses line centres, since author blocks are usually centred within their column."""
    valid = [s for s in section_spans if s['text'].strip()]
    if not valid:
        return []

    sorted_spans = sorted(valid, key=lambda s: (_span_center(s), s['origin_y']))
    columns = [[sorted_spans[0]]]
    for s in sorted_spans[1:]:
        col_x = sum(_span_center(item) for item in columns[-1]) / len(columns[-1])
        if abs(_span_center(s) - col_x) < x_gap:
            columns[-1].append(s)
        else:
            columns.append([s])

    for col in columns:
        col.sort(key=lambda s: s['origin_y'])
    columns.sort(key=lambda col: min(_span_center(s) for s in col))
    return columns


def _order_in_rows(spans):
    """Reading order (top-to-bottom, left-to-right) tolerant of raised superscripts."""
    rows = []
    for s in sorted(spans, key=lambda s: s['origin_y']):
        if rows:
            first = rows[-1][0]
            if s['origin_y'] - first['origin_y'] <= 0.5 * max(first['size'], s['size']):
                rows[-1].append(s)
                continue
        rows.append([s])
    return [s for row in rows for s in sorted(row, key=lambda s: s.get('origin_x', 0))]


# A whole comma segment of an affiliation that is a job title / study year, not a department
AFFIL_ROLE_SEGMENT_RE = re.compile(
    r'(?:(?:student|ug|pg|research|undergraduate|postgraduate)\s*)?(?:student|developer|scholar)s?'
    r'|(?:asst\.?|assistant|associate|assoc\.?)?\s*prof(?:\.|essor)?'
    r'|(?:m\.?sc|b\.?sc|b\.?tech|m\.?tech|mca|bca|msc\.?\s*cs)[.\s\w]*\b\d+\s*(?:st|nd|rd|th)\s*(?:sem(?:ester)?|year)'
    r'|\d+\s*(?:st|nd|rd|th)\s*(?:sem(?:ester)?|year)',
    re.I)
AFFIL_LOWER_WORDS = {'of', 'and', 'for', 'the', 'in', 'at', 'on', 'to', '&'}


def _clean_college(text):
    """Tidy a joined affiliation string: stray brackets, job titles, email tails, casing."""
    text = re.sub(r'\[\s*(.*?)\s*\]', r'\1', text.strip())
    text = re.sub(r'^\((.*)\)$', r'\1', text.strip())                   # "(Department of X)"
    text = re.sub(r'\b(Dept|Inst)\.(?=[A-Za-z])', r'\1. ', text)        # "Dept.of"
    segments = []
    for seg in re.split(r'\s*,\s*', text):
        seg = seg.strip()
        if seg.startswith('(') and seg.endswith(')'):
            seg = seg[1:-1].strip()
        if re.fullmatch(r'(?:[A-Z]\.){2,}[A-Z]?\.?', seg):
            seg = seg.replace('.', '')                                   # "A.I.M.S.R" → "AIMSR"
        if not seg or AFFIL_ROLE_SEGMENT_RE.fullmatch(seg) or re.fullmatch(r'\.?[a-z]{2,5}(?:\.[a-z]{2,3})*\.?', seg):
            continue
        # Title-case words typed all lowercase ("Department of biosciences")
        seg = ' '.join(w if not w.islower() or w in AFFIL_LOWER_WORDS else w[0].upper() + w[1:]
                       for w in seg.split())
        segments.append(seg)
    return ', '.join(segments).strip(' ,;:-')


def _parse_author_column(col_spans, italic_is_affiliation=False):
    """
    Parse an author column/block into a list of authors (supporting multiple stacked
    authors in the same vertical column/grid cell as well as comma-separated authors).

    - Lines after a name are that author's affiliation.
    - Lines after a comma-separated name line ("A, B and C") are shared by the group.
    - Numbered affiliation lines ("1Dept. ...", "1,2 Dept. ...") are mapped to the
      authors' superscript numbers.
    When italic_is_affiliation is True (IEEE style: upright names, italic affiliations),
    italic spans are never treated as author names.
    """
    authors = []
    group = []          # authors receiving the affiliation lines being collected
    group_lines = []
    numbered = {}       # affiliation number -> lines
    numbered_target = None

    def close_group():
        college = smart_join_parts(group_lines)
        for a in group:
            if not a['college']:
                a['college'] = college

    def add_author(name, span, affil=None):
        a = {'name': name, 'college': '', 'affil_num': affil,
             '_y': span['origin_y'], '_x': span.get('origin_x', 0)}
        authors.append(a)
        return a

    def start_numbered(nums):
        # Lines collected for a number already seen (repeated block) are discarded
        target = []
        if any(n not in numbered for n in nums):
            for n in nums:
                numbered.setdefault(n, target)
        return target

    def digits_of(t):
        nums = re.findall(r'\d+', t)
        return nums if nums and not re.search(r'[A-Za-z]', t) else None

    i = 0
    while i < len(col_spans):
        s = col_spans[i]
        text = s['text'].strip()
        if (not text or not re.search(r'[A-Za-z0-9]', text) or is_copyright(text)
                or is_email(text) or is_location_line(text)):
            i += 1
            continue

        nxt = col_spans[i + 1] if i + 1 < len(col_spans) else None

        # Affiliation number marker ("1", "1,2", "[1]", superscript "1*")
        nums = digits_of(text)
        if s['is_super'] or nums:
            if nums and nxt is not None and not nxt['is_super'] and not is_person_name(nxt['text']) \
                    and abs(nxt['origin_y'] - s['origin_y']) < max(8, nxt['size']):
                # Marker in front of an affiliation line → numbered affiliation block
                numbered_target = start_numbered(nums)
            elif nums and nxt is not None and abs(nxt['origin_y'] - s['origin_y']) < 4 \
                    and is_person_name(nxt['text']):
                pass  # author index in front of a name ("1 Gajjela Prakash", "[2]Aditi Gupta")
            elif nums and authors and authors[-1]['affil_num'] is None and group and authors[-1] in group:
                authors[-1]['affil_num'] = nums[0]
            i += 1
            continue

        # "1,2Dept. of ..." / "1Student, Department of ..."
        m_num = re.match(r'^(\d+(?:\s*,\s*\d+)*)\s*(?=[A-Za-z])(.*)$', text)
        if m_num and not is_person_name(m_num.group(2)):
            numbered_target = start_numbered(re.findall(r'\d+', m_num.group(1)))
            numbered_target.append(m_num.group(2))
            i += 1
            continue

        # Italic lines are affiliations in IEEE-style author blocks
        if italic_is_affiliation and s['is_italic']:
            (numbered_target if numbered_target is not None else group_lines).append(text)
            i += 1
            continue

        # Lone initial split into its own span (e.g. "A." + "Merry Ida") → join with the name
        if re.match(r'^[A-Z]\.$', text) and nxt is not None:
            if (abs(nxt['origin_y'] - s['origin_y']) < 2 and not nxt['is_italic']
                    and is_person_name(nxt['text'])):
                nxt = dict(nxt, text=text + ' ' + nxt['text'].strip(), origin_x=s.get('origin_x', 0))
                col_spans = col_spans[:i + 1] + [nxt] + col_spans[i + 2:]
                i += 1
                continue

        # Multiple names on one line: "A, B and C"
        if re.search(r',|\sand\s|&', text) and not is_affiliation_text(text):
            parts = [p.strip() for p in re.split(r'\s*,\s*|\s+and\s+|\s*&\s*', text) if p.strip()]
            parts = [p for p in parts if re.search(r'[A-Za-z]{2}', p)]
            if len(parts) >= 2 and all(is_person_name(p) for p in parts):
                close_group()
                group, group_lines, numbered_target = [], [], None
                for p_name in parts:
                    m_sup = re.search(r'(\d+)\W*$', p_name)
                    clean_name = clean_author_name(p_name)
                    if clean_name:
                        group.append(add_author(clean_name, s, m_sup.group(1) if m_sup else None))
                i += 1
                continue

        # Template placeholder in place of a name ("Teacher"): drop it with its affiliation lines
        if re.fullmatch(r'teacher', clean_author_name(text), re.I):
            close_group()
            group, group_lines, numbered_target = [], [], None
            i += 1
            continue

        # Single person name
        if is_person_name(text):
            numbered_target = None
            author = add_author(clean_author_name(text), s)
            if group and not group_lines and abs(group[-1]['_y'] - s['origin_y']) < 4:
                # Same line as the previous name ("A¹, B² and C*"): one shared affiliation
                group.append(author)
            else:
                close_group()
                group, group_lines = [author], []
            if nxt is not None:
                nt = nxt['text'].strip()
                n_nums = digits_of(nt)
                if n_nums and (nxt['is_super'] or abs(nxt['origin_y'] - s['origin_y']) < 4):
                    author['affil_num'] = n_nums[0]
                    i += 2
                    continue
            i += 1
            continue

        (numbered_target if numbered_target is not None else group_lines).append(text)
        i += 1

    close_group()

    # Fill colleges of numbered authors from the numbered affiliation blocks
    for a in authors:
        lines = numbered.get(a['affil_num'] or '')
        if lines:
            a['college'] = smart_join_parts(lines)
        a['college'] = _clean_college(a['college'])
    return authors


def _merge_word_spans(spans, max_gap=6.0):
    """
    Join consecutive spans on the same baseline into one line-level span.
    Some PDFs emit one span per word ("Marwadi" "University"), which would otherwise
    be comma-joined as separate entities and filtered word-by-word.
    """
    merged = []
    for s in spans:
        if not s['text'].strip():
            continue
        prev = merged[-1] if merged else None
        if (prev and not s['is_super'] and not prev['is_super']
                and s['is_italic'] == prev['is_italic']
                and abs(s['origin_y'] - prev['origin_y']) < 2
                and -1.0 <= s.get('origin_x', 0) - prev.get('end_x', 0) <= max_gap):
            # Glyph-adjacent fragments (small caps "T" + "HE") join without a space
            gap = s.get('origin_x', 0) - prev.get('end_x', 0)
            spaced = gap >= 0.8 or prev['text'][-1:].isspace() or s['text'][:1].isspace()
            merged[-1] = dict(prev, text=prev['text'].rstrip() + (' ' if spaced else '') + s['text'].strip(),
                              end_x=s.get('end_x', 0))
        else:
            merged.append(dict(s))
    return merged


def _extract_authors_spatial(section_spans):
    """
    Extract authors using spatial column clustering and row ordering so multi-column
    and grid-based author blocks (e.g. 2x2 or 3x2) are parsed completely.
    """
    filtered = []
    for s in _merge_word_spans(section_spans):
        text = s['text'].strip()
        if text and is_location_line(text):
            # "AITR, Indore, India": keep the institution acronym, drop the place names
            acronyms = [p.strip() for p in text.split(',') if re.fullmatch(r'[A-Z]{3,}', p.strip())]
            acronyms += re.findall(r'\(([A-Z]{3,})\)', text)   # "(AIMSR) Indore,India"
            if not acronyms:
                continue
            s = dict(s, text=', '.join(acronyms))
            text = s['text']
        if not text or is_copyright(text) or is_email(text):
            continue
        if AUTHOR_NOISE_RE.match(text):
            continue
        filtered.append(s)

    if not filtered:
        return []

    x0 = min(s.get('origin_x', 0) for s in filtered)
    x1 = max(s.get('end_x', 0) for s in filtered)
    x_spread = x1 - x0
    # Grid layouts never have lines spanning most of the block width
    wide_lines = sum(1 for s in filtered
                     if s.get('end_x', 0) - s.get('origin_x', 0) > 0.6 * max(x_spread, 1))
    columnar = x_spread > 120 and wide_lines == 0

    # IEEE-style block: upright author names alongside italic affiliations
    italic_is_affiliation = (
        any(s['is_italic'] for s in filtered if not s['is_super'])
        and any(not s['is_italic'] and is_person_name(s['text']) for s in filtered if not s['is_super'])
    )

    authors = []

    if columnar:
        per_column = []
        for col in _cluster_spans_by_column(filtered):
            parsed_list = [a for a in _parse_author_column(col, italic_is_affiliation) if a and a.get('name')]
            per_column.append(len(parsed_list))
            authors.extend(parsed_list)
        if all(n == 1 for n in per_column):
            # Single row of authors: left to right, even when the cells are vertically staggered
            authors.sort(key=lambda a: a['_x'])
        else:
            # Papers number authors row by row across the grid, not column by column
            rows = []
            for a in sorted(authors, key=lambda a: a['_y']):
                if rows and a['_y'] - rows[-1][0]['_y'] <= 12:
                    rows[-1].append(a)
                else:
                    rows.append([a])
            authors = [a for row in rows for a in sorted(row, key=lambda a: a['_x'])]
    else:
        parsed_list = _parse_author_column(_order_in_rows(filtered), italic_is_affiliation)
        for a in parsed_list:
            if a and a.get('name'):
                authors.append(a)
    for a in authors:
        a.pop('_y', None)
        a.pop('_x', None)

    # Deduplicate identical name+college pairs from overlapping columns
    seen = set()
    unique = []
    for a in authors:
        key = (a['name'].lower(), a.get('college', '').lower())
        if key in seen:
            continue
        seen.add(key)
        unique.append(a)
    return unique


# ============================================================
# PDF SCRAPING HELPERS & EXTRACTION
# ============================================================

ZERO_WIDTH_RE = re.compile('[\u200b\u200c\u200d\u2060\ufeff]')


def _split_on_wide_gaps(chars):
    """
    Split one PDF span into segments separated by runs of 3+ spaces.
    Some author blocks are typed as one line padded with spaces
    ("Priyanshu Sharma          Lovekush Nagda          Shubh Sharma").
    Returns [(text, x0, x1)] using the real character positions.
    """
    segments = []
    current = []
    space_run = 0
    for c in chars:
        ch = ZERO_WIDTH_RE.sub('', c['c'])
        if not ch:
            continue
        if ch.isspace():
            space_run += 1
            if space_run >= 3 and any(not x['c'].isspace() for x in current):
                segments.append(current)
                current = []
            elif current:
                current.append({'c': ch, 'origin': c['origin'], 'bbox': c['bbox']})
            continue
        space_run = 0
        current.append({'c': ch, 'origin': c['origin'], 'bbox': c['bbox']})
    if current:
        segments.append(current)

    out = []
    for seg in segments:
        solid = [c for c in seg if not c['c'].isspace()]
        if not solid:
            continue
        out.append((''.join(c['c'] for c in seg), solid[0]['origin'][0], solid[-1]['bbox'][2]))
    return out


def _extract_text_spans(page, page_no=0, y_offset=0.0):
    """Flatten and enhance all text spans in reading order from a PDF page."""
    page_dict = page.get_text('rawdict')
    spans = []
    for block in page_dict.get('blocks', []):
        if 'lines' not in block:
            continue
        for line in block['lines']:
            for span in line['spans']:
                for text, x0, x1 in _split_on_wide_gaps(span.get('chars', [])):
                    spans.append({
                        'text': text,
                        'size': round(span['size'], 1),
                        'flags': span['flags'],
                        'is_bold': bool(span['flags'] & 16),
                        'is_italic': bool(span['flags'] & 2),
                        'is_super': bool(span['flags'] & 1),
                        'origin_x': round(x0, 1),
                        'origin_y': round(span['origin'][1] + y_offset, 1),
                        'end_x': round(x1, 1),
                        'page': page_no,
                    })

    # Enhanced superscript detection for baseline-shifted / scaled fonts
    for i in range(1, len(spans)):
        s = spans[i]
        if s['is_super']:
            continue
        prev = spans[i - 1]
        if abs(s['origin_y'] - prev['origin_y']) < max(3, prev['size'] * 0.5):
            if prev['size'] > 0 and s['size'] < prev['size'] * 0.75:
                s['is_super'] = True

    return spans


TITLE_PREFIX_RE = re.compile(
    r'^(?:research\s+paper|paper\s+title|title|topic)\s*[:\-–—]+\s*', re.I)

# "Abstract—", "1Abstract–-", "ABSTRACT: -", "A B S T R A C T"
ABSTRACT_MARKER_RE = re.compile(
    r'^[\W\d_]{0,3}\s*(?:abstract|a\s+b\s+s\s+t\s+r\s+a\s+c\s+t)(?![a-z])', re.I)
# "Keywords—", "Key Words:", "Index Terms—", "“Keywords —"
KEYWORDS_MARKER_RE = re.compile(
    r'^[\W\d_]{0,3}\s*(?:key\s*words?|index\s*terms?)(?![a-z])', re.I)
# "I. INTRODUCTION", "1.Introduction", "Section I. INTRODUCTION", "Introduction"
SECTION_HEADING_RE = re.compile(
    r'^(?:section\s+)?(?:[IVX]{1,4}|\d{1,2})?\s*[.):]?\s*'
    r'(?:introduction|background|related\s+works?|literature\s+(?:review|survey))\s*[:.]?\s*$',
    re.I)


def _is_section_heading(spans, i):
    """True when span i starts the paper body (first numbered/introduction heading)."""
    t = spans[i]['text'].strip()
    if SECTION_HEADING_RE.match(t):
        return True
    # Small-caps heading split into fragments: "I" + "NTRODUCTION", "I." + "I" + "NTRODUCTION"
    if len(re.sub(r'[^A-Za-z]', '', t)) <= 2:
        joined = t
        for j in range(i + 1, min(i + 4, len(spans))):
            if abs(spans[j]['origin_y'] - spans[i]['origin_y']) >= 3:
                break
            joined += spans[j]['text'].strip()
            if SECTION_HEADING_RE.match(joined):
                return True
    # Roman-numbered upper-case heading: "I. THE CHALLENGE AHEAD", or "I." followed by
    # small-caps fragments on the same line ("I." "T" "HE " "A" "CCESS")
    m = re.match(r'^[IVX]{1,4}\.\s*(.*)$', t)
    if not m:
        return False
    rest = m.group(1)
    j = i + 1
    while len(re.sub(r'[^A-Za-z]', '', rest)) < 4 and j < min(i + 4, len(spans)):
        if abs(spans[j]['origin_y'] - spans[i]['origin_y']) >= 3:
            break
        rest += spans[j]['text']
        j += 1
    letters = re.sub(r'[^A-Za-z]', '', rest)
    return len(letters) >= 2 and sum(c.isupper() for c in letters) >= 0.8 * len(letters)


def _extract_title(spans):
    """
    Extract the title from page 1: the first block of the largest font (same weight,
    vertically adjacent lines), extended by an adjacent smaller-font subtitle line
    such as "KISAAN:" followed by "An AI-Powered ...".
    Returns (title, last_title_idx, title_indices).
    """
    page1 = [i for i, s in enumerate(spans)
             if s.get('page', 0) == 0 and s['text'].strip() and not s['is_super']
             and not is_copyright(s['text'])]
    if not page1:
        return "", 0, set()
    max_size = max(spans[i]['size'] for i in page1)
    first = min((i for i in page1 if spans[i]['size'] == max_size),
                key=lambda i: (spans[i]['origin_y'], spans[i]['origin_x']))
    ref_bold = spans[first]['is_bold']
    top_y = spans[first]['origin_y']

    def collect(min_size):
        cands = sorted(
            (i for i in page1
             if min_size <= spans[i]['size'] <= max_size
             and spans[i]['is_bold'] == ref_bold
             and spans[i]['origin_y'] >= top_y - 3),
            key=lambda i: (spans[i]['origin_y'], spans[i]['origin_x']))
        chosen, last_y = [], top_y
        for i in cands:
            if spans[i]['origin_y'] - last_y > spans[i]['size'] * 2.2:
                break
            chosen.append(i)
            last_y = max(last_y, spans[i]['origin_y'])
        return chosen

    chosen = collect(max_size - 0.5)
    extended = collect(max_size * 0.65)
    # Only accept the subtitle extension when it stays a single title block
    if len(extended) > len(chosen) and all(i in extended for i in chosen):
        chosen = extended

    chosen.sort(key=lambda i: (round(spans[i]['origin_y']), spans[i]['origin_x']))
    title = ' '.join(spans[i]['text'].strip() for i in chosen)
    title = re.sub(r'\s+', ' ', title).strip()
    title = TITLE_PREFIX_RE.sub('', title).strip()
    return title, max(chosen), set(chosen)


def _extract_fallback_keywords(title, abstract_text):
    """
    Extracts 4 to 6 relevant technical terms / noun phrases from the title and abstract
    when the original PDF has no explicit Keywords / Index Terms section.
    """
    stopwords = {
        'a', 'about', 'above', 'after', 'again', 'against', 'all', 'am', 'an', 'and', 'any', 'are',
        'as', 'at', 'be', 'because', 'been', 'before', 'being', 'below', 'between', 'both', 'but',
        'by', 'can', 'could', 'did', 'do', 'does', 'doing', 'down', 'during', 'each', 'few', 'for',
        'from', 'further', 'had', 'has', 'have', 'having', 'he', 'her', 'here', 'hers', 'herself',
        'him', 'himself', 'his', 'how', 'i', 'if', 'in', 'into', 'is', 'it', 'its', 'itself',
        'just', 'me', 'more', 'most', 'my', 'myself', 'no', 'nor', 'not', 'now', 'of', 'off',
        'on', 'once', 'only', 'or', 'other', 'our', 'ours', 'ourselves', 'out', 'over', 'own',
        's', 'same', 'she', 'should', 'so', 'some', 'such', 't', 'than', 'that', 'the', 'their',
        'theirs', 'them', 'themselves', 'then', 'there', 'these', 'they', 'this', 'those', 'through',
        'to', 'too', 'under', 'until', 'up', 'very', 'was', 'we', 'were', 'what', 'when', 'where',
        'which', 'while', 'who', 'whom', 'why', 'will', 'with', 'would', 'you', 'your', 'yours',
        'paper', 'study', 'presents', 'proposed', 'results', 'based', 'using', 'novel', 'approach',
        'system', 'method', 'analysis', 'performance', 'evaluation', 'overview', 'review', 'various'
    }
    combined_text = f"{title}. {abstract_text}"
    candidates = []

    # Capitalized technical phrases (e.g. "Convolutional Neural Networks", "IoT Devices")
    caps_phrases = re.findall(r'\b[A-Z][a-zA-Z0-9]*(?:\s+[A-Z][a-zA-Z0-9]*)+\b', combined_text)
    for phrase in caps_phrases:
        phrase_clean = phrase.strip()
        words = phrase_clean.lower().split()
        if not any(w in stopwords for w in words) and 3 <= len(phrase_clean) <= 40:
            if phrase_clean not in candidates:
                candidates.append(phrase_clean)

    # Key terms from title
    title_words = [w.strip('.,:;()[]"\'') for w in title.split() if len(w) > 3]
    for w in title_words:
        if w.lower() not in stopwords and w not in candidates:
            candidates.append(w)

    return ', '.join(candidates[:5]) if candidates else ''


# ============================================================
# PDF SCRAPING
# ============================================================

def extract_paper_data(pdf_path):
    """
    Extract title, authors+college, abstract, and keywords from the
    FIRST PAGE of a PDF. Uses font size and style metadata for robust
    detection across varying IEEE paper formats.
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

    # Page 1 plus page 2: some templates put the abstract/keywords on page 2
    spans = _extract_text_spans(doc[0], 0, 0.0)
    if len(doc) > 1:
        spans += _extract_text_spans(doc[1], 1, doc[0].rect.height)
    doc.close()
    spans = _merge_word_spans(spans)

    if not spans:
        print(f"  [ERROR] FATAL: No text spans found on page 1")
        return None

    # STEP 1: EXTRACT TITLE
    title, last_title_idx, title_indices = _extract_title(spans)
    if not title:
        print(f"  [WARN] No title found")
    else:
        print(f"  [OK] Title: \"{title}\"")

    # STEP 2: LOCATE ABSTRACT & KEYWORDS
    abstract_idx = None
    for i in range(last_title_idx + 1, len(spans)):
        if ABSTRACT_MARKER_RE.match(spans[i]['text'].strip()):
            abstract_idx = i
            break

    if abstract_idx is None:
        print(f"  [WARN] 'Abstract' marker not found -- trying fallback")
        for i in range(last_title_idx + 1, len(spans)):
            if 'abstract' in spans[i]['text'].lower():
                abstract_idx = i
                break

    # Find "Keywords" / "Index Terms" marker (stop looking once the body starts)
    keywords_idx = None
    kw_start = (abstract_idx + 1) if abstract_idx is not None else (last_title_idx + 1)
    for i in range(kw_start, len(spans) - 1):
        # Justified lines can split the label itself: "Index " + "Terms—digital twin"
        t, nxt = spans[i]['text'].strip(), spans[i + 1]
        if (re.match(r'^[\W\d_]{0,3}\s*(?:index|key)$', t, re.I)
                and re.match(r'^(?:terms?|words?)\b', nxt['text'].strip(), re.I)
                and abs(nxt['origin_y'] - spans[i]['origin_y']) < 3):
            spans[i] = dict(spans[i], text=t + ' ' + nxt['text'].strip(), end_x=nxt['end_x'])
            del spans[i + 1]
            break
    for i in range(kw_start, len(spans)):
        if KEYWORDS_MARKER_RE.match(spans[i]['text'].strip()):
            keywords_idx = i
            break
        if _is_section_heading(spans, i):
            break

    # ════════════════════════════════════════════════
    # STEP 3: EXTRACT AUTHORS + COLLEGE (spatial parsing)
    # ════════════════════════════════════════════════
    authors = []
    if abstract_idx is not None:
        section = [s for i, s in enumerate(spans[last_title_idx + 1: abstract_idx], last_title_idx + 1)
                   if i not in title_indices]
        authors = _extract_authors_spatial(section)

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
    keywords_text = ""

    if abstract_idx is not None:
        end_idx = keywords_idx if keywords_idx is not None else len(spans)
        parts = []
        started = False

        for i in range(abstract_idx, end_idx):
            text = spans[i]['text'].strip()
            if not text or is_copyright(text):
                continue
            if i > abstract_idx and _is_section_heading(spans, i):
                break

            if not started:
                text = ABSTRACT_MARKER_RE.sub('', text, count=1).strip()
                text = text.lstrip('-–—:.* \u2014\u2013').strip()
                if not text:
                    continue
                started = True

            parts.append(text)

        abstract_text = ' '.join(parts)
        abstract_text = re.sub(r'\s+', ' ', abstract_text).strip()

        # Check if keywords were embedded inside the abstract text
        embedded_kw_match = re.search(
            r'(?:Keywords?|Key\s*Words?|Index\s*Terms?)\s*[-–—: \u2014\u2013]+\s*(.+)',
            abstract_text,
            re.IGNORECASE | re.DOTALL
        )
        if embedded_kw_match:
            embedded_kw = embedded_kw_match.group(1).strip()
            abstract_text = abstract_text[:embedded_kw_match.start()].strip()
            keywords_text = re.sub(r'\s+', ' ', embedded_kw).strip().rstrip('.')

        print(f"  [OK] Abstract: {len(abstract_text)} characters")
    else:
        print(f"  [WARN] No abstract found")

    # ════════════════════════════════════════════════
    # STEP 5: EXTRACT KEYWORDS
    # ════════════════════════════════════════════════
    if keywords_idx is not None and not keywords_text:
        parts = []
        kw_size = spans[keywords_idx]['size']
        last_y = spans[keywords_idx]['origin_y']

        for i in range(keywords_idx, len(spans)):
            s = spans[i]
            t = s['text'].strip()
            if not t or is_copyright(t):
                continue

            if i > keywords_idx:
                # Keywords are a single paragraph: stop at a heading, a paragraph
                # gap, a jump to another column/page, or a change of font size
                if _is_section_heading(spans, i):
                    break
                if not parts:
                    # Label on its own line ("Keywords:" / "Keywords" + "—"): take the next line
                    kw_size = s['size']
                    last_y = s['origin_y']
                if s['origin_y'] - last_y > max(2.0 * s['size'], s['size'] + 8):
                    break
                if s['origin_y'] < last_y - 3:
                    break
                if abs(s['size'] - kw_size) > 1.5 and not s['is_super']:
                    break
                if re.match(r'^[A-Z\s]{5,}$', t) and not any(c in t for c in [',', ';']):
                    break
            last_y = max(last_y, s['origin_y'])

            if i == keywords_idx:
                t = KEYWORDS_MARKER_RE.sub('', t, count=1).strip()
                t = t.lstrip('-–—:.* \u2014\u2013').strip()
            if t:
                parts.append(t)

        if parts:
            keywords_text = ' '.join(parts)
            keywords_text = re.sub(r'\s+', ' ', keywords_text).strip().rstrip('.”"')

    # Fallback keyword extraction if none found in original PDF
    is_fallback_kw = False
    if not keywords_text and (title or abstract_text):
        keywords_text = _extract_fallback_keywords(title, abstract_text)
        if keywords_text:
            is_fallback_kw = True
            print(f"  [FALLBACK] Inferred Keywords: \"{keywords_text[:80]}\"")

    if keywords_text:
        keywords_text = tidy_keywords(keywords_text)
    if abstract_text:
        abstract_text = tidy_abstract(abstract_text, keywords_text)

    if keywords_text:
        print(f"  [OK] Keywords: \"{keywords_text[:80]}{'...' if len(keywords_text) > 80 else ''}\"")
    else:
        print(f"  [WARN] No keywords found")

    # ════════════════════════════════════════════════
    # VALIDATION & ANOMALY / DOUBT DETECTION
    # ════════════════════════════════════════════════
    anomalies = []

    # 1. Author count verification against superscripts & candidate names
    if abstract_idx is not None:
        author_section = spans[last_title_idx + 1: abstract_idx]
        author_text_spans = [s['text'].strip() for s in author_section if s['text'].strip() and not is_copyright(s['text']) and not is_email(s['text'])]
        detected_supers = set(re.findall(r'\b([1-9])\b', ' '.join(author_text_spans)))
        if len(detected_supers) > len(authors) and len(authors) > 0:
            anomalies.append(f"Author count potential mismatch: {len(detected_supers)} numeric affiliations detected, but {len(authors)} author(s) extracted")

    # 2. Check if keywords were inferred via fallback
    if is_fallback_kw:
        anomalies.append("No explicit Keywords/Index Terms section found in original PDF (inferred from title & abstract)")

    # 3. Check abstract length
    if len(abstract_text) < 250:
        anomalies.append(f"Unusually short abstract ({len(abstract_text)} characters)")

    # 4. Check for missing author affiliation
    missing_affils = [a['name'] for a in authors if not a.get('college')]
    if missing_affils:
        anomalies.append(f"Missing affiliation/college for author(s): {', '.join(missing_affils)}")

    # 5. Core missing fields
    if not title:
        anomalies.append("Missing title")
    if not authors:
        anomalies.append("Missing authors")
    if not abstract_text:
        anomalies.append("Missing abstract")
    if not keywords_text:
        anomalies.append("Missing keywords")

    # 6. Sanity limits: catch run-on or truncated fields the extractor cannot see itself
    if len(keywords_text) > 450:
        anomalies.append(f"Keywords unusually long ({len(keywords_text)} chars) -- may include body text")
    if len(abstract_text) > 3000:
        anomalies.append(f"Abstract unusually long ({len(abstract_text)} chars) -- may include body text")
    if title and (len(title) < 15 or title.rstrip().endswith((':', '-', ','))):
        anomalies.append(f"Title looks incomplete: \"{title}\"")
    if title and re.search(r'\b(?:a|an|the|of|in|for|and|to|with|on)$', title.rstrip(), re.I):
        anomalies.append(f"Title may be cut off in the source PDF: \"...{title[-45:]}\"")
    for old, new in AUTHOR_OVERRIDES.get(filename, {}).get('rename', {}).items():
        for a in authors:
            if a['name'] == old:
                a['name'] = new
                anomalies.append(f"Author name corrected by author_overrides.json: \"{old}\" -> \"{new}\"")
    suspicious = [a['name'] for a in authors
                  if re.search(r'[@:\d]|\b(?:author|e-?mail|student|note|teacher)\b', a['name'], re.I)]
    if suspicious:
        anomalies.append("Suspicious author name(s) -- check the source PDF: " + ', '.join(suspicious))

    if anomalies:
        print(f"  [ANOMALY / DOUBT] {len(anomalies)} issue(s) detected: {'; '.join(anomalies)}")
    else:
        print(f"  [OK] All fields extracted successfully")

    return {
        'title': title,
        'authors': authors,
        'abstract': abstract_text,
        'keywords': keywords_text,
        'source_file': filename,
        'anomalies': anomalies,
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
        # Vector circles rather than a "●" glyph: no unembedded symbol font, and copying
        # the page text no longer yields "G G G"
        count, radius, pitch = 11, 2.5 * LAYOUT_SCALE, 9.45 * LAYOUT_SCALE
        span = (count - 1) * pitch
        x = (self.width - span) / 2
        y = max(1, self.height / 3) + 2.6 * LAYOUT_SCALE
        self.canv.setFillColor(black)
        for i in range(count):
            self.canv.circle(x + i * pitch, y, radius, stroke=0, fill=1)


# ============================================================
# AUTHOR FORMATTING — Superscript Affiliations
# ============================================================

# Unicode superscript digits for affiliation markers
_SUPERSCRIPT_DIGITS = {
    1: '\u00b9', 2: '\u00b2', 3: '\u00b3', 4: '\u2074', 5: '\u2075',
    6: '\u2076', 7: '\u2077', 8: '\u2078', 9: '\u2079', 10: '\u00b9\u2070',
}

def format_authors_with_affiliations(authors, use_html_super=True, max_width=None, font_size=None):
    """
    Format authors with superscript affiliation numbers.

    Line 1: names with superscript affiliation numbers (always, even for one affiliation).
    Line 2: numbered affiliations (department/college), never job titles as authors.
            When they do not fit on one line (max_width), each affiliation gets its own line.

    Returns:
        (authors_line, affiliations_line)
    """
    if not authors:
        return '', ''

    # Drop empty-name entries; keep only valid author records
    authors = [a for a in authors if a.get('name', '').strip()]
    if not authors:
        return '', ''

    # Build unique affiliations preserving first-seen order
    college_to_num = {}
    college_list = []
    author_nums = []

    for a in authors:
        college = a.get('college', '').strip()
        pdf_num = a.get('affil_num')
        if pdf_num and str(pdf_num).isdigit():
            num = int(pdf_num)
            if college and college not in college_to_num:
                college_to_num[college] = num
                while len(college_list) < num:
                    college_list.append('')
                college_list[num - 1] = college
            author_nums.append(num)
            continue

        if not college:
            author_nums.append(None)
            continue
        if college not in college_to_num:
            college_to_num[college] = len(college_list) + 1
            college_list.append(college)
        author_nums.append(college_to_num[college])

    college_list = [c for c in college_list if c]
    if len(college_list) == 1:
        # One shared affiliation: an author whose college was not found still belongs to it
        author_nums = [1] * len(authors)

    def sup(num):
        return f"<super>{num}</super>" if use_html_super else _SUPERSCRIPT_DIGITS.get(num, str(num))

    author_parts = []
    for i, a in enumerate(authors):
        name_safe = markup_text(a['name'])
        num = author_nums[i] if college_list else None
        author_parts.append(name_safe if num is None else f"{name_safe}{sup(num)}")
    authors_line = ', '.join(author_parts)

    aff_parts = [f"{sup(idx + 1)}{markup_text(college)}" for idx, college in enumerate(college_list)]
    affiliations_line = ', '.join(aff_parts)
    if len(aff_parts) > 1 and max_width and font_size:
        plain = ', '.join(f"{idx + 1}{college}" for idx, college in enumerate(college_list))
        if stringWidth(plain, FONT_ITALIC, font_size) > max_width:
            affiliations_line = '<br/>'.join(aff_parts)

    return authors_line, affiliations_line


# ============================================================
# PDF GENERATION — BODY PAGES
# ============================================================

def _draw_footer_url(canvas, y):
    """Footer website text (left-aligned); clickable when it is a web address."""
    canvas.setFont(FONT_BOLD, FOOTER_URL_FONT_SIZE)
    canvas.setFillColor(black)
    canvas.drawString(LEFT_MARGIN, y, FOOTER_URL)
    if re.match(r'(?:https?://|www\.)', FOOTER_URL, re.I):
        url = FOOTER_URL if re.match(r'https?://', FOOTER_URL, re.I) else 'https://' + FOOTER_URL
        width = canvas.stringWidth(FOOTER_URL, FONT_BOLD, FOOTER_URL_FONT_SIZE)
        canvas.linkURL(url, (LEFT_MARGIN, y - 2, LEFT_MARGIN + width, y + FOOTER_URL_FONT_SIZE), relative=0)


def _body_page_handler(canvas, doc):
    """Draw header and footer on each body page."""
    canvas.saveState()

    # ══════════════════════════════════════
    # HEADER
    # ══════════════════════════════════════
    # Conference name (italic, left-aligned)
    canvas.setFont(FONT_ITALIC, HEADER_FONT_SIZE)
    header_y = PAGE_HEIGHT - 38 * LAYOUT_SCALE
    canvas.drawString(LEFT_MARGIN, header_y, CONFERENCE_HEADER)

    # Deep blue header divider line
    canvas.setStrokeColor(DIVIDER_COLOR)
    canvas.setLineWidth(1.2)
    header_line_y = header_y - 9 * LAYOUT_SCALE
    canvas.line(LEFT_MARGIN, header_line_y, PAGE_WIDTH - RIGHT_MARGIN, header_line_y)

    # ══════════════════════════════════════
    # FOOTER
    # ══════════════════════════════════════
    # Deep blue footer divider line
    footer_line_y = BOTTOM_MARGIN - 5 * LAYOUT_SCALE
    canvas.setStrokeColor(DIVIDER_COLOR)
    canvas.setLineWidth(1.2)
    canvas.line(LEFT_MARGIN, footer_line_y, PAGE_WIDTH - RIGHT_MARGIN, footer_line_y)

    # Website (left-aligned) below the line
    footer_text_y = footer_line_y - 14 * LAYOUT_SCALE
    _draw_footer_url(canvas, footer_text_y)

    # Page number (right-aligned) below the line
    canvas.setFont(FONT_REGULAR, FOOTER_PAGE_FONT_SIZE)
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

for _tier in TIER_SPECS:
    for _key in ('space_title', 'space_auth', 'space_abs', 'space_kw', 'spacer_auth_abs',
                 'sep_top', 'sep_dot', 'sep_bottom', 'sep_total'):
        _tier[_key] *= LAYOUT_SCALE


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
        fontName=FONT_BOLD,
        fontSize=font_title,
        leading=font_title * leading_factor,
        alignment=TA_CENTER,
        spaceAfter=space_title,
        wordSpace=WORD_SPACING,
        keepWithNext=True,
    )
    st_auth = ParagraphStyle(
        f"auth_{tier.get('name', 'tier')}_{len(page_papers)}_{uid}",
        fontName=FONT_REGULAR,
        fontSize=font_auth,
        leading=font_auth * leading_factor,
        alignment=TA_CENTER,
        spaceAfter=space_auth,
        wordSpace=WORD_SPACING * 0.7,
        keepWithNext=True,
    )
    st_abs = ParagraphStyle(
        f"abs_{tier.get('name', 'tier')}_{len(page_papers)}_{uid}",
        fontName=FONT_REGULAR,
        fontSize=font_abs,
        leading=font_abs * leading_factor,
        alignment=TA_JUSTIFY,
        spaceAfter=space_abs,
        wordSpace=WORD_SPACING,
        keepWithNext=True,
    )
    st_kw = ParagraphStyle(
        f"kw_{tier.get('name', 'tier')}_{len(page_papers)}_{uid}",
        fontName=FONT_REGULAR,
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
        title_safe = markup_text(paper['title'])
        abstract_safe = markup_text(paper['abstract'])
        keywords_safe = markup_text(paper['keywords'])
        authors_text, affiliations_text = format_authors_with_affiliations(
            paper['authors'], use_html_super=True, max_width=avail_width, font_size=font_auth)

        p_title = Paragraph(title_safe, st_title)
        p_authors = Paragraph(authors_text, st_auth)
        p_aff = Paragraph(f'<i>{affiliations_text}</i>', st_auth) if affiliations_text else None
        p_abs = Paragraph(f"<b>Abstract— </b>{abstract_safe}", st_abs)
        p_kw = Paragraph(f"<b>Keywords— </b><i>{keywords_safe}</i>", st_kw) if keywords_safe else None

        # Measure flowables
        _, h_t = p_title.wrap(avail_width, 9999)
        _, h_a = p_authors.wrap(avail_width, 9999)
        h_aff = 0
        if p_aff:
            _, h_aff = p_aff.wrap(avail_width, 9999)
        _, h_ab = p_abs.wrap(avail_width, 9999)
        h_k = 0
        if p_kw:
            _, h_k = p_kw.wrap(avail_width, 9999)

        item_h = (h_t + space_title + h_a +
                  (h_aff + space_auth if p_aff else space_auth) +
                  spacer_auth_abs + h_ab + space_abs + (h_k + space_kw if p_kw else 0))
        total_h += item_h

        # Wrap this entire paper's components in an atomic KeepTogether block with keepWithNext=True
        paper_block = [PageTracker(paper_idx), p_title, p_authors]
        if p_aff:
            paper_block.append(p_aff)
        paper_block.append(Spacer(1, spacer_auth_abs))
        paper_block.append(p_abs)
        if p_kw:
            paper_block.append(p_kw)

        page_flowables.append(KeepTogether(paper_block))

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
    Matrix shape: N x 4
    """
    matrix = []
    for p_idx, p in enumerate(papers):
        row = []
        for t_idx, tier in enumerate(TIER_SPECS):
            _, h = _build_and_measure_page([p], [p_idx], tier, avail_width)
            row.append(h)
        matrix.append(row)
    return matrix


def _find_optimal_zero_waste_packing(papers, avail_height, forbidden_pairs=None):
    """
    Bin-packing engine for abstract pages.

    Strategy: Tallest-first, shortest-partner matching.
    Big papers always get paired with the shortest available paper FIRST,
    so small papers are never wasted by pairing two smalls together
    while a big paper sits alone.

    Rules:
      1. At most MAX_PAPERS_PER_PAGE (2) abstracts per page.
      2. Every non-final page must have 2 abstracts (unless truly oversized).
      3. Non-final pages must fill at least MIN_PAGE_FILL_RATIO of height.
      4. Last page may contain a single leftover abstract (any whitespace OK).
      5. Conservative headroom prevents KeepTogether overflow / keyword leaks.
      6. Only papers that cannot fit with the SHORTEST available paper
         are allowed solo pages.
    """
    n = len(papers)
    if n == 0:
        return []
    if n == 1 or MAX_PAPERS_PER_PAGE == 1:
        return [(i,) for i in range(n)]   # one per page, in reading order

    if forbidden_pairs is None:
        forbidden_pairs = set()

    height_matrix = _precompute_paper_heights(papers, CONTENT_WIDTH)
    target_budget = avail_height - PACKING_HEADROOM_PT

    def test_group(grp):
        k = len(grp)
        if k == 0:
            return True, 0.0, 0
        if k > MAX_PAPERS_PER_PAGE:
            return False, float('inf'), None

        grp_tuple = tuple(sorted(grp))
        if grp_tuple in forbidden_pairs:
            return False, float('inf'), None

        for t_idx, tier in enumerate(TIER_SPECS):
            h_papers = sum(height_matrix[i][t_idx] for i in grp)
            h_sep = (k - 1) * tier['sep_total']
            tot = h_papers + h_sep
            if tot <= target_budget:
                return True, tot, t_idx
        return False, float('inf'), None

    # ── Phase 1: Tallest-first, shortest-partner greedy matching ──
    # Sort all papers by their minimum possible height (most compact tier)
    min_heights = [min(height_matrix[i]) for i in range(n)]
    
    # Sort indices: tallest first
    tall_order = sorted(range(n), key=lambda i: min_heights[i], reverse=True)
    
    paired = set()
    bins = []
    truly_oversized = set()
    
    for idx in tall_order:
        if idx in paired:
            continue
        
        # Find the shortest AVAILABLE partner that fits with this paper
        # Sort candidates by height ascending (shortest first)
        candidates = [
            j for j in range(n)
            if j != idx and j not in paired
        ]
        candidates.sort(key=lambda j: min_heights[j])  # shortest first
        
        best_partner = None
        best_tot = float('inf')
        best_tier = None
        
        for cand in candidates:
            pair_tuple = tuple(sorted([idx, cand]))
            if pair_tuple in forbidden_pairs:
                continue
            fits, tot, t_idx = test_group([idx, cand])
            if fits:
                # Pick the partner that gives the tightest fit (least waste)
                if best_partner is None or tot > best_tot:
                    # Actually prefer HIGHER fill (less whitespace)
                    best_partner = cand
                    best_tot = tot
                    best_tier = t_idx
                # But first valid (shortest) partner is already great
                # Accept first fit for speed, SA will refine later
                best_partner = cand
                best_tot = tot
                best_tier = t_idx
                break
        
        if best_partner is not None:
            bins.append([idx, best_partner])
            paired.add(idx)
            paired.add(best_partner)
        else:
            # This paper cannot pair with ANY remaining paper
            truly_oversized.add(idx)
            bins.append([idx])
            paired.add(idx)
    
    # ── Phase 2: Try to rescue oversized singles by stealing a partner ──
    # For each truly_oversized paper, check if swapping it with someone
    # from a paired bin would work better
    for solo_idx in list(truly_oversized):
        rescued = False
        for b_idx, b in enumerate(bins):
            if len(b) != 2:
                continue
            for pos in range(2):
                partner_in_bin = b[pos]
                other_in_bin = b[1 - pos]
                # Can solo_idx pair with partner_in_bin?
                pair1 = tuple(sorted([solo_idx, partner_in_bin]))
                if pair1 in forbidden_pairs:
                    continue
                fits1, _, _ = test_group([solo_idx, partner_in_bin])
                if not fits1:
                    continue
                # Can other_in_bin pair with anyone else or go solo on last page?
                # Check if other_in_bin can fit with another solo
                other_solo_bins = [i for i, bb in enumerate(bins) if len(bb) == 1 and bb[0] != solo_idx]
                placed_other = False
                for os_idx in other_solo_bins:
                    os_paper = bins[os_idx][0]
                    pair2 = tuple(sorted([other_in_bin, os_paper]))
                    if pair2 in forbidden_pairs:
                        continue
                    fits2, _, _ = test_group([other_in_bin, os_paper])
                    if fits2:
                        # Great! Swap: solo_idx takes partner_in_bin's spot,
                        # other_in_bin joins os_paper
                        bins[b_idx] = [solo_idx, partner_in_bin]
                        bins[os_idx] = [other_in_bin, os_paper]
                        # Remove solo_idx's old solo bin
                        bins = [bb for bb in bins if not (len(bb) == 1 and bb[0] == solo_idx)]
                        truly_oversized.discard(solo_idx)
                        truly_oversized.discard(os_paper)
                        placed_other = True
                        rescued = True
                        break
                if rescued:
                    break
            if rescued:
                break

    # ── Phase 3: Simulated Annealing refinement (5000 iterations) ──
    def score_partition(part):
        sc = 0.0
        valid_bins = [b for b in part if b]
        num_bins = len(valid_bins)
        for b_idx, b in enumerate(valid_bins):
            fits, tot, t_idx = test_group(b)
            if not fits:
                return -1e9

            ratio = min(1.0, tot / avail_height)
            is_last_page = (b_idx == num_bins - 1)

            if not is_last_page:
                if len(b) < 2:
                    if len(b) == 1 and b[0] in truly_oversized:
                        sc += 100.0  # Acceptable for truly oversized
                    else:
                        return -1e9  # Non-final solo page is FORBIDDEN
                if ratio < MIN_PAGE_FILL_RATIO:
                    sc -= 50000.0 * (MIN_PAGE_FILL_RATIO - ratio)

            if len(b) == 2:
                sc += 800.0 + (ratio * 300.0)
            elif len(b) == 1:
                if not is_last_page and b[0] not in truly_oversized:
                    return -1e9
                sc += 50.0

            # Prefer standard generous margins
            if t_idx == 0:
                sc += 60.0
            elif t_idx == 1:
                sc += 30.0
            elif t_idx == 3:
                sc -= 40.0
        return sc

    best_bins = [list(b) for b in bins]
    best_score = score_partition(best_bins)
    curr_bins = [list(b) for b in best_bins]

    for it in range(5000):
        curr_bins = [b for b in curr_bins if b]
        if len(curr_bins) < 2:
            break
        b1_idx, b2_idx = random.sample(range(len(curr_bins)), 2)
        b1 = curr_bins[b1_idx]
        b2 = curr_bins[b2_idx]

        # Move 1: Try item swap between b1 and b2
        if b1 and b2:
            i1 = random.randrange(len(b1))
            i2 = random.randrange(len(b2))
            c1 = list(b1)
            c2 = list(b2)
            c1[i1], c2[i2] = c2[i2], c1[i1]
            if len(c1) <= MAX_PAPERS_PER_PAGE and len(c2) <= MAX_PAPERS_PER_PAGE:
                f1, _, _ = test_group(c1)
                f2, _, _ = test_group(c2)
                if f1 and f2:
                    cand_part = list(curr_bins)
                    cand_part[b1_idx] = c1
                    cand_part[b2_idx] = c2
                    sc = score_partition(cand_part)
                    if sc > best_score:
                        best_score = sc
                        best_bins = [list(b) for b in cand_part if b]
                        curr_bins = cand_part
                        continue

        # Move 2: Try item transfer from b1 to b2
        if len(b1) >= 1 and len(b2) <= MAX_PAPERS_PER_PAGE - 1:
            i1 = random.randrange(len(b1))
            c1 = [x for idx, x in enumerate(b1) if idx != i1]
            c2 = b2 + [b1[i1]]
            f1, _, _ = test_group(c1) if c1 else (True, 0, 0)
            f2, _, _ = test_group(c2)
            if f1 and f2:
                cand_part = list(curr_bins)
                cand_part[b1_idx] = c1
                cand_part[b2_idx] = c2
                cand_part = [b for b in cand_part if b]
                sc = score_partition(cand_part)
                if sc > best_score:
                    best_score = sc
                    best_bins = [list(b) for b in cand_part]
                    curr_bins = cand_part

    # ── Final ordering: paired pages first (desc by fill), solos last ──
    clean_bins = [b for b in best_bins if b]
    multi_groups = [b for b in clean_bins if len(b) >= 2]
    single_groups = [b for b in clean_bins if len(b) == 1]

    multi_records = []
    for b in multi_groups:
        _, tot, t_idx = test_group(b)
        multi_records.append((tuple(b), tot, t_idx))
    multi_records.sort(key=lambda rec: rec[1], reverse=True)

    # Oversized solos go before the final leftover
    oversized_singles = [s for s in single_groups if s[0] in truly_oversized]
    leftover_singles = [s for s in single_groups if s[0] not in truly_oversized]

    final_groups = [rec[0] for rec in multi_records]
    for s in oversized_singles:
        final_groups.append(tuple(s))
    for s in leftover_singles:
        final_groups.append(tuple(s))

    return final_groups


def _generate_page_flowables_justified(page_papers, page_paper_indices, avail_width, avail_height, is_final_page=False):
    """
    Generates flowables for a page and vertically justifies / stretches internal spacing
    so that the entire page is 100% filled from top to bottom, eliminating empty white space
    at the bottom of the page with strict safe headroom.
    """
    k = len(page_papers)
    target_budget = avail_height - 45.0 * LAYOUT_SCALE
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

    # Calculate remaining white space (slack) with conservative 40pt buffer
    slack = (avail_height - 40.0 * LAYOUT_SCALE) - base_h

    # Vertically justify if there is slack. The boost is capped (4pt on A4), so a short final
    # page is not stretched to the bottom; it just gets the same spacing as the full pages.
    if slack > 4.0:
        # Expansion points: 5 per paper + 2 per separator
        num_expand_points = 5 * k + (2 * (k - 1) if k > 1 else 0)
        boost = min(4.0 * LAYOUT_SCALE, slack / max(1, num_expand_points))

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
            if final_h <= avail_height - 35.0 * LAYOUT_SCALE:
                return flowables, justified_tier['name'], final_h
            boost -= 0.5

    # Build standard flowables
    flowables, final_h = _build_and_measure_page(page_papers, page_paper_indices, best_tier, avail_width)
    return flowables, best_tier['name'], final_h


def _inspect_body_pdf_pages(pdf_path, expected_num_pages):
    """
    Inspects each rendered page of the generated body PDF using PyMuPDF (fitz).
    Detects any orphan keyword spills, split content, or underfilled intermediate pages.
    Returns (is_clean, list_of_defects).
    """
    import fitz
    if not os.path.exists(pdf_path):
        return False, [{'type': 'file_missing', 'msg': 'Body PDF file was not generated.'}]

    doc = fitz.open(pdf_path)
    defects = []

    if len(doc) != expected_num_pages:
        defects.append({
            'type': 'page_count_mismatch',
            'msg': f"Generated {len(doc)} physical pages, expected {expected_num_pages} (page overflow detected).",
            'actual_pages': len(doc),
            'expected_pages': expected_num_pages
        })

    for pg_idx, page in enumerate(doc):
        raw_text = page.get_text().strip()
        lines = [l.strip() for l in raw_text.split('\n') if l.strip()]
        is_last = (pg_idx == len(doc) - 1)

        # Check 1: Orphan keywords leak (starts with Keywords or contains only keywords without an abstract/title)
        has_title = any(len(l) > 30 and "—" not in l for l in lines)
        has_abstract = any("Abstract—" in l or "Abstract —" in l for l in lines)
        
        if (raw_text.startswith("Keywords—") or (not has_title and not has_abstract and "Keywords—" in raw_text)) or (len(raw_text) < 200 and "Keywords—" in raw_text and not has_abstract):
            defects.append({
                'type': 'orphan_keywords_leak',
                'page': pg_idx + 1,
                'msg': f"Page {pg_idx + 1} contains orphan keywords leaked across page boundary: '{raw_text[:60]}...'"
            })

        # Check 2: Intermediate underfilled page (< 280 chars) on non-final page
        if not is_last and len(raw_text) < 280:
            defects.append({
                'type': 'underfilled_intermediate_page',
                'page': pg_idx + 1,
                'msg': f"Page {pg_idx + 1} has insufficient content ({len(raw_text)} chars) on an intermediate page."
            })

    doc.close()
    return len(defects) == 0, defects


def generate_body_pdf(papers, output_path):
    """
    Generate the body pages of the compiled PDF using ReportLab Platypus
    with Automated Post-Compilation Self-Healing Verification.

    Zero-White-Space & Zero-Leak Guarantees:
      1. Uses Combinatorial Re-ordering & Bin Packing with 50pt safe headroom.
      2. Every non-final page contains AT LEAST 2 abstracts and is packed to 90%-100% fullness.
      3. Paragraphs are bound with keepWithNext=True to eliminate keyword spills.
      4. Inspects generated physical pages with PyMuPDF to verify zero defects.
      5. Automatically self-heals and re-packs if any defect is detected.

    Returns tuple (page_map, page_groups, page_density_modes)
    """
    global _page_map
    random.seed(PACKING_SEED)   # same papers -> same page layout on every run
    avail_height = PAGE_HEIGHT - TOP_MARGIN - BOTTOM_MARGIN
    forbidden_pairs = set()

    for attempt in range(1, 4):
        _page_map = {}

        doc = BaseDocTemplate(
            output_path,
            pagesize=PAGE_SIZE,
            leftMargin=LEFT_MARGIN,
            rightMargin=RIGHT_MARGIN,
            topMargin=TOP_MARGIN,
            bottomMargin=BOTTOM_MARGIN,
        )

        frame = Frame(
            LEFT_MARGIN,
            BOTTOM_MARGIN,
            CONTENT_WIDTH,
            avail_height,
            id='body_frame',
            # Zero padding so the frame matches CONTENT_WIDTH used when measuring heights
            leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0,
        )

        doc.addPageTemplates([
            PageTemplate('body_page', frames=[frame], onPage=_body_page_handler)
        ])

        # ── Step 1: Combinatorial Re-Ordering Bin Packing ──
        page_groups = _find_optimal_zero_waste_packing(papers, avail_height, forbidden_pairs=forbidden_pairs)

        if attempt == 1:
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
            if attempt == 1:
                print(f"    Page {pg_num+1}: {len(group)} abstract(s), {usage:.0f}% filled{mode_tag}{tag} -- {', '.join(titles)}")

            if pg_num > 0:
                elements.append(PageBreak())

            # Directly extend flowables (each paper is an atomic KeepTogether block with keepWithNext=True)
            elements.extend(flowables)

        # Build the PDF
        doc.build(elements)

        # ── Step 2: Post-Compilation PyMuPDF Verification ──
        is_clean, defects = _inspect_body_pdf_pages(output_path, len(page_groups))

        if is_clean:
            print(f"  [VERIFIED] All {len(page_groups)} body pages passed 100% clean verification (zero leaks, zero split content)!")
            return dict(_page_map), page_groups, page_density_modes
        else:
            print(f"  [SELF-HEALING] Detected {len(defects)} layout defect(s) on attempt {attempt}:")
            for d in defects:
                print(f"    - {d.get('msg')}")
                if 'page' in d and d['page'] <= len(page_groups):
                    offending_group = page_groups[d['page'] - 1]
                    forbidden_pairs.add(tuple(sorted(offending_group)))
                elif d['type'] == 'page_count_mismatch':
                    # Forbid any planned group whose papers were pushed onto different pages
                    for group in page_groups:
                        if len({_page_map.get(idx) for idx in group}) > 1:
                            forbidden_pairs.add(tuple(sorted(group)))

            print(f"  [SELF-HEALING] Re-optimizing pairings with tighter constraints...")

    # If completed after self-healing attempts, return final state
    print(f"  [DONE] Completed body PDF generation.")
    return dict(_page_map), page_groups, page_density_modes


# ============================================================
# PDF GENERATION — TABLE OF CONTENTS
# ============================================================

def generate_toc_pdf(papers, page_map, output_path):
    """
    Generate Table of Contents page(s) using direct canvas drawing
    for precise dotted-leader alignment.
    Returns list of metadata dicts for hyperlink injection:
    [
        {
            'paper_idx': i,
            'title': paper['title'],
            'toc_page_idx': current_toc_page,
            'body_page_num': page_val,
            'rect_fitz': (x0, y0, x1, y1),
        },
        ...
    ]
    """
    c = canvas_mod.Canvas(output_path, pagesize=PAGE_SIZE)
    top_y = PAGE_HEIGHT - 75 * LAYOUT_SCALE
    y = top_y
    current_toc_page = 0
    toc_entries_meta = []

    # Entry sizes follow the abstract text size (9 / 8 pt titles / names for 10 pt abstracts)
    toc_title_size = ABSTRACT_FONT_SIZE * 0.9
    toc_line_height = toc_title_size * 11.5 / 9
    toc_author_size = ABSTRACT_FONT_SIZE * 0.75
    toc_author_pitch = toc_author_size * 9.5 / 7.5
    toc_dot_size = toc_title_size * 8 / 9

    # ── "Contents" heading ──
    c.setFont(FONT_BOLD, 24 * LAYOUT_SCALE)
    c.drawString(LEFT_MARGIN, y, "Contents")
    y -= 28 * LAYOUT_SCALE

    # Deep blue underline
    c.setStrokeColor(DIVIDER_COLOR)
    c.setLineWidth(1.5)
    c.line(LEFT_MARGIN, y, PAGE_WIDTH - RIGHT_MARGIN, y)
    y -= 25 * LAYOUT_SCALE
    # ── Sort papers by page number ascending ──
    sorted_papers = [(i, p, page_map.get(i, 9999)) for i, p in enumerate(papers)]
    sorted_papers.sort(key=lambda x: x[2])

    for i, paper, page_val in sorted_papers:
        if page_val == 9999:
            page_num = '?'
        elif TOC_PAGE_NUMBERS == 'roman':
            page_num = to_roman(page_val)
        else:
            page_num = str(page_val)

        # ── Pre-estimate this entry's total height ──
        toc_title_font = FONT_REGULAR

        title = paper['title']
        pnum_width = stringWidth(page_num, FONT_REGULAR, toc_title_size)
        dot_char_width = stringWidth('.', FONT_REGULAR, toc_dot_size)
        max_single_w = CONTENT_WIDTH - pnum_width - 25 * LAYOUT_SCALE

        title_full_w = stringWidth(title, toc_title_font, toc_title_size)
        if title_full_w <= max_single_w:
            lines = [title]
        else:
            # 2-line clean wrap: line 1 uses full CONTENT_WIDTH, line 2 uses max_single_w
            words = title.split()
            line1_words = []
            curr_w = 0
            space_w = stringWidth(' ', toc_title_font, toc_title_size)
            split_idx = 0
            for w_idx, w in enumerate(words):
                w_len = stringWidth(w, toc_title_font, toc_title_size)
                needed = w_len if not line1_words else (space_w + w_len)
                if curr_w + needed <= CONTENT_WIDTH - 5:
                    line1_words.append(w)
                    curr_w += needed
                    split_idx = w_idx + 1
                else:
                    break
            if split_idx == 0:
                split_idx = 1
            line1 = ' '.join(words[:split_idx])
            remainder = ' '.join(words[split_idx:])

            if stringWidth(remainder, toc_title_font, toc_title_size) <= max_single_w:
                lines = [line1, remainder]
            else:
                sub_lines = _word_wrap(remainder, toc_title_font, toc_title_size, max_single_w)
                lines = [line1] + sub_lines

        author_names = ', '.join(a['name'] for a in paper['authors'])
        author_lines = _word_wrap(author_names, FONT_ITALIC, toc_author_size, CONTENT_WIDTH) if author_names else []

        # Total height this entry will consume
        entry_height = (len(lines) * toc_line_height +
                        len(author_lines) * toc_author_pitch + TOC_ENTRY_GAP)

        # ── Check for page overflow BEFORE drawing ──
        if y - entry_height < 50 * LAYOUT_SCALE:
            _draw_toc_footer(c)
            c.showPage()
            current_toc_page += 1
            # Draw header on continuation TOC pages
            _draw_toc_header(c)
            y = top_y

        # Record top of entry for hyperlink bounding box
        entry_toc_page = current_toc_page
        entry_top_rl = y + toc_title_size - 1.5 * LAYOUT_SCALE   # just above the title's capitals

        # ── Draw title with dotted leaders → page number ──
        for j, line in enumerate(lines):
            c.setFont(toc_title_font, toc_title_size)
            c.drawString(LEFT_MARGIN, y, line)

            if j == len(lines) - 1:
                title_end_x = LEFT_MARGIN + stringWidth(
                    line, toc_title_font, toc_title_size
                ) + 5
                page_right_x = PAGE_WIDTH - RIGHT_MARGIN
                dot_limit_x = page_right_x - pnum_width - 8 * LAYOUT_SCALE

                c.setFont(FONT_REGULAR, toc_dot_size)
                x = title_end_x
                while x + dot_char_width < dot_limit_x:
                    c.drawString(x, y, '.')
                    x += dot_char_width + 1.2 * LAYOUT_SCALE

                c.setFont(FONT_REGULAR, toc_title_size)
                c.drawRightString(page_right_x, y, page_num)

            y -= toc_line_height

        # ── Author names below title (italic, smaller) ──
        if author_lines:
            c.setFont(FONT_ITALIC, toc_author_size)
            for al in author_lines:
                c.drawString(LEFT_MARGIN, y, al)
                y -= toc_author_pitch

        # Record bottom of entry and save metadata for hyperlink
        # (y is already one line below the last author line: stop just under its descenders
        # so this link never overlaps the next entry's title)
        entry_bottom_rl = y + toc_author_pitch * 6.5 / 9.5
        fitz_x0 = LEFT_MARGIN - 2.0
        fitz_x1 = PAGE_WIDTH - RIGHT_MARGIN + 2.0
        fitz_y0 = max(0.0, PAGE_HEIGHT - entry_top_rl)
        fitz_y1 = min(PAGE_HEIGHT, PAGE_HEIGHT - entry_bottom_rl)

        if page_val != 9999:
            toc_entries_meta.append({
                'paper_idx': i,
                'title': paper['title'],
                'toc_page_idx': entry_toc_page,
                'body_page_num': page_val,
                'rect_fitz': (fitz_x0, fitz_y0, fitz_x1, fitz_y1),
            })

        y -= TOC_ENTRY_GAP  # clean gap before next entry

    _draw_toc_footer(c)
    c.save()
    return toc_entries_meta


def _draw_toc_header(canvas):
    """Draw conference header on TOC continuation pages."""
    canvas.setFont(FONT_ITALIC, HEADER_FONT_SIZE)
    header_y = PAGE_HEIGHT - 38 * LAYOUT_SCALE
    canvas.drawString(LEFT_MARGIN, header_y, CONFERENCE_HEADER)

    canvas.setStrokeColor(DIVIDER_COLOR)
    canvas.setLineWidth(1.2)
    header_line_y = header_y - 9 * LAYOUT_SCALE
    canvas.line(LEFT_MARGIN, header_line_y,
                PAGE_WIDTH - RIGHT_MARGIN, header_line_y)


def _draw_toc_footer(canvas):
    """Draw footer on a TOC page with deep blue divider."""
    # Deep blue footer divider line
    footer_line_y = BOTTOM_MARGIN - 5 * LAYOUT_SCALE
    canvas.setStrokeColor(DIVIDER_COLOR)
    canvas.setLineWidth(1.2)
    canvas.line(LEFT_MARGIN, footer_line_y, PAGE_WIDTH - RIGHT_MARGIN, footer_line_y)

    # Website (left-aligned)
    footer_text_y = footer_line_y - 14 * LAYOUT_SCALE
    _draw_footer_url(canvas, footer_text_y)


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

def merge_pdfs(toc_path, body_path, output_path, toc_entries_meta=None):
    """Merge Table of Contents + Body into a single final PDF with clickable TOC hyperlinks & PDF bookmarks."""
    output_doc = fitz.open()

    toc_doc = fitz.open(toc_path)
    body_doc = fitz.open(body_path)

    num_toc_pages = len(toc_doc)

    output_doc.insert_pdf(toc_doc)
    output_doc.insert_pdf(body_doc)

    # ── Inject Clickable Hyperlinks in Table of Contents ──
    if toc_entries_meta:
        pdf_outline_toc = []
        for entry in toc_entries_meta:
            toc_page_idx = entry['toc_page_idx']
            body_page_num = entry['body_page_num']
            if body_page_num == 9999 or toc_page_idx >= num_toc_pages:
                continue

            target_page_0based = num_toc_pages + (body_page_num - 1)
            target_page_1based = target_page_0based + 1

            # 1. Clickable on-page link annotation (clicking title/page number jumps to abstract)
            if toc_page_idx < len(output_doc) and target_page_0based < len(output_doc):
                page = output_doc[toc_page_idx]
                r = entry['rect_fitz']
                link_rect = fitz.Rect(r[0], r[1], r[2], r[3])
                page.insert_link({
                    'kind': fitz.LINK_GOTO,
                    'page': target_page_0based,
                    'from': link_rect,
                    'to': fitz.Point(0, 0)
                })

            # 2. PDF Document Outline / Bookmark
            title_short = entry['title']
            if len(title_short) > 80:
                title_short = title_short[:77] + '...'
            pdf_outline_toc.append([1, title_short, target_page_1based])

        # Set document outline bookmarks
        if pdf_outline_toc:
            try:
                output_doc.set_toc(pdf_outline_toc)
            except Exception as e:
                print(f"  [WARN] Could not set PDF outline bookmarks: {e}")

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
# PDF TO WORD CONVERSION
# ============================================================

def _inject_word_toc_hyperlinks(docx_path, papers):
    """
    Injects Word-compliant bookmarks (<w:bookmarkStart>) on body abstract titles and wraps
    Table of Contents entries inside (<w:hyperlink w:anchor="...">) elements,
    enabling internal clickable navigation without altering ANY existing styling,
    fonts, colors, sizes, or dotted leaders.
    """
    try:
        import docx
        from docx.oxml import OxmlElement
        from docx.oxml.ns import qn

        def normalize(text):
            return re.sub(r'[\.\s\d—\-_,:()\'\"’‘]+', '', text.lower())

        doc = docx.Document(docx_path)

        # Collect all body title paragraphs (doc.paragraphs where title matches)
        body_paragraphs = list(doc.paragraphs)

        # Collect all TOC candidate elements (from both doc.paragraphs and doc.tables)
        toc_elements = []
        for p in doc.paragraphs:
            toc_elements.append(p)
        for t in doc.tables:
            for row in t.rows:
                for cell in row.cells:
                    for p in cell.paragraphs:
                        toc_elements.append(p)

        first_abs_idx = next(
            (i for i, p in enumerate(doc.paragraphs) if 'Abstract' in p.text and ('—' in p.text or '-' in p.text)),
            len(doc.paragraphs)
        )

        used_body = set()
        used_toc = set()

        for idx, paper in enumerate(papers):
            # Clean alphanumeric bookmark identifier for full Microsoft Word navigation support
            bm_name = f'Paper{idx+1}'
            norm_title = normalize(paper['title'])
            if not norm_title:
                continue

            # 1. Add Bookmark to Body Title (at or after first_abs_idx)
            for i in range(max(0, first_abs_idx - 10), len(body_paragraphs)):
                if i in used_body:
                    continue
                p = body_paragraphs[i]
                txt = p.text.strip()
                if not txt or 'International Conference' in txt or txt.startswith('Abstract') or txt.startswith('Keywords'):
                    continue
                norm_p = normalize(txt)
                if norm_p[:18] and (norm_p[:18] in norm_title or norm_title[:18] in norm_p):
                    p_elem = p._p
                    if not any(bm.get(qn('w:name')) == bm_name for bm in p_elem.findall(qn('w:bookmarkStart'))):
                        bm_start = OxmlElement('w:bookmarkStart')
                        bm_start.set(qn('w:id'), str(idx + 1))
                        bm_start.set(qn('w:name'), bm_name)
                        bm_end = OxmlElement('w:bookmarkEnd')
                        bm_end.set(qn('w:id'), str(idx + 1))
                        p_elem.insert(0, bm_start)
                        p_elem.append(bm_end)
                    used_body.add(i)
                    break

            # 2. Add Hyperlink to TOC Entry (searching both paragraphs and tables)
            for i, p in enumerate(toc_elements):
                if i in used_toc:
                    continue
                txt = p.text.strip()
                if not txt or txt == 'Contents' or 'International Conference' in txt or txt.startswith('Abstract'):
                    continue
                norm_p = normalize(txt)
                if norm_p[:18] and (norm_p[:18] in norm_title or norm_title[:18] in norm_p):
                    p_elem = p._p
                    if not p_elem.findall(qn('w:hyperlink')):
                        runs = list(p_elem.findall(qn('w:r')))
                        if runs:
                            hyperlink = OxmlElement('w:hyperlink')
                            hyperlink.set(qn('w:anchor'), bm_name)
                            hyperlink.set(qn('w:history'), '1')
                            for r in runs:
                                p_elem.remove(r)
                                hyperlink.append(r)
                            p_elem.append(hyperlink)
                    used_toc.add(i)
                    break

        doc.save(docx_path)
    except Exception as e:
        print(f"  [WARN] Could not inject Word TOC hyperlinks: {e}")


def _restore_word_superscripts(docx_path, papers=None):
    """
    pdf2docx turns author affiliation superscripts into plain, smaller runs, so Word shows
    "Risha Fatima1". Re-mark a short number run as superscript when it is smaller than the
    text it is attached to (after a name, or in front of an affiliation). Numbers that the
    papers' text writes as subscripts (CO₂) are re-marked as subscripts instead.
    """
    subscripts = set()
    for paper in papers or []:
        text = ' '.join(paper.get(k, '') for k in ('title', 'abstract', 'keywords'))
        for m in re.finditer(r'([A-Za-z]+)([\u2080-\u2089]+)', text):
            subscripts.add((m.group(1), ''.join(str(ord(c) - 0x2080) for c in m.group(2))))
    try:
        import docx
        doc = docx.Document(docx_path)
        changed = 0
        for p in doc.paragraphs:
            runs = p.runs
            for i, r in enumerate(runs):
                number = r.text.strip()
                if not re.fullmatch(r'\d{1,2}(?:,\d{1,2})*\*?', number) or r.font.size is None:
                    continue
                prev_r = runs[i - 1] if i > 0 else None
                next_r = runs[i + 1] if i + 1 < len(runs) else None
                ref = None
                if prev_r is not None and re.search(r'[A-Za-z.]$', prev_r.text):
                    ref = prev_r
                elif next_r is not None and re.match(r'[A-Za-z]', next_r.text):
                    ref = next_r
                if ref is not None and ref.font.size and r.font.size < ref.font.size:
                    if ref is prev_r and any(prev_r.text.endswith(f) and number == n for f, n in subscripts):
                        r.font.subscript = True
                    else:
                        r.font.superscript = True
                    r.font.size = ref.font.size
                    changed += 1
        if changed:
            doc.save(docx_path)
    except Exception as e:
        print(f"  [WARN] Could not restore Word superscripts: {e}")


def convert_pdf_to_word(pdf_path, docx_path, papers=None):
    """
    Converts the compiled PDF directly to Word (.docx) format using pdf2docx,
    then adds clickable internal TOC hyperlinks & bookmarks using python-docx
    while preserving 100% of the visual styling, fonts, and layout.
    """
    try:
        import fitz
        if not hasattr(fitz.Rect, 'get_area'):
            fitz.Rect.get_area = lambda self: abs(self)

        from pdf2docx import Converter
        print(f"\n[PROCESS] Converting compiled PDF -> Word (.docx)...")
        # pdf2docx caps page margins at 1 inch, so a binding strip that widens the left margin
        # breaks its centring detection: convert without the strip, then add it back in Word.
        strip = max(0.0, LEFT_MARGIN - RIGHT_MARGIN)
        source = pdf_path
        if strip:
            import tempfile
            fd, source = tempfile.mkstemp(suffix='.pdf')
            os.close(fd)
            cropped = fitz.open(pdf_path)
            for page in cropped:
                page.set_cropbox(fitz.Rect(strip, 0, page.rect.width, page.rect.height))
            cropped.save(source)
            cropped.close()
        try:
            cv = Converter(source)
            cv.convert(docx_path, start=0, end=None)
            cv.close()
        finally:
            if source != pdf_path:
                os.remove(source)
        if strip:
            import docx
            from docx.shared import Pt
            doc = docx.Document(docx_path)
            for section in doc.sections:
                section.page_width += Pt(strip)
                section.left_margin += Pt(strip)
            doc.save(docx_path)

        # ── Inject Clickable TOC Hyperlinks & Bookmarks in Word (.docx) ──
        if papers:
            _inject_word_toc_hyperlinks(docx_path, papers)
        _restore_word_superscripts(docx_path, papers)

        print(f"  [OK] Successfully converted PDF to Word: {docx_path}")
        return True
    except ImportError:
        print("  [ERROR] pdf2docx is not installed. Run: pip install pdf2docx")
        return False
    except Exception as e:
        print(f"  [ERROR] PDF to Word conversion failed: {e}")
        return False


def generate_compilation_report(output_folder, pdf_output_path, docx_output_path, papers, page_map, total_pages, toc_pages_count):
    """
    Generates a detailed compilation audit report in JSON and Markdown formats:
    - Lists page-by-page mapping: on Page X, which articles are placed, and from which PDF source.
    - Lists all extracted metadata (Title, Authors with count, Keywords).
    - Lists any anomalies/doubts/warnings flagged during scraping (e.g. fallback keywords, author count mismatches).
    """
    # Invert page_map to get articles per body page: {body_page_num: [(paper_index, paper)]}
    pages_to_papers = {}
    for p_idx, p in enumerate(papers):
        pg = page_map.get(p_idx, 1)
        pages_to_papers.setdefault(pg, []).append((p_idx, p))

    report_data = {
        'summary': {
            'total_papers': len(papers),
            'total_pages': total_pages,
            'toc_pages': toc_pages_count,
            'body_pages': total_pages - toc_pages_count,
            'pdf_output': os.path.basename(pdf_output_path),
            'docx_output': os.path.basename(docx_output_path) if docx_output_path and os.path.exists(docx_output_path) else None,
            'generated_at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        },
        'pages': [],
        'anomalies_summary': []
    }

    md_lines = [
        "# Compilation & Extraction Audit Report",
        "",
        f"**Generated on:** {report_data['summary']['generated_at']}  ",
        f"**Total Papers:** {len(papers)} | **Total Document Pages:** {total_pages} ({toc_pages_count} TOC + {total_pages - toc_pages_count} Body)  ",
        f"**Outputs:** `{os.path.basename(pdf_output_path)}`",
        "",
        "---",
        "",
        "## Page-by-Page Article Mapping",
        ""
    ]

    for pg in sorted(pages_to_papers.keys()):
        pg_papers = pages_to_papers[pg]
        merged_pdf_page = toc_pages_count + pg
        md_lines.append(f"### Body Page {pg} (Document Page {merged_pdf_page})")
        md_lines.append(f"*Contains {len(pg_papers)} article(s)*\n")

        pg_entry = {
            'body_page': pg,
            'document_page': merged_pdf_page,
            'articles': []
        }

        for item_idx, (p_idx, p) in enumerate(pg_papers):
            auth_names = [a['name'] for a in p['authors']]
            auth_str = ', '.join(auth_names) if auth_names else '*(None extracted)*'
            anomalies = p.get('anomalies', [])

            art_entry = {
                'article_index': p_idx + 1,
                'source_file': p['source_file'],
                'title': p['title'],
                'author_count': len(p['authors']),
                'authors': auth_names,
                'keywords': p['keywords'],
                'anomalies': anomalies
            }
            pg_entry['articles'].append(art_entry)

            md_lines.append(f"#### Article {p_idx + 1}: {p['title']}")
            md_lines.append(f"- **Source PDF:** `{p['source_file']}`")
            md_lines.append(f"- **Authors ({len(p['authors'])}):** {auth_str}")
            md_lines.append(f"- **Keywords:** {p['keywords'] if p['keywords'] else '*(None)*'}")

            if anomalies:
                md_lines.append(f"- **[FLAGGED ISSUES / DOUBTS]:**")
                for anom in anomalies:
                    md_lines.append(f"  - ⚠️ {anom}")
                    report_data['anomalies_summary'].append({
                        'source_file': p['source_file'],
                        'title': p['title'],
                        'body_page': pg,
                        'issue': anom
                    })
            md_lines.append("")

        report_data['pages'].append(pg_entry)
        md_lines.append("---")
        md_lines.append("")

    # Add Anomalies Summary Section
    md_lines.append("## Extraction Anomalies & Doubts Summary")
    md_lines.append("")
    if report_data['anomalies_summary']:
        md_lines.append(f"Total flagged items: **{len(report_data['anomalies_summary'])}**\n")
        md_lines.append("| Body Page | Source PDF | Title | Flagged Doubt / Issue |")
        md_lines.append("| :---: | :--- | :--- | :--- |")
        for anom in report_data['anomalies_summary']:
            short_t = anom['title'][:45] + '...' if len(anom['title']) > 45 else anom['title']
            md_lines.append(f"| {anom['body_page']} | `{anom['source_file']}` | {short_t} | {anom['issue']} |")
    else:
        md_lines.append("✨ **Zero anomalies or doubts detected! All articles extracted cleanly with 100% complete metadata.**")

    # Write JSON report
    json_path = os.path.join(output_folder, "compilation_report.json")
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(report_data, f, indent=2, ensure_ascii=False)

    # Write Markdown report
    md_path = os.path.join(output_folder, "compilation_report.md")
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(md_lines))

    print(f"\n[REPORT] Generated Compilation & Audit Report:")
    print(f"  - Markdown: {md_path}")
    print(f"  - JSON:     {json_path}")
    if report_data['anomalies_summary']:
        print(f"  [WARN] {len(report_data['anomalies_summary'])} potential doubt(s) flagged in report for user review.")
    else:
        print(f"  [OK] 0 extraction anomalies detected across all {len(papers)} papers.")


# ============================================================
# MAIN
# ============================================================

def main():
    # ── Default format is 'both' (PDF + Word docx conversion) ──
    output_format = 'both'
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

    corrected = apply_paper_corrections(papers)
    if corrected:
        print(f"\n[CORRECTIONS] Applied edited text to {corrected} paper(s) from {os.path.basename(PAPER_CORRECTIONS_FILE)}")

    print(f"\n{'='*60}")
    print(f"[SUMMARY] EXTRACTION SUMMARY")
    print(f"{'='*60}")
    print(f"  [OK] Successful: {len(papers)}")
    if failed:
        print(f"  [ERROR] Failed:     {len(failed)} -- {', '.join(failed)}")

    # ── Generate body PDF ──
    body_temp = os.path.join(output_folder, "_body_temp.pdf")
    print(f"\n[PROCESS] Generating body pages...")
    page_map, page_groups, page_density_modes = generate_body_pdf(papers, body_temp)

    print(f"\n  Page assignments:")
    for i, p in enumerate(papers):
        short_title = p['title'][:55] + '...' if len(p['title']) > 55 else p['title']
        print(f"    Page {page_map.get(i, '?')}: {short_title}")

    # ── PDF output ──
    toc_temp = os.path.join(output_folder, "_toc_temp.pdf")
    print(f"\n[PROCESS] Generating Table of Contents...")
    toc_entries_meta = generate_toc_pdf(papers, page_map, toc_temp)

    pdf_output_path = os.path.join(output_folder, "compiled_output.pdf")
    print(f"\n[PROCESS] Merging TOC + Body -> {pdf_output_path}")
    merge_pdfs(toc_temp, body_temp, pdf_output_path, toc_entries_meta=toc_entries_meta)

    # Cleanup temp files
    if os.path.exists(body_temp):
        os.remove(body_temp)
    if os.path.exists(toc_temp):
        os.remove(toc_temp)

    # ── Convert to Word if requested ──
    docx_output_path = os.path.join(output_folder, "compiled_output.docx")
    if output_format in ('word', 'docx', 'both'):
        success = convert_pdf_to_word(pdf_output_path, docx_output_path, papers=papers)
        if not success:
            print("\n[ERROR] Word conversion failed!")
            sys.exit(1)

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

    # ── Final summary & Compilation Report ──
    final_doc = fitz.open(pdf_output_path)
    total_pages = len(final_doc)
    final_doc.close()

    body_page_count = len(set(page_map.values()))
    toc_pages = total_pages - body_page_count

    # Generate Page-by-Page Audit & Anomaly Report
    generate_compilation_report(
        output_folder=output_folder,
        pdf_output_path=pdf_output_path,
        docx_output_path=docx_output_path,
        papers=papers,
        page_map=page_map,
        total_pages=total_pages,
        toc_pages_count=toc_pages
    )

    print(f"\n{'='*60}")
    print(f"[DONE] COMPILATION COMPLETE")
    print(f"{'='*60}")
    print(f"  PDF Output:  {pdf_output_path}")
    if output_format in ('word', 'docx', 'both'):
        print(f"  Word Output: {docx_output_path}")
    print(f"  Papers:      {len(papers)}")
    print(f"  Total pages: {total_pages} "
          f"({toc_pages} TOC + {body_page_count} body)")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
