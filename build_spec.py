#!/usr/bin/env python3
"""Render DESIGN_SPEC.md to spec.html with consistent site styling."""
import markdown
from pathlib import Path

SOURCE = Path.home() / "Desktop/HomeAI/design/DESIGN_SPEC.md"
DEST = Path(__file__).parent / "spec.html"

md_text = SOURCE.read_text()

# Convert markdown to HTML
html_body = markdown.markdown(
    md_text,
    extensions=["tables", "fenced_code", "toc", "attr_list", "sane_lists"],
)

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Design Spec · 1490 Lively Ridge</title>
<meta name="description" content="Canonical design spec for 1490 Lively Ridge — California Modern Japandi · 9 principles · canon designers · 7 owner decisions">
<style>
  :root {{
    --bg: #faf8f4;
    --ink: #2a2622;
    --muted: #6b6660;
    --accent: #8a7a5a;
    --card-bg: #fff;
    --warm-tint: #f7eedc;
    --note-tint: #f0e8d8;
    --border: #e8e2d6;
    --target-tint: #e8efe2;
  }}
  * {{ box-sizing: border-box; }}
  html, body {{ margin: 0; padding: 0; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Inter", "Helvetica Neue", system-ui, sans-serif;
    background: var(--bg); color: var(--ink); line-height: 1.65;
    -webkit-font-smoothing: antialiased;
  }}
  nav.topnav {{
    position: sticky; top: 0; z-index: 50;
    background: rgba(250, 248, 244, 0.96);
    backdrop-filter: saturate(140%) blur(8px);
    -webkit-backdrop-filter: saturate(140%) blur(8px);
    border-bottom: 1px solid var(--border);
  }}
  .topnav-inner {{
    max-width: 1200px; margin: 0 auto; padding: 11px 28px;
    display: flex; gap: 4px; flex-wrap: wrap; align-items: center; font-size: 13px;
  }}
  .topnav-inner .home {{
    color: var(--muted); margin-right: 14px; font-weight: 600;
    text-decoration: none;
  }}
  .topnav-inner .home:hover {{ color: var(--accent); }}
  .topnav-inner .group-label {{
    color: var(--muted); font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px;
    margin: 0 4px 0 12px; font-weight: 600;
  }}
  .topnav-inner a:not(.home) {{
    color: var(--ink); text-decoration: none; padding: 4px 10px;
    border-radius: 999px; border: 1px solid var(--border);
  }}
  .topnav-inner a:not(.home):hover {{ background: var(--card-bg); border-color: var(--accent); }}
  .topnav-inner a.current {{ background: #f7eedc; border-color: #c9b88a; }}
  .container {{
    max-width: 880px;
    margin: 0 auto;
    padding: 40px 28px 80px;
  }}
  h1 {{
    font-size: 38px; font-weight: 600; letter-spacing: -0.6px;
    margin: 0 0 24px; line-height: 1.15;
  }}
  h2 {{
    font-size: 24px; font-weight: 600; margin: 48px 0 16px;
    border-top: 1px solid var(--border);
    padding-top: 36px;
  }}
  h3 {{
    font-size: 18px; font-weight: 600; margin: 28px 0 12px;
  }}
  h4 {{
    font-size: 15px; font-weight: 600; margin: 20px 0 10px;
    text-transform: uppercase; letter-spacing: 0.6px; color: var(--accent);
  }}
  p {{ margin: 0 0 16px; font-size: 15.5px; }}
  ul, ol {{ margin: 0 0 16px; padding-left: 24px; font-size: 15.5px; }}
  li {{ margin-bottom: 6px; }}
  strong {{ color: var(--ink); }}
  blockquote {{
    border-left: 3px solid var(--accent);
    margin: 16px 0;
    padding: 4px 0 4px 18px;
    color: var(--muted);
    font-style: italic;
  }}
  code {{
    background: #f0ece4;
    padding: 2px 6px;
    border-radius: 3px;
    font-family: "SF Mono", Menlo, monospace;
    font-size: 13px;
    color: #5c4f2f;
  }}
  pre {{
    background: var(--card-bg);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 16px 18px;
    overflow-x: auto;
    font-size: 13px;
  }}
  pre code {{
    background: none;
    padding: 0;
  }}
  table {{
    width: 100%;
    border-collapse: collapse;
    margin: 16px 0;
    font-size: 14px;
    background: var(--card-bg);
    border: 1px solid var(--border);
    border-radius: 8px;
    overflow: hidden;
  }}
  th, td {{
    text-align: left;
    padding: 10px 14px;
    border-bottom: 1px solid var(--border);
    vertical-align: top;
  }}
  th {{
    background: var(--warm-tint);
    color: var(--ink);
    font-weight: 600;
    font-size: 13px;
    text-transform: uppercase;
    letter-spacing: 0.4px;
  }}
  tr:last-child td {{ border-bottom: none; }}
  td code {{ font-size: 12px; }}
  hr {{
    border: none;
    border-top: 1px solid var(--border);
    margin: 40px 0;
  }}
  a {{
    color: var(--accent);
    text-decoration: none;
    border-bottom: 1px solid rgba(138, 122, 90, 0.3);
  }}
  a:hover {{ border-bottom-color: var(--accent); }}

  @media (max-width: 720px) {{
    .container {{ padding: 24px 18px 60px; }}
    h1 {{ font-size: 28px; }}
    h2 {{ font-size: 21px; }}
    table {{ font-size: 12.5px; }}
    th, td {{ padding: 8px 10px; }}
  }}
</style>
</head>
<body>

<nav class="topnav">
  <div class="topnav-inner">
    <a href="/" class="home">← 1490 Lively Ridge</a>
    <a href="/">Home</a><a href="/mood-board">Mood</a><a href="/spectrum">Spectrum</a><a href="/decisions">Decisions</a><a href="/spec" class="current">Spec</a>
    <span class="group-label">Rooms</span>
    <a href="/kitchen">Kitchen</a><a href="/master">Master</a><a href="/baths">Baths</a><a href="/lr">LR</a><a href="/nursery">Nursery</a><a href="/office">Office</a>
    <span class="group-label">Canon</span>
    <a href="/cathie-hong">Cathie Hong</a><a href="/owiu">OWIU</a><a href="/sss">SSS</a><a href="/jenni-kayne">Jenni Kayne</a>
    <a href="/materials">Materials</a><a href="/rejected">Rejected</a>
  </div>
</nav>

<div class="container">
{html_body}
</div>
</body>
</html>
"""

DEST.write_text(html)
print(f"Wrote {DEST} ({len(html):,} bytes)")
"""
"""
