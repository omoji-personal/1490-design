#!/usr/bin/env python3
"""Build all room/material/designer/rejected pages from a shared template."""
from pathlib import Path

SITE_DIR = Path(__file__).parent

# Shared CSS extracted from mood-board.html
SHARED_CSS = """
:root {
  --bg: #faf8f4;
  --ink: #2a2622;
  --muted: #6b6660;
  --accent: #8a7a5a;
  --card-bg: #fff;
  --target-tint: #e8efe2;
  --warm-tint: #f7eedc;
  --note-tint: #f0e8d8;
  --reject-tint: #f8e6df;
  --border: #e8e2d6;
  --topnav-h: 48px;
}
@media (max-width: 720px) { :root { --topnav-h: 56px; } }
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }
/* R1 mobile baseline — site-wide horizontal-overflow guard + responsive media. */
html, body { overflow-x: hidden; max-width: 100%; }
img, picture, video { max-width: 100%; height: auto; }
.table-wrapper { width: 100%; }
@media (max-width: 720px) {
  /* R2-UX1: scrollable surfaces get an edge-fade affordance + a visible
   * scrollbar so users know they can swipe. */
  .table-wrapper { overflow-x: auto; -webkit-overflow-scrolling: touch; max-width: 100%;
    position: relative; }
  .table-wrapper::-webkit-scrollbar { height: 6px; }
  .table-wrapper::-webkit-scrollbar-thumb { background: rgba(0,0,0,0.3);
    border-radius: 3px; }
  .table-wrapper::-webkit-scrollbar-track { background: transparent; }
  .topnav-scroller { position: relative; }
  .topnav-scroller::after, .table-wrapper::after {
    content: ""; position: absolute; top: 0; right: 0; bottom: 0;
    width: 24px; pointer-events: none;
    background: linear-gradient(to right, transparent, rgba(0,0,0,0.08)); }
  /* R4-4: scroll-driven animation makes the edge-fade content-aware on
   * Chrome 115+ / modern browsers — it fades out as the user scrolls to
   * the right edge. Older browsers fall back to the always-shown fade. */
  @supports (animation-timeline: scroll(x)) {
    .table-wrapper::after, .topnav-scroller::after {
      animation: edge-fade auto linear;
      animation-timeline: scroll(self x);
      animation-range: 95% 100%;
    }
    @keyframes edge-fade { to { opacity: 0; } }
  }
}
body {
  font-family: -apple-system, BlinkMacSystemFont, "Inter", "Helvetica Neue", system-ui, sans-serif;
  background: var(--bg); color: var(--ink); line-height: 1.55;
  -webkit-font-smoothing: antialiased;
}
nav.topnav {
  position: sticky; top: 0; z-index: 50;
  background: rgba(250, 248, 244, 0.96);
  backdrop-filter: saturate(140%) blur(8px);
  -webkit-backdrop-filter: saturate(140%) blur(8px);
  border-bottom: 1px solid var(--border);
}
/* R2-C1: scroller wraps the inner so absolute dropdowns positioned vs. <nav>
 * (or position:fixed on mobile) escape the horizontal-scroll overflow clip. */
.topnav-scroller { max-width: 1200px; margin: 0 auto; }
.topnav-inner {
  padding: 11px 28px;
  display: flex; gap: 4px; flex-wrap: wrap; align-items: center; font-size: 13px;
}
.topnav-inner .home {
  color: var(--muted); margin-right: 14px; font-weight: 600;
  text-decoration: none;
}
.topnav-inner .home:hover { color: var(--accent); }
.topnav-inner .group-label {
  color: var(--muted); font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px;
  margin: 0 4px 0 12px; font-weight: 600;
}
.topnav-inner a:not(.home) {
  color: var(--ink); text-decoration: none; padding: 4px 10px;
  border-radius: 999px; border: 1px solid var(--border);
}
.topnav-inner a:not(.home):hover { background: var(--card-bg); border-color: var(--accent); }
.topnav-inner a.current { background: var(--warm-tint); border-color: #c9b88a; }
/* Topnav dropdowns: Rooms ▾ + Canon ▾ — CSS-only, accessible via keyboard + hover. */
.topnav-inner details.nav-dropdown { position: relative; display: inline-block; margin: 0; }
.topnav-inner details.nav-dropdown > summary {
  list-style: none; cursor: pointer; color: var(--ink);
  padding: 4px 10px; border-radius: 999px; border: 1px solid var(--border);
  font-size: 13px; user-select: none; display: inline-flex; align-items: center; gap: 4px;
}
.topnav-inner details.nav-dropdown > summary::-webkit-details-marker { display: none; }
.topnav-inner details.nav-dropdown > summary::after {
  content: "\\25BE"; font-size: 9px; color: var(--muted); margin-left: 2px;
}
.topnav-inner details.nav-dropdown > summary:hover { background: var(--card-bg); border-color: var(--accent); }
.topnav-inner details.nav-dropdown[open] > summary { background: var(--warm-tint); border-color: #c9b88a; }
.topnav-inner details.nav-dropdown .nav-dropdown-menu {
  position: absolute; top: 100%; left: 0; margin-top: 4px;
  background: var(--card-bg); border: 1px solid var(--border);
  border-radius: 8px; padding: 6px; box-shadow: 0 4px 16px rgba(42, 38, 34, 0.08);
  min-width: 180px; z-index: 60; display: none; flex-direction: column; gap: 2px;
}
.topnav-inner details.nav-dropdown[open] > .nav-dropdown-menu { display: flex; }
.topnav-inner details.nav-dropdown .nav-dropdown-menu a {
  border: none; padding: 6px 10px; border-radius: 5px; font-size: 13px;
}
.topnav-inner details.nav-dropdown .nav-dropdown-menu a:hover { background: var(--warm-tint); border: none; }
.topnav-inner details.nav-dropdown .nav-dropdown-menu a.current { background: var(--warm-tint); }
/* Hover-reveal alongside click-reveal for mouse users (does not trap focus). */
@media (hover: hover) {
  .topnav-inner details.nav-dropdown:hover > .nav-dropdown-menu { display: flex; }
  .topnav-inner details.nav-dropdown:not([open]):hover > summary { background: var(--card-bg); border-color: var(--accent); }
}

header.page-header { max-width: 1100px; margin: 0 auto; padding: 44px 28px 14px; }
h1 { font-size: 38px; font-weight: 600; letter-spacing: -0.5px; margin: 0 0 10px; line-height: 1.15; }
.subtitle { color: var(--muted); font-size: 17px; margin: 0 0 24px; max-width: 70ch; }

main { max-width: 1100px; margin: 0 auto; padding: 8px 28px 80px; }

.section-header {
  margin: 44px 0 16px;
  border-bottom: 1px solid var(--border);
  padding-bottom: 12px;
  scroll-margin-top: calc(var(--topnav-h) + 22px);
}
.section-header h2 { font-size: 24px; font-weight: 600; margin: 0 0 4px; }
.section-header .count { color: var(--muted); font-size: 13px; }

.note-card {
  background: var(--note-tint);
  border-left: 4px solid var(--accent);
  border-radius: 4px;
  padding: 16px 22px;
  margin: 18px 0;
  font-size: 14.5px;
}
.note-card.warm { background: var(--warm-tint); }
.note-card.target { background: var(--target-tint); border-left-color: #6b8e57; }
.note-card.reject { background: var(--reject-tint); border-left-color: #a85a4a; }
.note-card strong { color: #5c4f2f; }

.grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 20px; }
.grid.three { grid-template-columns: repeat(3, 1fr); gap: 16px; }
.grid.four { grid-template-columns: repeat(4, 1fr); gap: 14px; }

.card {
  background: var(--card-bg); border: 1px solid var(--border);
  border-radius: 10px; overflow: hidden;
  display: flex; flex-direction: column;
}
.card.hero {
  background: var(--warm-tint);
  border: 2px solid #c9b88a;
}
.card img {
  width: 100%; height: auto; aspect-ratio: 4/3; object-fit: cover;
  display: block;
}
.card .meta {
  padding: 12px 14px;
  font-size: 13px;
  line-height: 1.5;
}
.card .meta .title { font-weight: 600; color: var(--ink); }
.card .meta .caption { color: var(--muted); margin-top: 3px; }
.card .meta .tag {
  display: inline-block; font-size: 11px; padding: 2px 8px;
  background: var(--note-tint); color: #5c4f2f;
  border-radius: 999px; margin-top: 6px;
}

.spec-table {
  width: 100%; border-collapse: collapse; font-size: 14px;
  background: var(--card-bg); border: 1px solid var(--border);
  border-radius: 8px;
}
.spec-table th, .spec-table td {
  text-align: left; padding: 10px 14px;
  border-bottom: 1px solid var(--border);
  vertical-align: top;
}
.spec-table th {
  background: var(--warm-tint); color: var(--ink);
  font-weight: 600; font-size: 12.5px;
  text-transform: uppercase; letter-spacing: 0.4px;
}
.spec-table tr:last-child td { border-bottom: none; }

.dims {
  display: flex; gap: 18px; flex-wrap: wrap;
  margin: 12px 0 22px;
}
.dims .dim {
  background: var(--card-bg); border: 1px solid var(--border);
  border-radius: 8px; padding: 10px 14px;
  min-width: 130px;
}
.dims .dim .label { font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.5px; }
.dims .dim .value { font-size: 16px; font-weight: 600; margin-top: 2px; }

ul.bullet { padding-left: 22px; margin: 12px 0; }
ul.bullet li { margin-bottom: 6px; font-size: 14.5px; }

.kill-list { background: var(--reject-tint); border-left: 4px solid #a85a4a; padding: 14px 20px; border-radius: 4px; margin: 16px 0; }
.kill-list strong { color: #7a3a2a; }
.kill-list ul { margin: 8px 0 0; padding-left: 22px; }
.kill-list li { font-size: 14px; color: #5c2a20; margin-bottom: 4px; }

/* R1 mobile baseline — unify on 720px breakpoint to match sourcing_render +
 * build_spec, plus add table overflow-x and topnav touch-target floor. */
@media (max-width: 720px) {
  body { font-size: 16px; }
  h1 { font-size: 28px; }
  .grid, .grid.three, .grid.four { grid-template-columns: 1fr 1fr; }
  main, header.page-header { padding-left: 18px; padding-right: 18px; }
  /* R2-C1: scroll the WRAPPER, not topnav-inner. Absolutely-positioned dropdown
   * menus inside topnav-inner now escape the overflow scope via position:fixed
   * so they don't get clipped on mobile. */
  .topnav-scroller { overflow-x: auto; -webkit-overflow-scrolling: touch;
    scrollbar-width: none; }
  .topnav-scroller::-webkit-scrollbar { display: none; }
  .topnav-inner { padding: 6px 12px; font-size: 13px; gap: 6px;
    flex-wrap: nowrap; }
  .topnav-inner > * { flex: 0 0 auto; }
  .topnav-inner a:not(.home),
  .topnav-inner details.nav-dropdown > summary {
    padding: 8px 12px; font-size: 13px; min-height: 44px;
    display: inline-flex; align-items: center; }
  /* R2-C1: dropdown menus pop out of the horizontal-scroll container by
   * using fixed positioning anchored below the sticky topnav. */
  .topnav-inner details.nav-dropdown[open] > .nav-dropdown-menu {
    position: fixed; top: calc(var(--topnav-h) + 4px); left: 12px; right: 12px;
    margin-top: 0; min-width: 0; max-height: calc(100vh - var(--topnav-h) - 24px);
    overflow-y: auto; }
  /* R2-T2: tags/chips/pills meet WCAG 2.5.5 44px floor on touch devices. */
  .tag, .chip, .pill { min-height: 44px;
    display: inline-flex; align-items: center; padding: 8px 14px;
    box-sizing: border-box; }
  /* R2-T4: in-cell anchors get vertical hit area inside tables on mobile. */
  td a { display: inline-block; padding: 8px 0; min-height: 44px;
    box-sizing: border-box; }
  /* Tables overflow-scroll on mobile (.table-wrapper opt-in for desktop polish). */
  table { display: block; overflow-x: auto; -webkit-overflow-scrolling: touch;
    max-width: 100%; white-space: nowrap; }
  table.mobile-stack { display: table; white-space: normal; overflow-x: visible; }
  /* R2-C2: when a table is wrapped in .table-wrapper, the WRAPPER handles
   * overflow and the child renders naturally (text wraps, max-width follows
   * the wrapper). Without this rule the child is also set to display:block
   * + nowrap, double-wrapping the overflow and forcing horizontal scroll
   * even for tables narrow enough to fit. */
  .table-wrapper > table { display: table; white-space: normal;
    overflow-x: visible; max-width: none; }
  pre, code { word-break: break-word; white-space: pre-wrap; }
}
@media (max-width: 480px) {
  body { font-size: 16px; line-height: 1.5; }
  h1 { font-size: 1.75rem; }
  h2 { font-size: 1.4rem; }
  h3 { font-size: 1.15rem; }
  .grid, .grid.three, .grid.four { grid-template-columns: 1fr; }
}
/* R1-2 / R1-5 / R2-A4 / R2-A5 / R2-A9 / R2-A10: catalog-gap pill + last-updated
   stamp ported from /sourcing renderer so all build_pages.py outputs carry the
   same visual vocabulary. Pills surface in spec tables and inline narrative;
   sage-green VERIFIED variant matches the renderer's locked-row badge. */
.catalog-gap-pill { display: inline-block; background: #fff4d6; color: #8a5a10;
  border: 1px solid #d4a93a; border-radius: 999px; padding: 1px 8px; font-size: 10px;
  font-weight: 700; letter-spacing: 0.4px; margin-left: 6px; vertical-align: middle; }
.catalog-gap-pill.catalog-verified { background: #e8efe2; color: #3a5a3a; border-color: #a4c08a; }
.last-updated { font-size: 12px; color: var(--muted); text-align: center;
  padding: 16px 0 8px; margin: 24px 0 0; border-top: 1px solid var(--border); }
"""

# Topnav — shared across all pages.
# Rooms ▾ + Canon ▾ collapse into CSS-only <details> dropdowns to match the
# pattern produced by sourcing_render_html._build_topnav_html(). All other
# entries (Home, Mood, Spectrum, Decisions, Budget, Sourcing, Suppliers,
# Vendors, Annika, Spec, Materials, Rejected) stay inline.
def topnav(current=""):
    items_main = [
        ("/", "Home"),
        ("/mood-board", "Mood"),
        ("/spectrum", "Spectrum"),
        ("/decisions", "Decisions"),
        ("/budget", "Budget"),
        ("/sourcing", "Sourcing"),
        ("/suppliers", "Suppliers"),
        ("/vendors", "Vendors"),
        ("/for-annika", "Annika"),
        ("/spec", "Spec"),
    ]
    items_rooms = [
        ("/kitchen", "Kitchen"),
        ("/master", "Master"),
        ("/baths", "Baths"),
        ("/lr", "LR"),
        ("/nursery", "Nursery"),
        ("/office", "Office"),
    ]
    items_designers = [
        ("/cathie-hong", "Cathie Hong"),
        ("/owiu", "OWIU"),
        ("/sss", "SSS"),
        ("/jenni-kayne", "Jenni Kayne"),
    ]
    items_extra = [
        ("/materials", "Materials"),
        ("/rejected", "Rejected"),
    ]

    cur_norm = (current or "").strip("/")

    def cls(href):
        return ' class="current"' if href.strip("/") == cur_norm else ""

    def render_inline(items):
        return "".join(f'<a href="{href}"{cls(href)}>{label}</a>' for href, label in items)

    def render_dropdown(label, aria, items):
        open_attr = " open" if any(href.strip("/") == cur_norm for href, _ in items) else ""
        menu_inner = "".join(f'<a href="{href}"{cls(href)}>{lbl}</a>' for href, lbl in items)
        return (
            f'<details class="nav-dropdown"{open_attr} aria-label="{aria}">'
            f'<summary>{label}</summary>'
            f'<div class="nav-dropdown-menu" role="menu">{menu_inner}</div>'
            f'</details>'
        )

    return f"""<nav class="topnav">
  <div class="topnav-scroller">
    <div class="topnav-inner">
      <a href="/" class="home">← 1490 Lively Ridge</a>
      {render_inline(items_main)}
      {render_dropdown("Rooms", "Rooms", items_rooms)}
      {render_dropdown("Canon", "Canon designers", items_designers)}
      {render_inline(items_extra)}
    </div>
  </div>
</nav>
<script>
  /* R4-1: scroll the active topnav pill into view on mount so users on
   * narrow viewports land on `/vendors` etc. with the .current pill
   * centered in the horizontally-scrollable topnav, not offscreen. */
  (function () {{
    const cur = document.querySelector('nav.topnav .current');
    if (cur && cur.scrollIntoView) {{
      cur.scrollIntoView({{block: 'nearest', inline: 'center'}});
    }}
  }})();
</script>
"""

LAST_UPDATED = "2026-05-17"


def page(slug, title, subtitle, body_html, current=None):
    """Generate a full HTML page.

    R1-5 / R2-A5: every page() output carries a footer-style "Last updated"
    stamp via the shared template so the renderer is the single source of
    truth — direct HTML edits to add stamps would revert on re-render.
    """
    current = current or slug
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} · 1490 Lively Ridge</title>
<meta name="description" content="{subtitle[:160]}">
<style>{SHARED_CSS}</style>
</head>
<body>
{topnav(current)}
<header class="page-header">
  <h1>{title}</h1>
  <p class="subtitle">{subtitle}</p>
</header>
<main>
{body_html}
<p class="last-updated">Last updated {LAST_UPDATED}</p>
</main>
</body>
</html>
"""

# =====================================================================
# ROOM PAGES
# =====================================================================

def kitchen_page():
    body = """
<div class="note-card warm">
<strong>Locked anchor:</strong> Cathie Hong's <em>Campbell House</em> kitchen (loved_12). Light oak Shaker base, Carrara waterfall island, brass pendants, Cle Sea Salt zellige backsplash. This is the room with the most construction-locked specs — what's locked here, locked everywhere.
<br><small style="color:var(--muted);">Vendor SKUs and decision status: <a href="/sourcing-kitchen" style="color:var(--accent);">Kitchen sourcing →</a></small>
</div>

<div class="dims">
  <div class="dim"><div class="label">Footprint</div><div class="value">11'-8" × 26'-6"</div></div>
  <div class="dim"><div class="label">Area</div><div class="value">308 sf</div></div>
  <div class="dim"><div class="label">Layout</div><div class="value">No change</div></div>
  <div class="dim"><div class="label">Appliances</div><div class="value">LG range + Bosch DW stay</div></div>
</div>

<section class="section-header"><h2>Locked construction specs</h2></section>
<div class="table-wrapper"><table class="spec-table">
<tr><th>Element</th><th>Spec</th></tr>
<tr><td>Cabinets</td><td>CDGA KraftMaid Vantage light oak Shaker, 30 LF</td></tr>
<tr><td>Counters</td><td>Caesarstone Statuario waterfall island + perimeter</td></tr>
<tr><td>Floor</td><td>Daltile Choice Ivory porcelain <span class="catalog-gap-pill" title="vendor catalog moved — see /sourcing K-FLOOR-TILE">⚠ CATALOG GAP — needs reselection</span><br><small style="color:var(--muted);">Owner reselect at Daltile Norcross — Choice Ivory 24×24 honed porcelain not in current catalog. See <a href="/sourcing#item-K-FLOOR-TILE" style="color:var(--accent);">K-FLOOR-TILE</a>.</small></td></tr>
<tr><td>Backsplash</td><td><strong>PIVOT:</strong> Carrara slab on range wall + Cle Sea Salt zellige counter-to-upper elsewhere (replaces prior Bejmat plan)</td></tr>
<tr><td>Hood</td><td>Vent-A-Hood PRH18-342SS family (42″ Magic Lung, matte black custom color) — order via CDGA / AJ Madison<br><small style="color:var(--muted);">PRH18342SS-BK is the orderable canon hood (Professional Magic Lung, 900 CFM dual blower, BK custom finish). See <a href="/sourcing#item-G3-HOOD" style="color:var(--accent);">G3-HOOD</a>.</small></td></tr>
<tr><td>Sink + faucet</td><td>Stainless undermount + Delta Trinsic Champagne Bronze</td></tr>
<tr><td>Under-cabinet lighting</td><td>Refresh / replace</td></tr>
<tr><td>Pendants</td><td>Rejuvenation Pinnock Cone Aged Brass × 3 — canon-compliant successor to discontinued Schoolhouse Hyatt <span class="catalog-gap-pill" title="vendor catalog moved — see /sourcing K-PENDANTS">⚠ CATALOG GAP — needs reselection</span><br><small style="color:var(--muted);">Owner reselect pending. See <a href="/sourcing#item-K-PENDANTS" style="color:var(--accent);">K-PENDANTS</a>.</small></td></tr>
<tr><td>Hardware</td><td>Rejuvenation/Forge — matte black + lacquered brass mix</td></tr>
<tr><td>Paint</td><td>BM Aura Bath & Spa (wet-room spec for kitchen)</td></tr>
</table></div>

<section class="section-header">
  <h2>Anchor moods</h2>
  <div class="count">5 canonical kitchen references</div>
</section>
<div class="grid">
  <div class="card hero">
    <img src="/images/cathiehong_05.jpg" alt="Campbell Modern kitchen — Cathie Hong">
    <div class="meta">
      <div class="title">Campbell Modern (Cathie Hong) — THE anchor</div>
      <div class="caption">Reeded oak island + Carrara backsplash + brass pendants. The target.</div>
      <span class="tag">cathiehong_05</span>
    </div>
  </div>
  <div class="card">
    <img src="/images/cathiehong_06.jpg" alt="Campbell Modern kitchen angle 2">
    <div class="meta">
      <div class="title">Campbell Modern kitchen — angle 2</div>
      <div class="caption">Different vantage confirms the formula reads from every direction.</div>
      <span class="tag">cathiehong_06</span>
    </div>
  </div>
  <div class="card">
    <img src="/images/owiu_10.jpg" alt="OWIU Brentwood kitchen">
    <div class="meta">
      <div class="title">OWIU Brentwood kitchen</div>
      <div class="caption">Same vocabulary, slightly cooler — boundary of "warm enough."</div>
      <span class="tag">owiu_10</span>
    </div>
  </div>
  <div class="card">
    <img src="/images/lifestyle_01.jpg" alt="Studio LIFE/STYLE Brentwood-2 kitchen">
    <div class="meta">
      <div class="title">Studio LIFE/STYLE Brentwood-2</div>
      <div class="caption">Cream Shaker + oak island + antique brass hood + Calacatta — alt path.</div>
      <span class="tag">lifestyle_01</span>
    </div>
  </div>
</div>

<section class="section-header">
  <h2>The 9-element kitchen signature</h2>
</section>
<ul class="bullet">
<li>Light oak Shaker base cabinets (KraftMaid Vantage tier — premium semi-custom)</li>
<li>Marble counters: Statuario waterfall (not subway tile, not standard quartz)</li>
<li>One warm-wood gesture: the oak island is THE wood gesture; floor stays porcelain, not oak</li>
<li>Lacquered brass hardware mixed with matte black (5:1 brass:black ratio)</li>
<li>Brass pendant lighting — Rejuvenation Pinnock Cone Aged Brass × 3 (canon-compliant successor to discontinued Schoolhouse Hyatt; owner reselect pending — see <a href="/sourcing#item-K-PENDANTS">K-PENDANTS</a>)</li>
<li>Backsplash slab Carrara (range wall) — bookmatched-look continuity to counter</li>
<li>Cle Sea Salt zellige (counter-to-upper elsewhere) — texture without color</li>
<li>One real plant at floor height — kentia palm or bird of paradise (cat-safe)</li>
<li>Restrained ceramic groupings on open shelf above sink — 3 pieces max</li>
</ul>

<div class="kill-list">
<strong>Kitchen kill list:</strong>
<ul>
<li>NO subway tile backsplash</li>
<li>NO white shaker with chrome hardware (modern farmhouse adjacent)</li>
<li>NO open shelving carrying matched-set dinnerware</li>
<li>NO industrial pendants (no Edison cage, no cone metal-shade)</li>
<li>NO painted accent island (the wood IS the accent)</li>
<li>NO butcher block counter (no, even on island)</li>
<li>NO walnut cabinetry (oak is the wood; walnut is accent only and not in kitchen)</li>
</ul>
</div>

<section class="section-header"><h2>Sourcing brief</h2></section>
<div class="table-wrapper"><table class="spec-table">
<tr><th>Item</th><th>Vendor / SKU</th><th>Status</th></tr>
<tr><td>Cabinet quote</td><td>CDGA (404-361-5200) — KraftMaid Vantage light oak Shaker</td><td>Owner action: get quote, push for Vantage volume discount</td></tr>
<tr><td>Counter slab</td><td>Caesarstone Statuario via Atlanta fab shop</td><td>Owner sources sample swatches first</td></tr>
<tr><td>Hood</td><td>Vent-A-Hood PRH18342SS-BK (42″, 900 CFM Magic Lung dual blower, matte black custom)</td><td>Order via CDGA or AJ Madison; ~$3,433 base + ~10% BK custom upcharge; 6-8 wk lead</td></tr>
<tr><td>Backsplash</td><td>Carrara slab (range) + Cle Sea Salt zellige (rest)</td><td>Cle sample box $7 — order now (4-6 wk lead)</td></tr>
<tr><td>Floor tile <span class="catalog-gap-pill">⚠ CATALOG GAP — needs reselection</span></td><td>Daltile Choice Ivory porcelain (needs reselect)</td><td>Owner reselect at Daltile Norcross — Choice Ivory 24×24 honed porcelain not in current catalog (see <a href="/sourcing#item-K-FLOOR-TILE">K-FLOOR-TILE</a>)</td></tr>
<tr><td>Faucet</td><td>Delta Trinsic in Champagne Bronze</td><td>Owner-direct via Build.com Pro account</td></tr>
<tr><td>Pendants <span class="catalog-gap-pill">⚠ CATALOG GAP — needs reselection</span></td><td>Rejuvenation Pinnock Cone Aged Brass × 3 (canon successor to discontinued Hyatt)</td><td>Owner reselect pending — see <a href="/sourcing#item-K-PENDANTS">K-PENDANTS</a></td></tr>
<tr><td>Hardware</td><td>Rejuvenation Westmore/Pinnock + Forge matte black mix</td><td>Owner-direct via Rejuvenation trade account</td></tr>
</table></div>
"""
    return page("/kitchen", "Kitchen", "California Modern Japandi kitchen at 1490 — Cathie Hong Campbell House as the anchor. Most construction-locked room in the house.", body)


def master_page():
    body = """
<div class="note-card warm">
<strong>Annika's domain.</strong> The "new master" is the current Study (8'-11" × 13'-11" = 124 sf). Sound insulation locked between master and future nursery wall. Aesthetic: Jenni Kayne Lake House meets SSS Mandy Moore project.
<br><small style="color:var(--muted);">Vendor SKUs and decision status: <a href="/sourcing-master" style="color:var(--accent);">Master Suite sourcing →</a></small>
</div>

<div class="dims">
  <div class="dim"><div class="label">Footprint</div><div class="value">8'-11" × 13'-11"</div></div>
  <div class="dim"><div class="label">Area</div><div class="value">124 sf (king-bed capable)</div></div>
  <div class="dim"><div class="label">Adjacency</div><div class="value">Master bath + nursery wall</div></div>
  <div class="dim"><div class="label">Light</div><div class="value">South-facing windows</div></div>
</div>

<section class="section-header"><h2>Locked construction specs</h2></section>
<div class="table-wrapper"><table class="spec-table">
<tr><th>Element</th><th>Spec</th></tr>
<tr><td>Floor</td><td>Existing hardwood refinished (Bleach + Rubio Pure)</td></tr>
<tr><td>Walls</td><td>BM White Dove (OC-17) matte — Aura product line</td></tr>
<tr><td>Trim + door</td><td>BM Simply White (OC-117) satin — Aura</td></tr>
<tr><td>Sound insulation</td><td>Rockwool + RC + drywall close-up — wall to nursery</td></tr>
<tr><td>Hardware</td><td>Lacquered brass (Rejuvenation Westmore pulls if any built-in)</td></tr>
<tr><td>Window treatments</td><td>Cream linen Roman shades (sheer + blackout layer)</td></tr>
<tr><td>Lighting</td><td>Bedside sconces — Schoolhouse Princeton or equivalent, brass</td></tr>
</table></div>

<section class="section-header"><h2>Master bath — sourcing notes</h2></section>
<div class="table-wrapper"><table class="spec-table">
<tr><th>Element</th><th>Spec / status</th></tr>
<tr><td>Master bath floor + shower</td><td>Daltile Choice Ivory 24×24 honed porcelain <span class="catalog-gap-pill">⚠ CATALOG GAP — needs reselection</span><br><small style="color:var(--muted);">Choice Ivory 24×24 honed not in current Daltile catalog; owner reselect at Norcross showroom. See <a href="/sourcing#item-MB-TILE-FLOOR" style="color:var(--accent);">MB-TILE-FLOOR</a> and <a href="/baths#master" style="color:var(--accent);">/baths master section</a>.</small></td></tr>
<tr><td>Master bath medicine cabinet</td><td>Pottery Barn Hutchinson recessed (originally spec'd) <span class="catalog-gap-pill">⚠ SPEC ERROR — wrong product class</span><br><small style="color:var(--muted);">PB Hutchinson is a vanity line — no Hutchinson medicine cabinet exists in the PB catalog. Owner reselect (PB Vintage Recessed candidate). See <a href="/sourcing#item-MB-MEDICINE-CABINET" style="color:var(--accent);">MB-MEDICINE-CABINET</a>.</small></td></tr>
<tr><td>Master bath full spec</td><td>See <a href="/baths" style="color:var(--accent);">/baths</a> for vanity, fixtures, tile, sconces, walls, paint.</td></tr>
</table></div>

<section class="section-header">
  <h2>Anchor moods</h2>
  <div class="count">Bedroom canon references</div>
</section>
<div class="grid">
  <div class="card hero">
    <img src="/images/cathiehong_10.jpg" alt="Campbell primary bedroom">
    <div class="meta">
      <div class="title">Campbell primary bedroom (Cathie Hong) — anchor</div>
      <div class="caption">Cream linen bed, light oak nightstands, sheer linen drapes, brass sconces.</div>
      <span class="tag">cathiehong_10</span>
    </div>
  </div>
  <div class="card">
    <img src="/images/jennikayne_04.jpg" alt="Jenni Kayne Lake House bedroom">
    <div class="meta">
      <div class="title">Jenni Kayne Lake House bedroom</div>
      <div class="caption">Same vocabulary slightly more rustic — palette extends without farmhouse.</div>
      <span class="tag">jennikayne_04</span>
    </div>
  </div>
  <div class="card">
    <img src="/images/sss_04.jpg" alt="SSS Mandy Moore bedroom">
    <div class="meta">
      <div class="title">Sarah Sherman Samuel (Mandy Moore) bedroom</div>
      <div class="caption">Mid-century furniture forms, brass sconces, restrained accent.</div>
      <span class="tag">sss_04</span>
    </div>
  </div>
  <div class="card">
    <img src="/images/owiu_09.jpg" alt="OWIU Duane House bedroom">
    <div class="meta">
      <div class="title">OWIU Duane House bedroom</div>
      <div class="caption">Cooler boundary of the canon — the warm-enough threshold.</div>
      <span class="tag">owiu_09</span>
    </div>
  </div>
</div>

<section class="section-header"><h2>Furniture brief (within $30K envelope)</h2></section>
<div class="table-wrapper"><table class="spec-table">
<tr><th>Piece</th><th>Direction</th><th>Vendor lean</th></tr>
<tr><td>Bed frame</td><td>King, upholstered cream linen OR light oak platform</td><td>WE Andes or Article Sven oak</td></tr>
<tr><td>Nightstands ×2</td><td>Light oak, 2-drawer, ~22-26" wide</td><td>WE Hutchinson nightstand or Rejuvenation</td></tr>
<tr><td>Dresser</td><td>Light oak 6-drawer low</td><td>WE Hutchinson 6-drawer</td></tr>
<tr><td>Lamp/sconces</td><td>Lacquered brass bedside sconces, plug-in or hardwired</td><td>Schoolhouse Princeton or Rejuvenation Putman</td></tr>
<tr><td>Rug</td><td>Year 1-3: flat-weave cream/oat 8×10. Year 4+: Beni Ourain.</td><td>Loloi II / Annie Selke flat-weave</td></tr>
<tr><td>Window treatments</td><td>Sheer linen Roman + blackout panels</td><td>Custom or Smith & Noble</td></tr>
<tr><td>Bedding</td><td>Linen — washed natural / oat / sage accent throw</td><td>WE / Coyuchi / Parachute</td></tr>
<tr><td>One color accent</td><td>Sage olive throw OR mustard cushion — ONE only</td><td>WE / vintage</td></tr>
</table></div>

<div class="kill-list">
<strong>Master bedroom kill list:</strong>
<ul>
<li>NO dark walnut bedframe</li>
<li>NO patterned bedding (no florals, no stripes, no plaids)</li>
<li>NO tufted headboard (Athena Calderone aesthetic — rejected)</li>
<li>NO crystal chandelier or polished nickel sconces</li>
<li>NO accent wall paint — keep all 4 walls White Dove</li>
<li>NO multiple color accents — ONE per room</li>
<li>NO mirrored furniture or lucite legs</li>
</ul>
</div>
"""
    return page("/master", "Master Bedroom", "Annika's domain. New master = current Study. King-bed capable. Jenni Kayne + SSS anchor with cream linen + light oak.", body)


def baths_page():
    body = """
<div class="note-card warm">
<strong>Three bath gut.</strong> Master ($23,500 honest), Hall ($15,400), Basement ¾ ($11,800 → $17K honest). Cle Bejmat is master ONLY (kitchen pivoted to Carrara + Sea Salt zellige). Delta Trinsic Champagne Bronze plumbing is the non-negotiable contract callout across all three.
<br><small style="color:var(--muted);">Vendor SKUs and decision status: <a href="/sourcing-baths" style="color:var(--accent);">Baths sourcing →</a></small>
</div>

<section class="section-header">
  <h2>Master bath — $23,500 honest</h2>
  <div class="count">33 sf · vanity wall 48"</div>
</section>
<div class="grid">
  <div class="card">
    <img src="/images/cathiehong_11.jpg" alt="Cathie Hong marble vanity bath">
    <div class="meta">
      <div class="title">Cathie Hong marble bath vanity</div>
      <div class="caption">Light oak vanity + marble + lacquered brass fixtures — master direction.</div>
      <span class="tag">cathiehong_11</span>
    </div>
  </div>
  <div class="card">
    <img src="/images/cathiehong_09.jpg" alt="Cathie Hong bath alt">
    <div class="meta">
      <div class="title">Cathie Hong bath alt</div>
      <div class="caption">Curbless walk-in shower direction with frameless glass.</div>
      <span class="tag">cathiehong_09</span>
    </div>
  </div>
  <div class="card">
    <img src="/images/lifestyle_04.jpg" alt="Studio LIFE/STYLE primary bath">
    <div class="meta">
      <div class="title">Studio LIFE/STYLE primary bath</div>
      <div class="caption">Light oak vanity + Calacatta + brass — closest alt to our master spec.</div>
      <span class="tag">lifestyle_04</span>
    </div>
  </div>
</div>
<div class="table-wrapper"><table class="spec-table">
<tr><th>Element</th><th>Spec</th></tr>
<tr><td>Vanity</td><td>WE Hutchinson 36" Single, blonde oak</td></tr>
<tr><td>Toilet</td><td>Toto Drake II One-Piece + Toto Washlet C5</td></tr>
<tr><td>Shower walls</td><td>Cle Weathered White Bejmat 2×6 (master ONLY)</td></tr>
<tr><td>Shower floor / drain</td><td>Daltile Choice Ivory 24×24 honed + Schluter linear drain <span class="catalog-gap-pill">⚠ CATALOG GAP — needs reselection</span><br><small style="color:var(--muted);">Daltile Choice Ivory 24×24 honed porcelain not in current catalog; owner reselect — see <a href="/sourcing#item-MB-TILE-FLOOR" style="color:var(--accent);">MB-TILE-FLOOR</a>.</small></td></tr>
<tr><td>Shower glass</td><td>Frameless 48×36 walk-in (curbless)</td></tr>
<tr><td>Floor</td><td>Daltile Choice Ivory + heated mat (whole bath) <span class="catalog-gap-pill">⚠ CATALOG GAP — needs reselection</span><br><small style="color:var(--muted);">Floor SKU shares MB-TILE-FLOOR reselect.</small></td></tr>
<tr><td>Faucet / shower</td><td>Delta Trinsic in Champagne Bronze (NOT chrome)</td></tr>
<tr><td>Sconces</td><td>Schoolhouse Princeton — flanking mirror</td></tr>
<tr><td>Medicine cabinet</td><td>Pottery Barn Hutchinson recessed <span class="catalog-gap-pill">⚠ SPEC ERROR — wrong product class</span><br><small style="color:var(--muted);">Hutchinson is a PB vanity line — no Hutchinson medicine cabinet exists in PB catalog. Owner reselect (PB Vintage Recessed candidate) — see <a href="/sourcing#item-MB-MEDICINE-CABINET" style="color:var(--accent);">MB-MEDICINE-CABINET</a>.</small></td></tr>
<tr><td>Door</td><td>Pocket door — premium hardware</td></tr>
<tr><td>Exhaust</td><td>New w/ wall vent (humidity microclimate spec)</td></tr>
</table></div>

<section class="section-header">
  <h2>Hall bath — $15,400 honest</h2>
  <div class="count">42 sf · tub install</div>
</section>
<div class="grid">
  <div class="card">
    <img src="/images/jennikayne_05.jpg" alt="Jenni Kayne bath mood">
    <div class="meta">
      <div class="title">Jenni Kayne Lake House bath</div>
      <div class="caption">Soaking tub + light oak + brass + restrained palette.</div>
      <span class="tag">jennikayne_05</span>
    </div>
  </div>
  <div class="card">
    <img src="/images/sss_05.jpg" alt="SSS Mandy Moore bath">
    <div class="meta">
      <div class="title">SSS Mandy Moore bath</div>
      <div class="caption">Mid-century-meets-Japandi bath — alt direction reference.</div>
      <span class="tag">sss_05</span>
    </div>
  </div>
  <div class="card">
    <img src="/images/allprace_04.jpg" alt="Allprace Japandi bath">
    <div class="meta">
      <div class="title">Allprace Japandi bath</div>
      <div class="caption">Freestanding tub + oak vanity + penny tile floor.</div>
      <span class="tag">allprace_04</span>
    </div>
  </div>
</div>
<div class="table-wrapper"><table class="spec-table">
<tr><th>Element</th><th>Spec</th></tr>
<tr><td>Vanity</td><td>WE Hutchinson 36" Single, blonde oak</td></tr>
<tr><td>Toilet</td><td>Toto Drake II Two-Piece + Toto Washlet C5</td></tr>
<tr><td>Tub</td><td>Kohler Bellwether cast iron (60") — alcove install</td></tr>
<tr><td>Wall tile</td><td>Cle Sea Salt 4×4 Petite Zellige (handmade actual zellige; locked per DESIGN_SPEC §6 — replaces prior Bedrosians Cloé character-only)</td></tr>
<tr><td>Floor</td><td>Daltile Portfolio White 12×24 honed</td></tr>
<tr><td>Faucet / shower</td><td>Delta Trinsic in Champagne Bronze</td></tr>
<tr><td>Sconces</td><td>Cedar & Moss — flanking mirror</td></tr>
<tr><td>Mirror</td><td>Framed wood-edge round</td></tr>
<tr><td>Shelf</td><td>Slim wall shelf above tub</td></tr>
</table></div>

<section class="section-header">
  <h2>Basement ¾ bath — $11,800 sheet / $17,000 honest</h2>
  <div class="count">~30 sf · slab cut for shower drain</div>
</section>
<div class="table-wrapper"><table class="spec-table">
<tr><th>Element</th><th>Spec</th></tr>
<tr><td>Vanity</td><td>Pottery Barn Mason 24" wall-mount <span class="catalog-gap-pill">⚠ SPEC ERROR — wrong product class</span><br><small style="color:var(--muted);">PB Mason smallest is 31.5"; no 24" / no wall-mount Mason in PB catalog. Owner reselect (PB Bryston/Sabine/Sinclaire 24-30 candidates) — see <a href="/sourcing#item-BB-VANITY" style="color:var(--accent);">BB-VANITY</a>.</small></td></tr>
<tr><td>Toilet</td><td>Toto Drake II Two-Piece + Toto Washlet C5</td></tr>
<tr><td>Shower</td><td>32×32 neo-angle frameless enclosure</td></tr>
<tr><td>Wall tile</td><td>Cle Sea Salt 4×4 Petite Zellige (match hall — DESIGN_SPEC §6 lock; replaces prior Bedrosians Cloé)</td></tr>
<tr><td>Floor</td><td>Daltile Portfolio (match hall)</td></tr>
<tr><td>Mirror</td><td>Small framed circular</td></tr>
<tr><td>Plumbing</td><td>Slab cut for shower drain ($1.5-2K of the line) + Washlet C5 dedicated GFCI</td></tr>
</table></div>

<div class="kill-list">
<strong>Bath kill list (all three):</strong>
<ul>
<li>NO chrome plumbing — Delta Trinsic Champagne Bronze is the contract callout</li>
<li>NO subway tile</li>
<li>NO Carrara in baths (kitchen only) — Cle/Bedrosians/Daltile is the bath palette</li>
<li>NO Cle Bejmat outside master bath</li>
<li>NO framed shower doors — frameless only</li>
<li>NO white melamine vanities — WE Hutchinson blonde oak only</li>
<li>NO vinyl flooring — porcelain tile only (humidity microclimate)</li>
</ul>
</div>
"""
    return page("/baths", "Bathrooms", "Three bath gut. Master ($23.5K), Hall ($15.4K), Basement ¾ ($17K). Cle Bejmat master-only. Delta Trinsic Champagne Bronze across all.", body)


def lr_page():
    body = """
<div class="note-card warm">
<strong>The most-public room.</strong> Living Room is where guests land first — cocktail-hour, weekly drinks, monthly parties up to 20. Existing LR cabinetry refresh locked at $5,100. Music is huge here — Sony floor-standing speakers + amp + HUE around the couch.
<br><small style="color:var(--muted);">Vendor SKUs and decision status: <a href="/sourcing-lr" style="color:var(--accent);">Living + Dining sourcing →</a></small>
</div>

<div class="dims">
  <div class="dim"><div class="label">Footprint</div><div class="value">12'-10" × 19'-0"</div></div>
  <div class="dim"><div class="label">Area</div><div class="value">244 sf</div></div>
  <div class="dim"><div class="label">TV</div><div class="value">Samsung Frame wall-mounted</div></div>
  <div class="dim"><div class="label">Music</div><div class="value">Sony floor-standing + amp</div></div>
</div>

<section class="section-header"><h2>Locked construction specs</h2></section>
<div class="table-wrapper"><table class="spec-table">
<tr><th>Element</th><th>Spec</th></tr>
<tr><td>Floor</td><td>Existing hardwood refinished (Bleach + Rubio Pure)</td></tr>
<tr><td>Walls</td><td>BM White Dove (OC-17) matte — Aura</td></tr>
<tr><td>Built-in TV cabinetry</td><td>Refresh existing — $5,100 (paint-grade modification, hardware refresh, no full rebuild)</td></tr>
<tr><td>Lighting</td><td>Brass overhead pendant + 2 floor lamps + table lamps. At least one brass fixture per public room.</td></tr>
</table></div>

<section class="section-header">
  <h2>Anchor moods</h2>
  <div class="count">Living room canon references</div>
</section>
<div class="grid">
  <div class="card hero">
    <img src="/images/cathiehong_01.jpg" alt="Campbell Modern LR — Cathie Hong">
    <div class="meta">
      <div class="title">Campbell Modern LR (Cathie Hong) — anchor</div>
      <div class="caption">Cream linen sectional, light oak coffee table, brass floor lamp, sage accent.</div>
      <span class="tag">cathiehong_01</span>
    </div>
  </div>
  <div class="card">
    <img src="/images/jennikayne_02.jpg" alt="Jenni Kayne Lake House LR">
    <div class="meta">
      <div class="title">Jenni Kayne Lake House LR</div>
      <div class="caption">Slightly more rustic — language travels without farmhouse.</div>
      <span class="tag">jennikayne_02</span>
    </div>
  </div>
  <div class="card">
    <img src="/images/owiu_07.jpg" alt="OWIU Duane House LR">
    <div class="meta">
      <div class="title">OWIU Duane House LR (warm project)</div>
      <div class="caption">Boundary of "warm enough" with architectural precision.</div>
      <span class="tag">owiu_07</span>
    </div>
  </div>
  <div class="card">
    <img src="/images/sss_01.jpg" alt="SSS Mandy Moore LR">
    <div class="meta">
      <div class="title">SSS Mandy Moore LR</div>
      <div class="caption">Mid-century forms, restrained ceramic groupings.</div>
      <span class="tag">sss_01</span>
    </div>
  </div>
</div>

<section class="section-header"><h2>Furniture brief (within $30K envelope)</h2></section>
<div class="table-wrapper"><table class="spec-table">
<tr><th>Piece</th><th>Direction</th><th>Vendor lean</th></tr>
<tr><td>Sofa / sectional</td><td>Cream linen Crypton/Perennials performance fabric (pet+kid proof) — Andes or Harmony</td><td>West Elm Andes / Harmony in performance linen</td></tr>
<tr><td>Coffee table</td><td>Light oak, ~48×30, round or rectangle</td><td>Article Sven / WE Anton / Rejuvenation Mast</td></tr>
<tr><td>Accent chair (1)</td><td>Light oak + linen seat (Wishbone-form or paper-cord)</td><td>Article / vintage / Allbirds Atlantic Westside</td></tr>
<tr><td>Floor lamp (1)</td><td>Brass + linen drum shade</td><td>Schoolhouse Apex / Rejuvenation Putman</td></tr>
<tr><td>Table lamps (2)</td><td>Ceramic base + linen shade</td><td>WE / Schoolhouse</td></tr>
<tr><td>Rug</td><td>Year 1-3: flat-weave cream/oat 9×12. Year 4+: Beni Ourain.</td><td>Loloi II flat-weave</td></tr>
<tr><td>Real plant tree</td><td>Cat-safe: kentia palm OR parlor palm OR bird of paradise (NOT fiddle leaf — toxic)</td><td>Local nursery</td></tr>
<tr><td>Ceramic groupings</td><td>3-5 hand-thrown matte-clay pieces per shelf</td><td>Vintage / etsy / local Atlanta makers</td></tr>
<tr><td>Bar zone (architected freestanding shelf)</td><td>Custom or floating walnut accent shelf on street-facing kitchen wall</td><td>Custom millwork (separate budget within construction $25-35K range)</td></tr>
</table></div>

<div class="kill-list">
<strong>LR kill list:</strong>
<ul>
<li>NO patterned sofa — cream linen only</li>
<li>NO tufted upholstery</li>
<li>NO glass coffee table on chrome legs</li>
<li>NO lucite or mirrored furniture</li>
<li>NO matched-set commercial pottery on shelves</li>
<li>NO macramé wall hangings, dreamcatchers, Coachella-boho</li>
<li>NO multiple color accents — sage OR mustard OR rust, ONE per room</li>
</ul>
</div>
"""
    return page("/lr", "Living Room", "The most-public room. Cream linen + light oak + brass anchor. Cocktail-hour ready. $30K furniture envelope.", body)


def nursery_page():
    body = """
<div class="note-card warm">
<strong>Annika's domain.</strong> Kid 1 expected within ~1 year. The future nursery is currently the Guest Bedroom (~125 sf est — needs tape-measure verification). Sound insulation locked between master and nursery wall.
<br><small style="color:var(--muted);">Vendor SKUs and decision status: <a href="/sourcing-nursery" style="color:var(--accent);">Nursery sourcing →</a></small>
</div>

<div class="dims">
  <div class="dim"><div class="label">Footprint</div><div class="value">~9' × 14' est</div></div>
  <div class="dim"><div class="label">Area</div><div class="value">~125 sf</div></div>
  <div class="dim"><div class="label">Verification needed</div><div class="value">Tape-measure</div></div>
</div>

<section class="section-header"><h2>Aesthetic framework</h2></section>
<div class="table-wrapper"><table class="spec-table">
<tr><th>Element</th><th>Direction</th></tr>
<tr><td>Approach</td><td>Same California Modern Japandi palette — cream, plaster, light oak, sage accent. NOT pastel. NOT primary-color nursery.</td></tr>
<tr><td>Floor</td><td>Existing hardwood refinished — soft cream wool rug 5×7 with washable cover</td></tr>
<tr><td>Walls</td><td>BM White Dove (OC-17) matte. NO accent wall.</td></tr>
<tr><td>Crib</td><td>Light oak — Babyletto Hudson / Million Dollar Baby Foothill / Oeuf Sparrow (all in oak/natural)</td></tr>
<tr><td>Glider</td><td>Cream performance linen, lacquered brass legs</td></tr>
<tr><td>Dresser / changer</td><td>Light oak, doubles as changing table</td></tr>
<tr><td>Color accent</td><td>ONE: sage olive curtain OR mustard mobile OR rust throw blanket. Not all three.</td></tr>
<tr><td>Lighting</td><td>Brass overhead pendant (dimmable) + brass sconce or table lamp for night feeds</td></tr>
<tr><td>Mobile / art</td><td>Hand-thrown or hand-woven (no commercial cartoon characters)</td></tr>
<tr><td>Window treatments</td><td>Blackout linen Roman (sheer + blackout)</td></tr>
</table></div>

<section class="section-header"><h2>Mood references</h2></section>
<div class="grid">
  <div class="card">
    <img src="/images/cathiehong_10.jpg" alt="Japandi bedroom palette for nursery">
    <div class="meta">
      <div class="title">Cathie Hong palette — extend to nursery</div>
      <div class="caption">Same canon, smaller scale: light oak + cream linen + restrained accent.</div>
      <span class="tag">cathiehong_10</span>
    </div>
  </div>
  <div class="card">
    <img src="/images/allprace_03.jpg" alt="Allprace plaster bedroom">
    <div class="meta">
      <div class="title">Allprace plaster bedroom direction</div>
      <div class="caption">Plaster walls + oak beams + paper-fan art — extends into a kid's room cleanly.</div>
      <span class="tag">allprace_03</span>
    </div>
  </div>
</div>

<div class="kill-list">
<strong>Nursery kill list:</strong>
<ul>
<li>NO pastels (no baby blue, no baby pink, no mint green)</li>
<li>NO Disney / cartoon characters</li>
<li>NO primary-color stimulation room</li>
<li>NO IKEA white melamine (light oak only)</li>
<li>NO ABC alphabet wall decals</li>
<li>NO mobile with primary-color cartoon shapes</li>
<li>NO matching nursery furniture sets from buybuy BABY</li>
</ul>
</div>

<div class="note-card target">
<strong>Phase plan:</strong> nursery doesn't get built out during P1 reno (timing is post-move-back-in, when arrival is closer). P1 just preps the room: paint + floor refinish + sound insulation wall. Furniture/decor happens in the months before arrival, within the $30K envelope.
</div>
"""
    return page("/nursery", "Nursery", "Annika's domain. Same California Modern Japandi palette extended to nursery — NOT pastel, NOT primary-color. Light oak + cream + ONE accent.", body)


def office_page():
    body = """
<div class="note-card warm">
<strong>Omid's WFH office.</strong> The new office is the current Master Bedroom + attached skylight (10'-1" × 13'-3" = 134 sf). Has the most natural light in the house. South-facing windows + skylight.
<br><small style="color:var(--muted);">Vendor SKUs and decision status: <a href="/sourcing-office" style="color:var(--accent);">Office sourcing →</a></small>
</div>

<div class="dims">
  <div class="dim"><div class="label">Footprint</div><div class="value">10'-1" × 13'-3"</div></div>
  <div class="dim"><div class="label">Area</div><div class="value">134 sf</div></div>
  <div class="dim"><div class="label">Light</div><div class="value">South windows + skylight (kept + shade)</div></div>
  <div class="dim"><div class="label">Use</div><div class="value">WFH primary</div></div>
</div>

<section class="section-header"><h2>Construction specs</h2></section>
<div class="table-wrapper"><table class="spec-table">
<tr><th>Element</th><th>Spec</th></tr>
<tr><td>Floor</td><td>Existing hardwood refinished</td></tr>
<tr><td>Walls</td><td>BM White Dove matte (Aura)</td></tr>
<tr><td>Skylight</td><td>KEEP + add shade (cell shade or sheer linen Roman)</td></tr>
<tr><td>Built-in (optional, within $25-35K custom millwork allowance)</td><td>Light oak built-in desk + bookcase, full wall</td></tr>
<tr><td>Lighting</td><td>Overhead brass pendant + desk lamp (brass, swing-arm)</td></tr>
<tr><td>Electrical</td><td>Cat6 already in scope, surge protector, dedicated computer circuit if WFH-heavy</td></tr>
</table></div>

<section class="section-header"><h2>Mood references</h2></section>
<div class="grid">
  <div class="card hero">
    <img src="/images/owiu_12.jpg" alt="OWIU Wellington Office">
    <div class="meta">
      <div class="title">OWIU Wellington Office — aspirational reference</div>
      <div class="caption">Light oak built-in desk + warm wood acoustic ceiling. The dream.</div>
      <span class="tag">owiu_12</span>
    </div>
  </div>
  <div class="card">
    <img src="/images/cathiehong_03.jpg" alt="Cathie Hong built-in nook">
    <div class="meta">
      <div class="title">Cathie Hong built-in oak nook</div>
      <div class="caption">Smaller-scale built-in oak under window — closer to our 134 sf footprint.</div>
      <span class="tag">cathiehong_03</span>
    </div>
  </div>
</div>

<section class="section-header"><h2>Furniture brief</h2></section>
<div class="table-wrapper"><table class="spec-table">
<tr><th>Piece</th><th>Direction</th><th>Vendor lean</th></tr>
<tr><td>Desk</td><td>Light oak — standing desk capable OR fixed wood top. ~60×30.</td><td>Custom millwork built-in OR Article Madera / WE Hutchinson desk</td></tr>
<tr><td>Office chair</td><td>Ergonomic but visually quiet (no gaming chair).</td><td>Herman Miller Aeron (timeless) or Steelcase Leap</td></tr>
<tr><td>Bookcase / shelving</td><td>Light oak built-in OR freestanding. Hand-thrown ceramic groupings + plants.</td><td>Custom millwork or Rejuvenation Mast</td></tr>
<tr><td>Desk lamp</td><td>Brass swing-arm</td><td>Schoolhouse Hudson swing arm</td></tr>
<tr><td>Rug</td><td>Cream/oat flat-weave 6×9</td><td>Loloi II</td></tr>
<tr><td>Plant</td><td>Kentia palm (cat-safe) under skylight</td><td>Local nursery</td></tr>
</table></div>

<div class="kill-list">
<strong>Office kill list:</strong>
<ul>
<li>NO black industrial desk</li>
<li>NO RGB-anything (cables, monitors, ambient)</li>
<li>NO motivational wall art with capital letters</li>
<li>NO ergonomic furniture in primary colors (Aeron in graphite, not red)</li>
<li>NO Edison-cage pendant lights</li>
</ul>
</div>
"""
    return page("/office", "Office", "Omid's WFH office — current Master BR + skylight. 134 sf, best light in house. Light oak built-in desk + brass + skylight shade.", body)


# =====================================================================
# MATERIALS PAGE
# =====================================================================

def materials_page():
    body = """
<div class="note-card warm">
<strong>Bookmark this page.</strong> Every locked material spec with closeups + vendor + alt options. The owner-facing reference for sample orders + TCW change-order verification.
</div>

<section class="section-header"><h2>Wood floors</h2></section>
<div class="table-wrapper"><table class="spec-table">
<tr><th>Element</th><th>Spec</th><th>Vendor</th></tr>
<tr><td>Refinish process</td><td><strong>Bleach + Rubio Monocoat Pure</strong> — NOT Bona poly + "natural" stain (contract callout)</td><td>Rhodes Hardwood Atlanta — $7.48/sf published</td></tr>
<tr><td>Existing floor</td><td>Red oak strip — refinishing reveals warm-honey-white-oak tone</td><td>—</td></tr>
<tr><td>Basement LVP</td><td>Mid-grade LVP — vapor underlayment + transitions</td><td>Owner-direct (Build.com Pro / Lowe's Pro)</td></tr>
<tr><td>Wood rules</td><td>White oak primary, ash/beech secondary, light walnut accent ONLY. NO dark walnut, NO espresso, NO pickled.</td><td>—</td></tr>
</table></div>

<section class="section-header"><h2>Tile</h2></section>
<div class="table-wrapper"><table class="spec-table">
<tr><th>Where</th><th>Spec</th><th>Vendor / SKU</th></tr>
<tr><td>Master bath shower walls</td><td>Cle Weathered White Bejmat 2×6 — handmade specialty</td><td>cletile.com (master ONLY)</td></tr>
<tr><td>Master bath + Kitchen floor</td><td>Daltile Choice Ivory porcelain 24×24 honed</td><td>Daltile via Atlanta dealer</td></tr>
<tr><td>Hall + Basement bath wall</td><td>Cle Sea Salt 4×4 Petite Zellige — handmade actual zellige (DESIGN_SPEC §6 LOCKED canon; replaces prior Bedrosians Cloé character-only)</td><td>cletile.com</td></tr>
<tr><td>Hall + Basement bath floor</td><td>Daltile Portfolio White 12×24 honed</td><td>Daltile</td></tr>
<tr><td>Kitchen range backsplash (PIVOT)</td><td>Carrara slab — bookmatched or single piece</td><td>Atlanta fab shop slab</td></tr>
<tr><td>Kitchen counter-to-upper (PIVOT)</td><td>Cle Sea Salt 4×4 Petite Zellige — handmade actual zellige (same canon family as hall+basement bath wall)</td><td>cletile.com</td></tr>
</table></div>

<section class="section-header"><h2>Paint</h2></section>
<div class="table-wrapper"><table class="spec-table">
<tr><th>Where</th><th>Color</th><th>Sheen</th><th>Product line</th></tr>
<tr><td>Walls — most rooms</td><td>BM White Dove (OC-17)</td><td>Matte</td><td><strong>BM Aura</strong></td></tr>
<tr><td>Walls — bedroom alt</td><td>SW Accessible Beige (SW 7036)</td><td>Matte</td><td>BM Aura (color-matched)</td></tr>
<tr><td>Bath accent wall</td><td>BM Saybrook Sage (HC-114)</td><td>Matte</td><td>BM Aura</td></tr>
<tr><td>Trim + doors</td><td>BM Simply White (OC-117)</td><td>Satin</td><td>BM Aura</td></tr>
<tr><td>Wet rooms (baths, kitchen, basement)</td><td>same colors</td><td>Matte/eggshell</td><td><strong>BM Aura Bath & Spa</strong></td></tr>
<tr><td>Exterior</td><td>TBD — coordinate with brick</td><td>—</td><td><strong>BM Aura Exterior</strong></td></tr>
</table></div>

<div class="note-card target">
<strong>Why Aura, not Regal Select or ben:</strong> 1490's lot is heavily tree-canopied + close to creek = persistent high humidity year-round. Aura is BM's premium washable + mildew-resistant line. Non-negotiable in this microclimate. Marginal cost ~$30-40/gal premium = $1,500-2,000 total project upcharge.
</div>

<section class="section-header"><h2>Plumbing fixtures</h2></section>
<div class="table-wrapper"><table class="spec-table">
<tr><th>Element</th><th>Spec</th></tr>
<tr><td>Faucet line (all baths + kitchen)</td><td><strong>Delta Trinsic in Champagne Bronze</strong> — contract callout (NOT chrome, NOT polished nickel)</td></tr>
<tr><td>Toilet</td><td>Toto Drake II (One-Piece in master, Two-Piece in hall + basement)</td></tr>
<tr><td>Washlet</td><td>Toto Washlet C5 in all 3 baths — dedicated GFCI per bath</td></tr>
<tr><td>Master vanity</td><td>WE Hutchinson 36" Single blonde oak</td></tr>
<tr><td>Hall vanity</td><td>WE Hutchinson 36" Single blonde oak</td></tr>
<tr><td>Basement vanity</td><td>PB Mason 24" wall-mount <span class="catalog-gap-pill">⚠ SPEC ERROR — wrong product class</span><br><small style="color:var(--muted);">PB Mason smallest is 31.5"; no 24" / no wall-mount Mason in PB catalog. Owner reselect — see <a href="/sourcing#item-BB-VANITY" style="color:var(--accent);">BB-VANITY</a>.</small></td></tr>
<tr><td>Master medicine cabinet</td><td>Pottery Barn Hutchinson recessed (originally spec'd) <span class="catalog-gap-pill">⚠ SPEC ERROR — wrong product class</span><br><small style="color:var(--muted);">Hutchinson is a PB vanity line — no Hutchinson medicine cabinet exists in PB catalog. Owner reselect candidates: PB Vintage Recessed / Vintage Slim. See <a href="/sourcing#item-MB-MEDICINE-CABINET" style="color:var(--accent);">MB-MEDICINE-CABINET</a>.</small></td></tr>
<tr><td>Hall bath tub</td><td>Kohler Bellwether cast iron 60" alcove</td></tr>
<tr><td>Master shower drain</td><td>Schluter linear drain + Kerdi waterproofing system</td></tr>
<tr><td>Kitchen sink</td><td>Stainless undermount (owner-direct, Build.com Pro)</td></tr>
</table></div>

<section class="section-header"><h2>Hardware</h2></section>
<div class="table-wrapper"><table class="spec-table">
<tr><th>Where</th><th>Spec</th><th>Vendor</th></tr>
<tr><td>Kitchen cabinet pulls</td><td>Rejuvenation Westmore/Pinnock + Forge matte black mix (5:1 brass:black)</td><td>Rejuvenation trade account</td></tr>
<tr><td>Front door handleset</td><td>Schoolhouse Mortise OR Rejuvenation Emry — lacquered brass</td><td>Schoolhouse / Rejuvenation trade</td></tr>
<tr><td>Secondary entry door</td><td>Standard matte black or brass — Emtek (less premium)</td><td>Emtek</td></tr>
<tr><td>Interior doors (10)</td><td>Emtek Modern matte black</td><td>Emtek via Build.com</td></tr>
<tr><td>Bath fixtures</td><td>Delta Trinsic Champagne Bronze (faucet + shower trim)</td><td>—</td></tr>
<tr><td>Lighting fixtures</td><td>Schoolhouse Princeton / Hudson / Apex + Rejuvenation Putman</td><td>Schoolhouse + Rejuvenation</td></tr>
</table></div>

<div class="note-card target">
<strong>Patina rule:</strong> LACQUERED brass throughout — "no patina romance." Schoolhouse's lacquered finish stays color-fast, vs unlacquered which develops patina. Owner explicitly chose lacquered (locked decision #4). This is consistent with the warm-but-stays-looking-good philosophy.
</div>

<section class="section-header"><h2>Counters</h2></section>
<div class="table-wrapper"><table class="spec-table">
<tr><th>Where</th><th>Spec</th></tr>
<tr><td>Kitchen island + perimeter</td><td>Caesarstone Statuario waterfall island + perimeter</td></tr>
<tr><td>Bath vanity tops</td><td>Matches respective tile / vanity spec (Hutchinson is integral)</td></tr>
</table></div>

<section class="section-header"><h2>Roof + envelope</h2></section>
<div class="table-wrapper"><table class="spec-table">
<tr><th>Element</th><th>Spec</th></tr>
<tr><td>Shingle</td><td>Premium 50-yr impact with AR (algae-resistant) granules + 10-yr algae warranty</td></tr>
<tr><td>Underlayment</td><td>Synthetic + ice-and-water shield at eaves, valleys, penetrations</td></tr>
<tr><td>Gutter</td><td>Heavy-duty + micro-mesh leaf guard (LeafFilter-tier)</td></tr>
<tr><td>Exterior paint</td><td>BM Aura Exterior — full repaint (humidity microclimate)</td></tr>
</table></div>

<section class="section-header"><h2>Sample order list (owner action)</h2></section>
<div class="note-card warm">
Lead times: Cle = 4-6 weeks. Bedrosians = 2-3 weeks. Daltile = 1 week. Order this weekend or sample arrival pushes construction prep.
</div>
<ul class="bullet">
<li>Cle Bejmat Weathered White sample box ($7 + ship)</li>
<li>Cle Sea Salt 4×4 Petite zellige sample (separate order — DESIGN_SPEC §6 lock for hall + basement bath wall + kitchen counter-to-upper)</li>
<li>Daltile Choice Ivory + Portfolio chip set (free)</li>
<li>Bedrosians Cloé sample (rejected as primary per §6 lock; keep for character-only fallback only if §6 4×4 Petite is unavailable)</li>
<li>BM Aura paint chips: White Dove, Saybrook Sage, Simply White; Aura B&S samples</li>
<li>SW Accessible Beige chip</li>
<li>Rubio Monocoat Pure + Smoke 5% finish samples (Rhodes Hardwood Atlanta or Rubio direct)</li>
<li>Crypton Suede + Perennials Linen swatches (for sofa + drapery)</li>
<li>Rejuvenation Westmore brass + Pinnock pulls samples</li>
<li>Schoolhouse Princeton sconce spec sheet (no sample, but full dimensions)</li>
<li>Caesarstone Statuario slab swatch (full sample, not chip)</li>
</ul>
"""
    return page("/materials", "Materials", "Every locked material spec with vendor + alt options. Owner-facing reference for samples + TCW verification.", body)


# =====================================================================
# DESIGNER FEATURE PAGES
# =====================================================================

def cathie_hong_page():
    body = """
<div class="note-card warm">
<strong>The anchor.</strong> Cathie Hong Interiors is the spine of 1490's canon. Campbell House (Rue Magazine, 2023) is THE single reference that ties the whole direction together — kitchen, LR, dining, primary bedroom all land within the canon.
</div>

<section class="section-header"><h2>Why she anchors</h2></section>
<ul class="bullet">
<li><strong>Warmth without messiness.</strong> Light oak + cream + brass without veering boho or rustic. The exact temperature of "warm Japandi."</li>
<li><strong>Repeatable formula.</strong> Multiple projects (Campbell House, plus 5+ others) hit the same 9-element signature — proves it's a language, not a one-off.</li>
<li><strong>Color discipline.</strong> One real-color accent per room. Never more. Never primary. Never tufted.</li>
<li><strong>California sensibility, transferable to Atlanta.</strong> Her work is climate-agnostic enough that the formula translates to a 1953 Atlanta brick ranch without feeling out-of-place.</li>
</ul>

<section class="section-header">
  <h2>Campbell House — THE spine project</h2>
  <div class="count">Rue Magazine feature, 2023</div>
</section>
<div class="grid">
  <div class="card hero">
    <img src="/images/cathiehong_05.jpg" alt="Campbell Modern kitchen">
    <div class="meta">
      <div class="title">Campbell Modern kitchen</div>
      <div class="caption">Reeded oak island + Carrara backsplash + brass pendants. The kitchen anchor.</div>
      <span class="tag">cathiehong_05</span>
    </div>
  </div>
  <div class="card">
    <img src="/images/cathiehong_01.jpg" alt="Campbell Modern LR">
    <div class="meta">
      <div class="title">Campbell Modern LR</div>
      <div class="caption">Cream linen sectional + light oak coffee table + brass floor lamp.</div>
      <span class="tag">cathiehong_01</span>
    </div>
  </div>
  <div class="card">
    <img src="/images/cathiehong_08.jpg" alt="Campbell Modern dining">
    <div class="meta">
      <div class="title">Campbell Modern dining</div>
      <div class="caption">Wegner wishbone paper-cord chairs + light oak pedestal table.</div>
      <span class="tag">cathiehong_08</span>
    </div>
  </div>
  <div class="card">
    <img src="/images/cathiehong_10.jpg" alt="Campbell Modern bedroom">
    <div class="meta">
      <div class="title">Campbell Modern bedroom</div>
      <div class="caption">Cream linen bed, light oak nightstands, brass sconces.</div>
      <span class="tag">cathiehong_10</span>
    </div>
  </div>
</div>

<section class="section-header"><h2>Kitchen — 3 angles of the same project</h2></section>
<div class="grid three">
  <div class="card">
    <img src="/images/cathiehong_05.jpg" alt="Campbell kitchen angle 1">
    <div class="meta"><div class="title">Angle 1 — island side</div></div>
  </div>
  <div class="card">
    <img src="/images/cathiehong_06.jpg" alt="Campbell kitchen angle 2">
    <div class="meta"><div class="title">Angle 2 — range wall</div></div>
  </div>
  <div class="card">
    <img src="/images/cathiehong_07.jpg" alt="Campbell kitchen angle 3">
    <div class="meta"><div class="title">Angle 3 — into dining</div></div>
  </div>
</div>

<section class="section-header"><h2>LR + entry + nook</h2></section>
<div class="grid">
  <div class="card">
    <img src="/images/cathiehong_02.jpg" alt="LR angle 2">
    <div class="meta"><div class="title">LR alternate angle</div></div>
  </div>
  <div class="card">
    <img src="/images/cathiehong_12.jpg" alt="LR angle 3">
    <div class="meta"><div class="title">LR third angle</div></div>
  </div>
  <div class="card">
    <img src="/images/cathiehong_03.jpg" alt="Built-in oak nook">
    <div class="meta"><div class="title">Built-in oak bench entry</div></div>
  </div>
  <div class="card">
    <img src="/images/cathiehong_04.jpg" alt="Front door entry">
    <div class="meta"><div class="title">Front door entry — Pheasant House</div></div>
  </div>
</div>

<section class="section-header"><h2>Baths — Pheasant House</h2></section>
<div class="grid">
  <div class="card">
    <img src="/images/cathiehong_09.jpg" alt="Pheasant House bath 1">
    <div class="meta"><div class="title">Marble vanity bath</div></div>
  </div>
  <div class="card">
    <img src="/images/cathiehong_11.jpg" alt="Pheasant House bath 2">
    <div class="meta"><div class="title">Marble vanity bath alt</div></div>
  </div>
</div>

<section class="section-header"><h2>What to steal directly</h2></section>
<ul class="bullet">
<li>The kitchen cabinet color + counter + backsplash trinity</li>
<li>The "one warm-wood gesture per surface" discipline (the oak island IS the wood; the floor and built-in stay neutral)</li>
<li>The brass pendant density (3-4 per kitchen, not 1-2 — repetition creates rhythm)</li>
<li>The plant placement convention — kentia palm or bird of paradise (NOT fiddle leaf, which is toxic to cats)</li>
<li>The cream-linen-sofa decisiveness — no patterns, no tufting, just one anchor</li>
<li>The ceramic restraint — 3-5 pieces per surface, never more</li>
</ul>

<div class="note-card target">
<strong>Owner takeaway:</strong> If a decision feels unclear, ask "what would Cathie Hong do here?" She's the tie-breaker.
</div>
"""
    return page("/cathie-hong", "Cathie Hong Interiors", "The anchor designer. Campbell House (Rue Magazine) is THE spine project — kitchen, LR, dining, bedroom all canonical.", body)


def owiu_page():
    body = """
<div class="note-card warm">
<strong>The LA Japandi voice.</strong> OWIU Studio brings the precision and warmth-from-wood that anchors California Modern Japandi. <strong>Only WARM projects.</strong>
</div>

<section class="section-header"><h2>Warm projects (canon)</h2></section>
<ul class="bullet">
<li><strong>Palmero House</strong> (Atwater Village) — kitchen anchor</li>
<li><strong>Ryokan House</strong> — bath + entry anchor</li>
<li><strong>Echo Park Hill House</strong> — LR + dining</li>
<li><strong>Duane House</strong> — full-house warm Japandi</li>
<li><strong>Brentwood Residence</strong> — kitchen + LR boundary of "warm enough"</li>
<li><strong>Wellington Office</strong> — office built-in inspiration</li>
</ul>

<section class="section-header"><h2>Rejected projects (do NOT use)</h2></section>
<div class="kill-list">
<strong>OWIU projects that are NOT canon (too cold/austere/loft-industrial):</strong>
<ul>
<li>Biscuit Loft — too pale, lacks coziness, reads industrial</li>
<li>Glass Ridge — too minimal-to-the-point-of-clinical</li>
</ul>
The boundary is "warm enough." If a project reads austere, it's not us.
</div>

<section class="section-header">
  <h2>Visual canon</h2>
</section>
<div class="grid">
  <div class="card hero">
    <img src="/images/owiu_12.jpg" alt="Wellington Office">
    <div class="meta">
      <div class="title">Wellington Office — aspirational</div>
      <div class="caption">Light oak built-in desk + warm wood acoustic ceiling.</div>
      <span class="tag">owiu_12</span>
    </div>
  </div>
  <div class="card">
    <img src="/images/owiu_10.jpg" alt="Brentwood kitchen">
    <div class="meta">
      <div class="title">Brentwood Residence kitchen</div>
      <div class="caption">Boundary of "warm enough" — confirms the threshold.</div>
      <span class="tag">owiu_10</span>
    </div>
  </div>
  <div class="card">
    <img src="/images/owiu_11.jpg" alt="Brentwood LR">
    <div class="meta">
      <div class="title">Brentwood Residence LR</div>
      <div class="caption">Cream linen + oak + brass — architectural precision.</div>
      <span class="tag">owiu_11</span>
    </div>
  </div>
  <div class="card">
    <img src="/images/owiu_09.jpg" alt="Duane House bedroom">
    <div class="meta">
      <div class="title">Duane House bedroom</div>
      <div class="caption">The cooler edge — useful boundary marker.</div>
      <span class="tag">owiu_09</span>
    </div>
  </div>
</div>

<section class="section-header"><h2>Palmero House (3 angles)</h2></section>
<div class="grid three">
  <div class="card">
    <img src="/images/owiu_01.jpg" alt="Palmero 1">
    <div class="meta"><div class="title">Palmero — angle 1</div></div>
  </div>
  <div class="card">
    <img src="/images/owiu_02.jpg" alt="Palmero 2">
    <div class="meta"><div class="title">Palmero — angle 2</div></div>
  </div>
  <div class="card">
    <img src="/images/owiu_03.jpg" alt="Palmero 3">
    <div class="meta"><div class="title">Palmero — angle 3</div></div>
  </div>
</div>

<section class="section-header"><h2>Echo Park Hill House (3 angles)</h2></section>
<div class="grid three">
  <div class="card">
    <img src="/images/owiu_04.jpg" alt="Echo Park 1">
    <div class="meta"><div class="title">Echo Park — angle 1</div></div>
  </div>
  <div class="card">
    <img src="/images/owiu_05.jpg" alt="Echo Park 2">
    <div class="meta"><div class="title">Echo Park — angle 2</div></div>
  </div>
  <div class="card">
    <img src="/images/owiu_06.jpg" alt="Echo Park 3">
    <div class="meta"><div class="title">Echo Park — angle 3</div></div>
  </div>
</div>

<section class="section-header"><h2>Duane House (3 angles)</h2></section>
<div class="grid three">
  <div class="card">
    <img src="/images/owiu_07.jpg" alt="Duane 1">
    <div class="meta"><div class="title">Duane House — LR</div></div>
  </div>
  <div class="card">
    <img src="/images/owiu_08.jpg" alt="Duane 2">
    <div class="meta"><div class="title">Duane House — alt</div></div>
  </div>
  <div class="card">
    <img src="/images/owiu_09.jpg" alt="Duane 3">
    <div class="meta"><div class="title">Duane House — bedroom</div></div>
  </div>
</div>

<section class="section-header"><h2>What to steal directly</h2></section>
<ul class="bullet">
<li>The light-oak built-in discipline — built-ins are oak, not painted</li>
<li>The wood acoustic ceiling concept (consider for office)</li>
<li>The architectural precision — clean lines, recessed lighting, restrained moldings</li>
<li>The "one bold timber move" idea — a single dramatic oak gesture per room</li>
<li>The skylight handling (relevant for office, current master)</li>
</ul>
"""
    return page("/owiu", "OWIU Studio", "LA Japandi precision. Palmero, Ryokan, Echo Park, Duane, Brentwood, Wellington Office are canon. Biscuit Loft + Glass Ridge are NOT.", body)


def sss_page():
    body = """
<div class="note-card warm">
<strong>Mid-century anchor.</strong> Sarah Sherman Samuel brings mid-century furniture forms + warm wood tones + restrained color into California Modern Japandi. Her Mandy Moore home redesign is the canonical reference.
</div>

<section class="section-header"><h2>Canonical project</h2></section>
<ul class="bullet">
<li><strong>Mandy Moore home redesign</strong> — 1950s LA mid-century ranch (parallel to 1490's 1953 Atlanta brick ranch). Same era of architecture, same warmth goal.</li>
</ul>

<section class="section-header"><h2>Visual canon</h2></section>
<div class="grid">
  <div class="card hero">
    <img src="/images/sss_04.jpg" alt="Mandy Moore bedroom">
    <div class="meta">
      <div class="title">Mandy Moore bedroom</div>
      <div class="caption">Mid-century forms, brass sconces, restrained accent.</div>
      <span class="tag">sss_04</span>
    </div>
  </div>
  <div class="card">
    <img src="/images/sss_01.jpg" alt="Mandy Moore LR">
    <div class="meta">
      <div class="title">Mandy Moore LR</div>
      <div class="caption">Cream linen + light oak coffee table + brass.</div>
      <span class="tag">sss_01</span>
    </div>
  </div>
  <div class="card">
    <img src="/images/sss_02.jpg" alt="Mandy Moore kitchen">
    <div class="meta">
      <div class="title">Mandy Moore kitchen</div>
      <div class="caption">Same canon, mid-century-modern flavor.</div>
      <span class="tag">sss_02</span>
    </div>
  </div>
  <div class="card">
    <img src="/images/sss_03.jpg" alt="Mandy Moore dining">
    <div class="meta">
      <div class="title">Mandy Moore dining</div>
      <div class="caption">Mid-century chairs + light oak table.</div>
      <span class="tag">sss_03</span>
    </div>
  </div>
  <div class="card">
    <img src="/images/sss_05.jpg" alt="Mandy Moore bath">
    <div class="meta">
      <div class="title">Mandy Moore bath</div>
      <div class="caption">Mid-century-meets-Japandi bath direction.</div>
      <span class="tag">sss_05</span>
    </div>
  </div>
</div>

<section class="section-header"><h2>What to steal directly</h2></section>
<ul class="bullet">
<li>The mid-century furniture silhouettes — Wishbone CH24, Aalto, Hans Wegner</li>
<li>The 1950s-ranch-respect approach (relevant: 1490 is also 1953)</li>
<li>The "warm mid-century" palette — cream + oat + sage + brass, never harsh</li>
<li>The brass sconce placement at bedside</li>
<li>The under-skylight handling (relevant for office)</li>
</ul>
"""
    return page("/sss", "Sarah Sherman Samuel", "Mid-century anchor. Mandy Moore home redesign — 1950s LA ranch redesign, parallel to 1490's 1953 Atlanta brick ranch.", body)


def jenni_kayne_page():
    body = """
<div class="note-card warm">
<strong>The "elevated rustic" anchor.</strong> Jenni Kayne Interiors brings a slightly more rustic-warm edge to California Modern Japandi without veering farmhouse. Useful for showing how the canon scales.
</div>

<section class="section-header"><h2>Canonical projects</h2></section>
<ul class="bullet">
<li><strong>Lake House</strong> — relaxed cream-and-oak with elevated craft</li>
<li><strong>Santa Ynez Ranch</strong> — California rustic without farmhouse pastiche</li>
</ul>

<section class="section-header"><h2>Visual canon</h2></section>
<div class="grid">
  <div class="card hero">
    <img src="/images/jennikayne_03.jpg" alt="Lake House dining">
    <div class="meta">
      <div class="title">Lake House dining — hero quality</div>
      <div class="caption">Light oak pedestal, cream linen, Beni Ourain. Photography Tessa Neustadt.</div>
      <span class="tag">jennikayne_03</span>
    </div>
  </div>
  <div class="card">
    <img src="/images/jennikayne_02.jpg" alt="Lake House LR">
    <div class="meta">
      <div class="title">Lake House LR</div>
      <div class="caption">Cream linen + light oak + Beni Ourain (year 4+ direction).</div>
      <span class="tag">jennikayne_02</span>
    </div>
  </div>
  <div class="card">
    <img src="/images/jennikayne_01.jpg" alt="Lake House kitchen">
    <div class="meta">
      <div class="title">Lake House kitchen</div>
      <div class="caption">Slightly more rustic — language extends without farmhouse.</div>
      <span class="tag">jennikayne_01</span>
    </div>
  </div>
  <div class="card">
    <img src="/images/jennikayne_04.jpg" alt="Lake House bedroom">
    <div class="meta">
      <div class="title">Lake House bedroom</div>
      <div class="caption">Cream linen bed + sheer drapes + light oak.</div>
      <span class="tag">jennikayne_04</span>
    </div>
  </div>
  <div class="card">
    <img src="/images/jennikayne_05.jpg" alt="Lake House bath">
    <div class="meta">
      <div class="title">Lake House bath</div>
      <div class="caption">Soaking tub + light oak + brass + restrained palette.</div>
      <span class="tag">jennikayne_05</span>
    </div>
  </div>
</div>

<section class="section-header"><h2>What to steal directly</h2></section>
<ul class="bullet">
<li>The Beni Ourain rug direction (year 4+ target)</li>
<li>The relaxed cream textile layering (without veering boho)</li>
<li>The "elevated rustic" approach — natural materials without farmhouse trappings</li>
<li>The plant density in public rooms — multiple at floor height</li>
</ul>
"""
    return page("/jenni-kayne", "Jenni Kayne Interiors", "Elevated rustic anchor. Lake House + Santa Ynez Ranch — California Modern Japandi with relaxed warmth.", body)


# =====================================================================
# REJECTED PAGE
# =====================================================================

def rejected_page():
    body = """
<div class="note-card reject">
<strong>What we explicitly REJECTED.</strong> These designers and styles are NOT the canon. Knowing the boundaries is as important as knowing the anchors. Each rejection is reasoned, not arbitrary.
</div>

<section class="section-header"><h2>Norm Architects — too austere</h2></section>
<div class="grid">
  <div class="card">
    <img src="/images/rejected_01.jpg" alt="Norm Architects austere 1">
    <div class="meta">
      <div class="title">Norm Architects — austere project 1</div>
      <div class="caption">Pure light, white walls, minimal to the point of clinical.</div>
      <span class="tag">rejected_01</span>
    </div>
  </div>
  <div class="card">
    <img src="/images/rejected_02.jpg" alt="Norm Architects austere 2">
    <div class="meta">
      <div class="title">Norm Architects — austere project 2</div>
      <div class="caption">Beautiful but cold. Scandinavian winter sun, not California morning.</div>
      <span class="tag">rejected_02</span>
    </div>
  </div>
</div>
<div class="note-card reject">
<strong>Why rejected:</strong> Norm's austere work is the platonic ideal of cold Japandi. The owners explicitly want WARM. Cathie Hong's warmth-from-wood beats Norm's purity-from-restraint every time.
</div>

<section class="section-header"><h2>Daytrip Studio — dark London modern</h2></section>
<div class="grid">
  <div class="card">
    <img src="/images/rejected_03.jpg" alt="Daytrip Studio dark floors">
    <div class="meta">
      <div class="title">Daytrip Studio — fumed oak floors</div>
      <div class="caption">Dark-stained walnut/oak floors. Direct opposite of light-oak-wide-plank.</div>
      <span class="tag">rejected_03</span>
    </div>
  </div>
</div>
<div class="note-card reject">
<strong>Why rejected:</strong> Daytrip's hallmark is dark-stained walnut floors + dark moody palettes — directly opposite our locked spec. Beautiful work but wrong temperature for 1490.
</div>

<section class="section-header"><h2>Athena Calderone — Brooklyn classic dark</h2></section>
<div class="grid">
  <div class="card">
    <img src="/images/rejected_04.jpg" alt="Athena Calderone navy plaster">
    <div class="meta">
      <div class="title">Athena Calderone — navy-plaster Brooklyn</div>
      <div class="caption">Saturated walls + dark moody atmosphere.</div>
      <span class="tag">rejected_04</span>
    </div>
  </div>
  <div class="card">
    <img src="/images/rejected_05.jpg" alt="Athena Calderone family room">
    <div class="meta">
      <div class="title">Athena Calderone — family room</div>
      <div class="caption">Tufted velvet + jewel tones + classic-dark aesthetic.</div>
      <span class="tag">rejected_05</span>
    </div>
  </div>
</div>
<div class="note-card reject">
<strong>Why rejected:</strong> Athena's Brooklyn townhouse aesthetic = dark, moody, classic with jewel tones. The opposite of California Modern. Her tufted velvet sofas alone disqualify the direction.
</div>

<section class="section-header"><h2>Heidi Caillier — cottage traditional</h2></section>
<div class="grid">
  <div class="card">
    <img src="/images/rejected_06.jpg" alt="Heidi Caillier Ballard cottage">
    <div class="meta">
      <div class="title">Heidi Caillier — Ballard Cottage dining</div>
      <div class="caption">Cottage traditional — beadboard, classic trim, dark accent paint.</div>
      <span class="tag">rejected_06</span>
    </div>
  </div>
</div>
<div class="note-card reject">
<strong>Why rejected:</strong> Heidi's cottage work uses shiplap, beadboard, board-and-batten — direct contradictions of our kill list. Note: Inverness Cottage was the original anchor signal but we've since refined past it.
</div>

<section class="section-header"><h2>Mahno residential — textile maximalist</h2></section>
<div class="note-card reject">
<strong>Why rejected:</strong> Mahno's work is gorgeous but stacks pattern-on-pattern textiles. We want restraint — ONE color accent per room, never layered patterns. No image included; the principle is "no pattern stacking" rather than rejection of a specific Mahno project.
</div>

<section class="section-header"><h2>Reath Design — saturated jewel-tone</h2></section>
<div class="grid">
  <div class="card">
    <img src="/images/rejected_07.jpg" alt="Reath Design Holmby House">
    <div class="meta">
      <div class="title">Reath Design — Holmby House play room</div>
      <div class="caption">Saturated jewel-tone palette. Terracotta walls + navy ceilings = us with the volume on 11.</div>
      <span class="tag">rejected_07</span>
    </div>
  </div>
</div>
<div class="note-card reject">
<strong>Why rejected:</strong> Reath leans into terracotta walls, navy ceilings, emerald accents — saturated jewel-tone palette. We're cream + plaster + ONE muted accent, never saturated.
</div>

<section class="section-header"><h2>Justina Blakeney / Jungalow — Coachella boho</h2></section>
<div class="grid">
  <div class="card">
    <img src="/images/rejected_08.jpg" alt="Justina Blakeney Jungalow">
    <div class="meta">
      <div class="title">Justina Blakeney / Jungalow</div>
      <div class="caption">Maximalist plant + pattern + macramé + dreamcatchers + kilim revival.</div>
      <span class="tag">rejected_08</span>
    </div>
  </div>
</div>
<div class="note-card reject">
<strong>Why rejected:</strong> Maximalist plant + pattern + macramé + dreamcatchers + kilim revival. We have plants (cat-safe palms) but in restraint. The whole boho-Coachella vocabulary is on the kill list.
</div>

<section class="section-header"><h2>Modern Farmhouse (genre)</h2></section>
<div class="note-card reject">
<strong>Why rejected:</strong> Shiplap + barn doors + black metal grid windows + farmhouse sink + chicken wire + "live laugh love." Not us. Not even close. This is the most-common Atlanta default we're actively avoiding.
</div>

<section class="section-header"><h2>The reconciled kill list</h2></section>
<div class="kill-list">
<strong>Across all rejected anchors, the visual elements we will NEVER use:</strong>
<ul>
<li>Dark-stained or dark walnut floors</li>
<li>Beadboard, shiplap, board-and-batten walls in public rooms</li>
<li>Walnut as PRIMARY cabinetry (accent permitted)</li>
<li>Open shelves carrying matched-set commercial dishware</li>
<li>Saturated wall paint (terracotta, navy, emerald) — single-accent textile is the only color delivery</li>
<li>Gilt mirrors, antlers, taxidermy, William Morris wallpaper, dreamcatchers, macramé walls</li>
<li>Chrome, polished nickel, exposed Edison cages, crystal, dark bronze (light finishes only — lacquered brass + matte black)</li>
<li>Glass coffee tables on chrome legs, lucite, mirrored furniture</li>
<li>Espresso / mahogany / cherry / pickled-whitewash wood finishes</li>
<li>High-saturation kilim revival rugs, pattern-on-pattern textile stacking</li>
<li>Shiplap with barn doors with black metal grid ("modern farmhouse")</li>
<li>Tufted furniture (sofas, headboards)</li>
<li>Patterned upholstery (florals, plaids, stripes)</li>
</ul>
</div>
"""
    return page("/rejected", "Rejected Anti-Patterns", "What we explicitly DID NOT pick. Norm/Daytrip/Athena Calderone/Heidi Caillier/Mahno/Reath/Justina Blakeney + modern farmhouse.", body)


def budget_page():
    body = """
<div class="note-card warm">
<strong>The honest reckoning.</strong> What the renovation costs at Atlanta 2026 market, after two rounds of multi-agent audit. The cap moved up $17K on 2026-05-15 — not because scope grew, but because deeper itemization surfaced costs the prior sheet was carrying implicitly.
</div>

<div class="dims">
  <div class="dim"><div class="label">Cap</div><div class="value">$342K</div></div>
  <div class="dim"><div class="label">All-in projection</div><div class="value">$341,768</div></div>
  <div class="dim"><div class="label">Cushion</div><div class="value">$232</div></div>
  <div class="dim"><div class="label">Contingency</div><div class="value">5.4%</div></div>
</div>

<section class="section-header"><h2>Where it stands today</h2></section>
<div class="table-wrapper"><table class="spec-table">
<tr><th>Line</th><th>$</th></tr>
<tr><td>Construction subtotal (honest, post-correction)</td><td>$312,398</td></tr>
<tr><td>Contingency (5.4% held)</td><td>$16,870</td></tr>
<tr><td>Alternate housing during reno</td><td>$12,500</td></tr>
<tr><td><strong>All-in projection</strong></td><td><strong>$341,768</strong></td></tr>
<tr><td>Cap (revised 2026-05-15)</td><td>$342,000</td></tr>
<tr><td>Cushion</td><td>$232</td></tr>
</table></div>

<section class="section-header"><h2>How we got here — the audit chain</h2></section>

<div class="note-card">
<strong>2026-05-14 — the sheet looked done.</strong> Three-agent re-audit + TCW 2023 floor verification reconciled to <strong>$324,937 all-in</strong> at the $325K cap with $63 of cushion. Contingency was already reduced 11% → 5.4% as the lever to fit.
</div>

<div class="note-card">
<strong>2026-05-15 morning — G1 deep-dive.</strong> A two-agent per-line itemization of Group 1 (Claude + Codex with citations) surfaced <strong>$48,150 of hidden cost in G1 alone</strong>. The single biggest surprise: hardwood refinish with Bleach + Rubio Pure (the locked non-negotiable spec) is a specialty premium process, not a standard refinish — honest cost $11,200, not $5,500. The sheet's "$63 under cap" was structural fiction.
</div>

<div class="note-card">
<strong>2026-05-15 afternoon — full-sheet vet.</strong> Six agents (Codex + Gemini-3-pro + four specialized Claude subagents) extended the line-by-line method to G2 through G7. Total honest gap surfaced: <strong>$85,645 across the sheet</strong>, not just G1.
</div>

<div class="table-wrapper"><table class="spec-table">
<tr><th>Group</th><th>Sheet</th><th>Honest (UP-only)</th><th>Delta</th></tr>
<tr><td>G1 Interior</td><td>$145,930</td><td>$200,800</td><td>+$54,870</td></tr>
<tr><td>G2 Baths</td><td>$42,000</td><td>$55,900</td><td>+$13,900</td></tr>
<tr><td>G3 Kitchen</td><td>$33,000</td><td>$40,800</td><td>+$7,800</td></tr>
<tr><td>G4 Water</td><td>$4,000</td><td>$4,500</td><td>+$500</td></tr>
<tr><td>G5 EV + smart</td><td>$5,500</td><td>$6,000</td><td>+$500</td></tr>
<tr><td>G6 Outdoor</td><td>$47,000</td><td>$53,675</td><td>+$6,675</td></tr>
<tr><td>G7 Soft</td><td>$31,500</td><td>$32,900</td><td>+$1,400</td></tr>
<tr><td><strong>Total honest gap</strong></td><td></td><td></td><td><strong>+$85,645</strong></td></tr>
</table></div>

<div class="note-card">
<strong>Then — audit-overestimate correction.</strong> A line-by-line review of the audit findings caught ~$10K of padding the agents had added: closets priced as four-rooms-all-premium when the real spec is one premium reach-in + three PAX hybrid; exterior doors priced as both-premium when only the front door is the walnut splurge; sheetrock / trim / exterior paint slightly above Atlanta 2026 market; G5 EV cluster overpriced. Real material-only delta to absorb: <strong>$15,968</strong>.
</div>

<section class="section-header"><h2>The HARD RULE that governed the revision</h2></section>

<div class="note-card target">
<strong>Revisions move UP, never DOWN.</strong> Once a line is at TCW 2023 × 1.10 floor or honest 2026 market, it cannot be value-engineered downward as a budget-fit lever. To fit a cap, only three moves are legal: <strong>(a)</strong> reduce contingency %, <strong>(b)</strong> defer entire scope items to Phase 2, <strong>(c)</strong> revise the cap upward. Trimming a line item's dollar figure to make math work is exactly the kind of self-deception the multi-agent process is designed to surface.
</div>

<section class="section-header"><h2>How the gap closes — Path 3 still required</h2></section>

<p>The $85,645 surfaced gap minus $15,968 material-only corrections + $17K cap revision still leaves a labor delta that Path 3 must absorb:</p>

<div class="table-wrapper"><table class="spec-table">
<tr><th>Lever</th><th>Honest ceiling</th></tr>
<tr><td>TCW labor friend rate from 20% → 30% off market</td><td>$15-25K</td></tr>
<tr><td>Owner-direct material trade discounts (Home Depot Pro Xtra, Lowe's Pro, manufacturer-direct on tile / lighting / hardware)</td><td>$5-10K</td></tr>
<tr><td>G6.7 buffer line itemized + negotiated down (hidden 27.6% contingency on outdoor scope)</td><td>$2.5-3K</td></tr>
<tr><td><strong>Path 3 realistic ceiling</strong></td><td><strong>$22.5-38K labor absorption</strong></td></tr>
</table></div>

<div class="kill-list">
<strong>Risk R19 (High probability):</strong> if TCW does NOT absorb the labor delta via aggressive friend rate, all-in projection goes to <strong>$395-415K range</strong>. The TCW change-order email is the gating conversation that resolves Path 3 viability.
</div>

<section class="section-header"><h2>What the cap revision did NOT do</h2></section>

<div class="table-wrapper"><table class="spec-table">
<tr><th>Tempting move</th><th>Why we said no</th></tr>
<tr><td>Defer kitchen full reno to P2</td><td>Five years of patched-together cooking in a 1953 ranch kitchen — quality-of-life cost too high for the savings.</td></tr>
<tr><td>Defer basement ¾ bath</td><td>Adding shower to under-stair half-bath unlocks the basement as a guest suite + future kid-2 zone — high option-value preserved.</td></tr>
<tr><td>Drop hardwood spec back to standard refinish</td><td>Bleach + Rubio is one of two non-negotiable contract callouts — the aesthetic depends on it (avoids pinkish poly tone on red oak).</td></tr>
<tr><td>Cut contingency to 0%</td><td>1953 ranch reno with no permits + waterproofing on contractor-allowance + structural-engineer-letter gap on 2020 kitchen wall. 5.4% is already thin.</td></tr>
<tr><td>Trim 2 exterior doors to keep originals</td><td>Front door is the walnut splurge — the canon Campbell House move. Side door upgrade is the smaller adjacent decision; defer-able if Path 3 underperforms.</td></tr>
</table></div>

<section class="section-header"><h2>Files behind these numbers</h2></section>

<div class="table-wrapper"><table class="spec-table">
<tr><th>Doc</th><th>What it is</th></tr>
<tr><td>scope/TIER_B_FINAL_LOCKED.md</td><td>The canonical sheet — every line, every owner-locked decision, the risk register</td></tr>
<tr><td>audits/2026-05-15-g1-itemization/</td><td>2-agent G1 deep-dive (Claude + Codex), SYNTHESIS.md, $48K surfaced</td></tr>
<tr><td>audits/2026-05-15-full-sheet-vet/</td><td>6-agent full-sheet vet (Codex + Gemini-3-pro + 4 subagents), SYNTHESIS.md, $86K surfaced</td></tr>
<tr><td>audits/2026-05-14-tier-b-recheck/</td><td>The prior 3-agent reckoning + TCW 2023 floor verification (what the new audits built on)</td></tr>
<tr><td>audits/2026-05-14-roof-research/</td><td>Roof material decision (premium shingle vs metal vs stone-coated steel) — locked at $16K shingle</td></tr>
</table></div>

<div class="note-card warm">
<strong>Next gate:</strong> the TCW change-order email. Ten line-itemized asks (G1-G7 full breakdown + G6.7 buffer itemization + Vent-A-Hood SKU verification with CDGA + kitchen backsplash spec reconciliation + Aura paint product-line confirmation + HVAC bundle truth-up + management fee concession). Rick's reply on those specifics is the only data point that resolves whether Path 3 holds at $22-38K or falls short and forces the next cap conversation.
</div>
"""
    return page("/budget", "Budget", "The honest reckoning — $342K cap, $341,768 all-in projection, $232 cushion. How an 8-agent audit chain surfaced $86K of hidden cost and revised the cap up $17K.", body)


# =====================================================================
# MAIN
# =====================================================================

PAGES = [
    ("kitchen.html", kitchen_page),
    ("master.html", master_page),
    ("baths.html", baths_page),
    ("lr.html", lr_page),
    ("nursery.html", nursery_page),
    ("office.html", office_page),
    ("materials.html", materials_page),
    ("cathie-hong.html", cathie_hong_page),
    ("owiu.html", owiu_page),
    ("sss.html", sss_page),
    ("jenni-kayne.html", jenni_kayne_page),
    ("rejected.html", rejected_page),
    ("budget.html", budget_page),
]

if __name__ == "__main__":
    for fname, gen in PAGES:
        path = SITE_DIR / fname
        path.write_text(gen())
        print(f"Wrote {fname} ({path.stat().st_size:,} bytes)")
    print(f"\nGenerated {len(PAGES)} pages.")
