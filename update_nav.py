#!/usr/bin/env python3
"""Inject the new comprehensive topnav into existing pages."""
import re
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))
from build_pages import topnav

SITE_DIR = Path(__file__).parent

# Pages to update with the new topnav. Tuple of (filename, current_slug_for_highlighting).
PAGES = [
    ("index.html", "/"),
    ("mood-board.html", "/mood-board"),
    ("spectrum.html", "/spectrum"),
    ("decisions.html", "/decisions"),
]

# Pattern to match existing <nav class="topnav">...</nav>
TOPNAV_RE = re.compile(r'<nav class="topnav">.*?</nav>', re.DOTALL)

# Body-open pattern for pages with no existing topnav (mood-board, spectrum)
BODY_OPEN_RE = re.compile(r'(<body[^>]*>)', re.IGNORECASE)

def update(filename, current):
    path = SITE_DIR / filename
    html = path.read_text()
    new_nav = topnav(current).strip()

    if TOPNAV_RE.search(html):
        # Replace existing topnav
        html = TOPNAV_RE.sub(new_nav, html, count=1)
        print(f"  {filename}: replaced existing topnav")
    else:
        # Insert new topnav right after <body>
        html = BODY_OPEN_RE.sub(r'\1\n' + new_nav, html, count=1)
        print(f"  {filename}: injected new topnav after <body>")

    # Also need to inject the topnav CSS if missing
    if 'topnav-inner' not in html or '.topnav-inner .home' not in html:
        # Add a minimal supplementary CSS block (the topnav style)
        topnav_css = """
<style>
nav.topnav { position: sticky; top: 0; z-index: 50; background: rgba(250,248,244,0.96);
  backdrop-filter: saturate(140%) blur(8px); border-bottom: 1px solid #e8e2d6; }
.topnav-inner { max-width: 1200px; margin: 0 auto; padding: 11px 28px; display: flex;
  gap: 4px; flex-wrap: wrap; align-items: center; font-size: 13px; }
.topnav-inner .home { color: #6b6660; margin-right: 14px; font-weight: 600; text-decoration: none; }
.topnav-inner .home:hover { color: #8a7a5a; }
.topnav-inner .group-label { color: #6b6660; font-size: 11px; text-transform: uppercase;
  letter-spacing: 0.5px; margin: 0 4px 0 12px; font-weight: 600; }
.topnav-inner a:not(.home) { color: #2a2622; text-decoration: none; padding: 4px 10px;
  border-radius: 999px; border: 1px solid #e8e2d6; }
.topnav-inner a:not(.home):hover { background: #fff; border-color: #8a7a5a; }
.topnav-inner a.current { background: #f7eedc; border-color: #c9b88a; }
</style>
"""
        html = html.replace('</head>', f'{topnav_css}\n</head>', 1)
        print(f"  {filename}: added topnav CSS to <head>")

    path.write_text(html)

if __name__ == "__main__":
    print("Updating existing pages' topnav:")
    for fname, current in PAGES:
        update(fname, current)
    print("Done.")
