#!/usr/bin/env python3
"""
Extraction accuracy test against hand-written ground truth.

Usage:
    python3 tests/test_extraction.py <pdf_folder> [expected.json] [-v]

Runs extract_paper_data() on every PDF listed in the expected file (PDFs are not
moved or modified) and checks title, author names, abstract start/end and keywords.
Exit code is 0 only when every check passes.
"""

import os
import re
import sys
import io
import json
import contextlib
import unicodedata

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

with contextlib.redirect_stdout(io.StringIO()):
    import scraper  # noqa: E402

HONORIFICS = r'^(?:dr|prof|mr|mrs|ms|er)\.?\s+'


def norm(text):
    """Lowercase, unify dashes/quotes, keep only letters and digits."""
    text = unicodedata.normalize('NFKC', text or '').lower()
    return re.sub(r'[^a-z0-9]+', '', text)


def norm_name(name):
    name = unicodedata.normalize('NFKC', name or '').strip().lower()
    name = re.sub(HONORIFICS, '', name)
    return norm(name)


def check_paper(expected, got):
    """Return a dict of field -> (passed, detail)."""
    res = {}

    res['title'] = (norm(got['title']) == norm(expected['title']),
                    got['title'][:90])

    exp_names = [norm_name(n) for n in expected['authors']]
    got_names = [norm_name(a['name']) for a in got['authors']]
    missing = [n for n, k in zip(expected['authors'], exp_names) if k not in got_names]
    extra = [a['name'] for a, k in zip(got['authors'], got_names) if k not in exp_names]
    in_order = not expected.get('authors_ordered') or got_names == exp_names
    res['authors'] = (not missing and not extra and in_order,
                      f"missing={missing} extra={extra} in_order={in_order}"
                      if (missing or extra or not in_order) else 'ok')

    abstract = norm(got['abstract'])
    starts = abstract.startswith(norm(expected['abs_start']))
    ends = norm(expected['abs_end']) in abstract[-300:]
    res['abstract'] = (starts and ends,
                       'ok' if starts and ends else
                       f"start_ok={starts} end_ok={ends} len={len(got['abstract'])} "
                       f"head='{got['abstract'][:50]}' tail='{got['abstract'][-60:]}'")

    if expected['kw'] is None:
        # No explicit keywords in the source: the extractor must say so (fallback flag)
        flagged = any('No explicit Keywords' in a for a in got['anomalies'])
        res['keywords'] = (flagged, 'ok' if flagged else f"expected fallback flag, got '{got['keywords'][:60]}'")
    else:
        kw = norm(got['keywords'])
        k_start, k_end = norm(expected['kw'][0]), norm(expected['kw'][1])
        ok = kw.startswith(k_start) and kw.endswith(k_end)
        res['keywords'] = (ok, 'ok' if ok else f"len={len(got['keywords'])} got='{got['keywords'][:80]}...{got['keywords'][-40:]}'")

    return res


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('-')]
    verbose = '-v' in sys.argv
    if not args:
        print(__doc__)
        sys.exit(2)
    pdf_folder = args[0]
    expected_path = args[1] if len(args) > 1 else os.path.join(HERE, 'expected_batch2.json')

    with open(expected_path, encoding='utf-8') as f:
        expected_all = {k: v for k, v in json.load(f).items() if not k.startswith('_')}

    fields = ['title', 'authors', 'abstract', 'keywords']
    totals = {f: 0 for f in fields}
    failures = []
    n = 0

    for fname, expected in sorted(expected_all.items()):
        path = os.path.join(pdf_folder, fname)
        if not os.path.exists(path):
            print(f"  [SKIP] {fname} not found in {pdf_folder}")
            continue
        n += 1
        with contextlib.redirect_stdout(io.StringIO()):
            got = scraper.extract_paper_data(path)
        if not got:
            failures.append((fname, 'all', 'extraction returned None'))
            continue
        for field, (ok, detail) in check_paper(expected, got).items():
            if ok:
                totals[field] += 1
            else:
                failures.append((fname, field, detail))
        if verbose:
            print(f"  {fname}: anomalies={got['anomalies']}")

    print(f"\nExtraction accuracy on {n} papers:")
    for field in fields:
        print(f"  {field:9} {totals[field]:3}/{n}")
    print(f"  {'TOTAL':9} {sum(totals.values()):3}/{n * len(fields)}")

    if failures:
        print(f"\nFailures ({len(failures)}):")
        for fname, field, detail in failures:
            print(f"  {fname:9} {field:9} {detail}")
    sys.exit(0 if not failures else 1)


if __name__ == '__main__':
    main()
