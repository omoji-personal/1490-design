# sourcing_render_html.py
"""Render sourcing data to a static HTML page styled to match /budget and /decisions.
Cards carry data-* attributes for client-side filtering (see filter UI in build_sourcing.py)."""
import re
import yaml
from pathlib import Path
from typing import List, Optional, Dict
from html import escape

from sourcing_schema import Item, Meta
from sourcing_lint import LintFinding
from sourcing_queue import ScheduleLookup, T0_PHASES

SITE_DIR = Path(__file__).parent


def _supplementary_paths(image_path: str, recommend: bool = False) -> list:
    """Given 'images/sourcing/k-faucet-1.jpg', return list of existing supplementary paths.

    Checks two conventions agents used:
    1. Option-level:  images/sourcing/k-faucet-1-b.jpg  (most items)
    2. Item-level:    images/sourcing/k-faucet-b.jpg    (strip trailing -N digit block)
       NOTE: item-level fallback is ONLY used for the recommended (★) option to prevent
       the same -b/-c image from appearing under every vendor option.
    Returns only paths whose files exist on disk.
    """
    if not image_path:
        return []
    base = image_path[:-4]  # strip .jpg
    results = []
    for suffix in ["-b", "-c"]:
        # Convention 1: option-level (always safe — file is keyed to this specific option)
        candidate = f"{base}{suffix}.jpg"
        if (SITE_DIR / candidate).exists():
            results.append(candidate)
            continue  # prefer this; skip item-level if option-level found
        # Convention 2: item-level — only apply for the recommended option to avoid
        # showing the same alternate-view image under every vendor in the options grid.
        if recommend:
            item_base = re.sub(r"-\d+$", "", base)
            if item_base != base:
                candidate2 = f"{item_base}{suffix}.jpg"
                if (SITE_DIR / candidate2).exists():
                    results.append(candidate2)
    return results


STATUS_BADGE = {
    "options_drafted": ("decide-now", "Decide now"),
    "awaiting_sample": ("awaiting-sample", "Awaiting sample"),
    "sample_in_hand": ("sample-in-hand", "Sample in hand"),
    "decided": ("decided", "Decided"),
    "ordered": ("ordered", "Ordered"),
    "received": ("received", "Received"),
    "installed": ("installed", "Installed"),
    "deferred_p2": ("deferred-p2", "Deferred P2"),
    "cancelled": ("cancelled", "Cancelled"),
    "watch_list": ("watch-list", "Vintage watch-list"),
    "found_candidate": ("found-candidate", "Vintage candidate"),
}


SHARED_CSS = """
:root {
  --bg: #faf8f4; --ink: #2a2622; --muted: #6b6660; --accent: #8a7a5a;
  --card-bg: #fff; --warm-tint: #f7eedc; --note-tint: #f0e8d8;
  --reject-tint: #f8e6df; --target-tint: #e8efe2; --border: #e8e2d6;
  --status-decide-now: #c94d4d; --status-decided: #5a8a5a;
  --status-awaiting: #c9893a; --status-installed: #6b6660;
  --status-deferred: #8a85a0;
  --approved-overshoot-bg: #eef0f4; --approved-overshoot-border: #9ba8c0;
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
   * scrollbar so users know they can swipe. Applies to .table-wrapper and
   * the topnav scroller; .filter-bar.scrollable opt-in for sourcing. */
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
body { font-family: -apple-system, BlinkMacSystemFont, "Inter", system-ui, sans-serif;
       background: var(--bg); color: var(--ink); line-height: 1.55; -webkit-font-smoothing: antialiased; }
nav.topnav { position: sticky; top: 0; z-index: 50; background: rgba(250, 248, 244, 0.96);
  border-bottom: 1px solid var(--border); backdrop-filter: blur(8px); }
/* R2-C1: scroller wraps the inner so absolute dropdowns positioned vs. <nav>
 * (or position:fixed on mobile) escape the horizontal-scroll overflow clip. */
.topnav-scroller { max-width: 1200px; margin: 0 auto; }
.topnav-inner { padding: 11px 28px; display: flex;
  gap: 4px; flex-wrap: wrap; align-items: center; font-size: 13px; }
.topnav-inner .home { color: #6b6660; margin-right: 14px; font-weight: 600; text-decoration: none; }
.topnav-inner .home:hover { color: var(--accent); }
.topnav-inner .group-label { color: #6b6660; font-size: 11px; text-transform: uppercase;
  letter-spacing: 0.5px; margin: 0 4px 0 12px; font-weight: 600; }
.topnav-inner a:not(.home) { color: var(--ink); text-decoration: none; padding: 4px 10px;
  border-radius: 999px; border: 1px solid var(--border); }
.topnav-inner a:not(.home):hover { background: var(--card-bg); border-color: var(--accent); }
.topnav-inner a.current { background: var(--warm-tint); border-color: #c9b88a; }
/* Topnav dropdowns: Rooms ▾ + Canon ▾ — CSS-only, accessible via keyboard + hover. */
.topnav-inner details.nav-dropdown { position: relative; display: inline-block;
  margin: 0; }
.topnav-inner details.nav-dropdown > summary { list-style: none; cursor: pointer;
  color: var(--ink); padding: 4px 10px; border-radius: 999px;
  border: 1px solid var(--border); font-size: 13px; user-select: none;
  display: inline-flex; align-items: center; gap: 4px; }
.topnav-inner details.nav-dropdown > summary::-webkit-details-marker { display: none; }
.topnav-inner details.nav-dropdown > summary::after { content: "\\25BE"; font-size: 9px;
  color: var(--muted); margin-left: 2px; }
.topnav-inner details.nav-dropdown > summary:hover { background: var(--card-bg);
  border-color: var(--accent); }
.topnav-inner details.nav-dropdown[open] > summary { background: var(--warm-tint);
  border-color: #c9b88a; }
.topnav-inner details.nav-dropdown .nav-dropdown-menu { position: absolute; top: 100%;
  left: 0; margin-top: 4px; background: var(--card-bg); border: 1px solid var(--border);
  border-radius: 8px; padding: 6px; box-shadow: 0 4px 16px rgba(42, 38, 34, 0.08);
  min-width: 180px; z-index: 60; display: none; flex-direction: column; gap: 2px; }
.topnav-inner details.nav-dropdown[open] > .nav-dropdown-menu { display: flex; }
.topnav-inner details.nav-dropdown .nav-dropdown-menu a { border: none; padding: 6px 10px;
  border-radius: 5px; font-size: 13px; }
.topnav-inner details.nav-dropdown .nav-dropdown-menu a:hover { background: var(--warm-tint);
  border: none; }
.topnav-inner details.nav-dropdown .nav-dropdown-menu a.current { background: var(--warm-tint); }
/* Hover-reveal alongside click-reveal for mouse users (does not trap focus). */
@media (hover: hover) {
  .topnav-inner details.nav-dropdown:hover > .nav-dropdown-menu { display: flex; }
  .topnav-inner details.nav-dropdown:not([open]):hover > summary { background: var(--card-bg);
    border-color: var(--accent); }
}
.page-header { max-width: 1200px; margin: 36px auto 20px; padding: 0 28px; }
.page-header h1 { font-size: 30px; margin: 0 0 6px; font-weight: 600; letter-spacing: -0.5px; }
.page-header .subtitle { color: var(--muted); font-size: 15px; max-width: 760px; }
main { max-width: 1200px; margin: 0 auto; padding: 0 28px 80px; }
.lint-alert { background: #fff4d6; border: 1px solid #e9c97f; border-radius: 8px;
  padding: 12px 16px; margin: 16px 0; }
.lint-alert.lint-error { background: #fde8e6; border-color: #d99080; }
.lint-alert.lint-warning { background: #fef3e2; border-color: #d4943a; }
.lint-alert h4 { margin: 0 0 6px; font-size: 13px; text-transform: uppercase; letter-spacing: 0.6px; }
.lint-alert ul { margin: 0; padding-left: 18px; font-size: 13px; }
.approved-overshoots-block { background: var(--approved-overshoot-bg); border: 1px solid var(--approved-overshoot-border);
  border-radius: 8px; padding: 12px 16px; margin: 16px 0; color: #3a4060; }
.approved-overshoots-block h4 { margin: 0 0 6px; font-size: 13px; text-transform: uppercase;
  letter-spacing: 0.6px; color: #4a5280; }
.approved-overshoots-block ul { margin: 0; padding-left: 18px; font-size: 13px; }
.schedule-not-locked { font-size: 11px; padding: 2px 8px; border-radius: 4px; background: #fef0d6;
  border: 1px solid #e9c97f; color: #6e4f1a; }
.schedule-banner { background: #fef3e2; border: 1px solid #d4943a; border-radius: 8px;
  padding: 10px 16px; margin: 0 0 16px; font-size: 13px; color: #5c3a10; }
.revision-history { margin-top: 12px; padding-top: 8px; border-top: 1px dashed var(--border);
  font-size: 11.5px; color: var(--muted); }
.revision-history strong { color: var(--ink); margin-right: 6px; }
.filter-bar { display: flex; gap: 6px; flex-wrap: wrap; padding: 14px 0; border-bottom: 1px solid var(--border); margin-bottom: 24px; position: sticky; top: var(--topnav-h); background: var(--bg); z-index: 40; }
.filter-bar button, .filter-bar select { background: var(--card-bg); border: 1px solid var(--border);
  border-radius: 999px; padding: 5px 12px; font-size: 13px; cursor: pointer; color: var(--ink); }
.filter-bar button.active { background: var(--warm-tint); border-color: #c9b88a; }
.item-card { background: var(--card-bg); border: 1px solid var(--border); border-radius: 12px;
  padding: 18px 20px; margin-bottom: 14px; }
.item-card.hidden { display: none; }
.item-card-header { display: flex; gap: 12px; align-items: baseline; flex-wrap: wrap; margin-bottom: 8px; }
.item-card-header .item-id { font-family: ui-monospace, Menlo, monospace; font-size: 12px; color: var(--muted); }
.item-card-header h3 { margin: 0; font-size: 18px; font-weight: 600; flex: 1; }
.status-badge { font-size: 11px; padding: 3px 10px; border-radius: 999px; text-transform: uppercase;
  letter-spacing: 0.5px; font-weight: 600; }
.status-badge.decide-now { background: var(--status-decide-now); color: white; }
.status-badge.decided { background: var(--status-decided); color: white; }
.status-badge.awaiting-sample, .status-badge.sample-in-hand { background: var(--status-awaiting); color: white; }
.status-badge.installed, .status-badge.ordered, .status-badge.received { background: var(--status-installed); color: white; }
.status-badge.deferred-p2, .status-badge.cancelled, .status-badge.watch-list, .status-badge.found-candidate { background: var(--status-deferred); color: white; }
.item-meta { color: var(--muted); font-size: 13px; margin-bottom: 10px; }
.item-meta strong { color: var(--ink); }
.decided-line { padding: 8px 12px; background: #e8efe2; border-radius: 6px; margin: 8px 0;
  font-weight: 500; color: #3a5a3a; }
.options-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; margin-top: 10px; }
.option-card { border: 1px solid var(--border); border-radius: 8px; padding: 10px; background: #fdfbf7; }
.option-card.recommend { border-color: #c9b88a; background: #fefaf0; }
.option-card .vendor { font-size: 11px; color: var(--muted); text-transform: uppercase; }
.option-card .sku { font-weight: 600; margin: 4px 0; }
.option-card .price { color: var(--accent); font-weight: 600; }
.option-card .reasoning { font-size: 12.5px; color: var(--muted); margin-top: 6px; line-height: 1.45; }
.option-card .star { color: #d4a93a; font-size: 14px; }
.option-img-main { width: 100%; max-width: 220px; height: 160px; object-fit: cover;
  border-radius: 6px; border: 1px solid var(--border); background: #f3ede0;
  display: block; margin: 8px 0 6px; }
.option-img-supps { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 6px; }
.option-img-supp { width: 80px; height: 80px; object-fit: cover; border-radius: 5px;
  border: 1px solid var(--border); background: #f3ede0; }
.option-details { font-size: 11.5px; color: var(--muted); margin: 6px 0 8px; padding: 6px 8px; background: var(--note-tint); border-radius: 4px; line-height: 1.4; }
.sku-link { color: var(--ink); text-decoration: none; border-bottom: 1px dotted var(--accent); }
.sku-link:hover { color: var(--accent); }
.vintage-brief { background: #f3eedd; border-radius: 8px; padding: 12px; font-size: 13.5px; }
.vintage-brief strong { display: inline-block; min-width: 80px; }
.notes-line { font-size: 12.5px; color: var(--muted); font-style: italic; margin-top: 8px; }
.img-placeholder { width: 100%; height: 120px; background: var(--note-tint); border-radius: 6px;
  border: 1px dashed var(--border); display: flex; align-items: center; justify-content: center;
  font-size: 12px; color: var(--muted); text-align: center; padding: 8px; margin: 8px 0; }
/* Catalog reconciliation banner — shows on cards whose spec'd SKU does not match
   the current vendor catalog (yellow tint per spec). */
.catalog-gap-banner { background: #fff4d6; border: 1px solid #d4a93a; color: #6b4f10;
  border-radius: 6px; padding: 8px 12px; margin: 8px 0 10px; font-size: 13px; line-height: 1.45; }
.catalog-gap-banner strong { color: #8a5a10; text-transform: uppercase; letter-spacing: 0.4px;
  font-size: 11px; display: inline-block; margin-right: 6px; }
.item-card.catalog-gap { border-color: #d4a93a; box-shadow: 0 0 0 2px #fff4d6 inset; }
.locked-row.catalog-gap { background: #fff8e0; border-left: 3px solid #d4a93a;
  padding-left: 9px; }
.catalog-gap-pill { display: inline-block; background: #fff4d6; color: #8a5a10;
  border: 1px solid #d4a93a; border-radius: 999px; padding: 1px 8px; font-size: 10px;
  font-weight: 700; letter-spacing: 0.4px; margin-left: 6px; vertical-align: middle; }
/* Pinned decisions-needed banner (catalog gaps surfaced atop /sourcing + /for-annika). */
.decisions-needed-banner { background: #fff4d6; border: 2px solid #d4a93a;
  border-radius: 10px; padding: 14px 18px; margin: 0 0 18px;
  box-shadow: 0 2px 8px rgba(212, 169, 58, 0.12); }
.decisions-needed-banner h3 { margin: 0 0 6px; font-size: 15px; font-weight: 700;
  color: #6b4f10; letter-spacing: 0.3px; }
.decisions-needed-banner .summary-line { font-size: 13.5px; color: #5a4310;
  margin: 0 0 10px; line-height: 1.5; }
.decisions-needed-banner ul { margin: 0; padding-left: 0; list-style: none;
  display: flex; flex-wrap: wrap; gap: 8px; }
.decisions-needed-banner li { margin: 0; }
.decisions-needed-banner a { display: inline-block; background: #fff; color: #6b4f10;
  text-decoration: none; border: 1px solid #d4a93a; border-radius: 999px;
  padding: 4px 12px; font-size: 12.5px; font-weight: 600; }
.decisions-needed-banner a:hover { background: #fef3e2; border-color: #b08a20;
  color: #4a3510; }
.decisions-needed-banner .gap-kind { display: inline-block; font-size: 10px;
  text-transform: uppercase; letter-spacing: 0.4px; color: #8a5a10;
  margin-right: 4px; font-weight: 700; }
/* R2-C5: anchor-shim uses --topnav-h so jump-link offsets track the actual
 * sticky topnav height across mobile + desktop. */
.item-card[id]::before { content: ""; display: block; height: var(--topnav-h);
  margin-top: calc(-1 * var(--topnav-h));
  visibility: hidden; pointer-events: none; }
/* Git-history audit-trail line shown under item title. */
.item-last-changed { font-size: 11.5px; color: var(--muted); font-style: italic;
  margin: -4px 0 8px; }
/* Budget rollup block. */
.budget-rollup { background: #fff; border: 1px solid var(--border); border-radius: 10px;
  padding: 14px 18px; margin: 0 0 18px; }
.budget-rollup h3 { margin: 0 0 8px; font-size: 14px; font-weight: 700;
  text-transform: uppercase; letter-spacing: 0.6px; color: var(--accent); }
.budget-rollup .totals-row { display: flex; gap: 22px; flex-wrap: wrap;
  margin: 0 0 10px; font-size: 14px; align-items: baseline; }
.budget-rollup .totals-row strong { color: var(--ink); font-size: 16px; }
.budget-rollup .delta-positive { color: #3a6a3a; font-weight: 600; }
.budget-rollup .delta-negative { color: #a63a3a; font-weight: 600; }
.budget-rollup table { width: 100%; border-collapse: collapse; font-size: 12.5px;
  margin-top: 8px; }
.budget-rollup th, .budget-rollup td { padding: 4px 8px; text-align: left;
  border-bottom: 1px dashed #efe7d4; }
.budget-rollup th { color: var(--muted); font-weight: 600; text-transform: uppercase;
  letter-spacing: 0.4px; font-size: 10.5px; }
.budget-rollup td.num { text-align: right; font-variant-numeric: tabular-nums;
  font-family: ui-monospace, Menlo, monospace; }
.budget-rollup tr:last-child td { border-bottom: none; }

@media (max-width: 720px) {
  body { font-size: 16px; }
  .page-header h1 { font-size: 24px; }
  /* R2-C1: scroll the WRAPPER, not topnav-inner. Absolutely-positioned dropdown
   * menus inside topnav-inner now escape the overflow scope and become
   * position:fixed (anchored below the topnav) so they don't get clipped. */
  .topnav-scroller { overflow-x: auto; -webkit-overflow-scrolling: touch;
    scrollbar-width: none; }
  .topnav-scroller::-webkit-scrollbar { display: none; }
  .topnav-inner { padding: 6px 12px; font-size: 13px; gap: 6px;
    flex-wrap: nowrap; }
  .topnav-inner > * { flex: 0 0 auto; }
  .topnav-inner .home { margin-right: 8px; }
  .topnav-inner a:not(.home),
  .topnav-inner details.nav-dropdown > summary {
    padding: 8px 12px; font-size: 13px; min-height: 44px;
    display: inline-flex; align-items: center; }
  .topnav-inner .group-label { font-size: 10px; margin: 0 2px 0 8px; }
  /* R2-C1: dropdown menus pop out of the horizontal-scroll container by
   * using fixed positioning anchored below the sticky topnav. */
  .topnav-inner details.nav-dropdown[open] > .nav-dropdown-menu {
    position: fixed; top: calc(var(--topnav-h) + 4px); left: 12px; right: 12px;
    margin-top: 0; min-width: 0; max-height: calc(100vh - var(--topnav-h) - 24px);
    overflow-y: auto; }
  .filter-bar { top: auto; position: static; flex-wrap: wrap; padding: 10px 0; }
  /* R2-T1: filter-bar controls meet WCAG 2.5.5 44px floor. */
  .filter-bar button, .filter-bar select, .filter-bar input {
    font-size: 13px; padding: 8px 14px;
    min-height: 44px; box-sizing: border-box; }
  /* R2-T2/T3 + R3-UX2: pills/chips/tags (incl. .collection-chip on /suppliers)
   * + decisions-needed banner links meet 44px floor. */
  .tag, .chip, .pill, .collection-chip { min-height: 44px;
    display: inline-flex; align-items: center; padding: 8px 14px;
    box-sizing: border-box; }
  .decisions-needed-banner a { min-height: 44px;
    display: inline-flex; align-items: center; padding: 8px 14px;
    box-sizing: border-box; }
  /* R2-T4: in-cell anchors get vertical hit area inside tables on mobile. */
  td a { display: inline-flex; align-items: center; min-height: 44px;
    box-sizing: border-box; padding: 8px 0; }
  .options-grid { grid-template-columns: 1fr; }
  .option-img-main { max-width: 100%; height: auto; max-height: 220px; }
  .item-card { padding: 12px; }
  main { padding: 0 14px 60px; }
  .page-header { padding: 0 14px; }
  /* R1 baseline: tables overflow-scroll on mobile (overridden by .table-wrapper
   * for pages that opt into a desktop-friendly wrapper instead). */
  table { display: block; overflow-x: auto; -webkit-overflow-scrolling: touch;
    max-width: 100%; white-space: nowrap; }
  table.mobile-stack { display: table; white-space: normal; overflow-x: visible; }
  /* R2-C2: wrapped tables render naturally; the WRAPPER handles overflow.
   * Without this rule, .table-wrapper child tables would still be display:block
   * + nowrap, forcing horizontal scroll even when content could wrap. */
  .table-wrapper > table { display: table; white-space: normal;
    overflow-x: visible; max-width: none; }
  /* Long URLs / code blocks must wrap so they can't break the page layout. */
  pre, code { word-break: break-word; white-space: pre-wrap; }
}
@media (max-width: 480px) {
  body { font-size: 16px; line-height: 1.5; }
  h1 { font-size: 1.75rem; }
  h2 { font-size: 1.4rem; }
  h3 { font-size: 1.15rem; }
}
"""


# R9 declutter: CSS only injected into /sourcing (not per-room pages, to keep per-room
# HTML line counts unchanged ±5%). Covers the 2-up grid for drafted items and the
# collapsed <details> "locked decisions" block.
SOURCING_MAIN_CSS = """
.sourcing-grid-2up { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.sourcing-grid-2up .item-card { margin-bottom: 0; }
/* R2-UX2: admin-section collapse on mobile.
 * Desktop default (>720px): the wrapper is transparent (display: contents),
 * the summary is hidden, and the inner banners render inline as before.
 * Mobile (≤720px): the wrapper becomes a tap-target <details>. Default
 * closed; tapping reveals schedule/decisions/budget/overshoot/lint banners.
 * Cuts ~5 screens of admin off the /sourcing first-paint on phone. */
.admin-section-summary { display: none; }
.admin-section { display: contents; }
@media (max-width: 720px) {
  .admin-section { display: block; margin: 0 0 16px; }
  .admin-section[open] { background: transparent; }
  .admin-section-summary {
    display: flex; justify-content: space-between; align-items: center;
    background: var(--warm-tint); border: 1px solid #c9b88a;
    border-radius: 999px; padding: 10px 16px; font-size: 13px;
    font-weight: 600; cursor: pointer; user-select: none;
    list-style: none; min-height: 44px; box-sizing: border-box;
    color: #5a4a20; }
  .admin-section-summary::-webkit-details-marker { display: none; }
  .admin-section-summary::marker { display: none; }
  .admin-section-summary::after { content: "\\25BE"; font-size: 11px;
    color: #5a4a20; transition: transform .15s; }
  .admin-section[open] > .admin-section-summary::after { transform: rotate(180deg); }
  .admin-section-inner { padding-top: 12px; }
}
.locked-decisions-banner { background: var(--warm-tint); border: 1px solid #c9b88a;
  border-radius: 10px; padding: 0; margin: 16px 0 22px; overflow: hidden; }
.locked-decisions-banner > summary { padding: 12px 16px; cursor: pointer;
  font-size: 14px; font-weight: 600; color: #5a4a20; list-style: none; user-select: none;
  display: flex; align-items: center; gap: 10px; }
.locked-decisions-banner > summary::-webkit-details-marker { display: none; }
.locked-decisions-banner > summary::before { content: "\\25B6"; font-size: 10px; color: var(--accent); }
.locked-decisions-banner[open] > summary::before { content: "\\25BC"; }
.locked-decisions-banner > summary .locked-count { color: var(--accent); font-weight: 700; }
.locked-decisions-banner > summary .locked-hint { color: var(--muted); font-weight: 400;
  font-size: 12.5px; margin-left: auto; }
.locked-decisions-inner { padding: 4px 16px 14px; border-top: 1px dashed #d8c89a;
  background: #fdf8ec; }
.locked-row { display: grid; grid-template-columns: 180px 1fr auto; gap: 14px;
  align-items: baseline; padding: 6px 0; border-bottom: 1px dashed #efe2c2;
  font-size: 13px; }
.locked-row:last-child { border-bottom: none; }
.locked-row.hidden { display: none; }
.locked-row-id { font-family: ui-monospace, Menlo, monospace; font-size: 11.5px;
  color: var(--muted); }
.locked-row-title { font-weight: 600; color: var(--ink); }
.locked-row-sku { color: #3a5a3a; font-size: 12.5px; }
.locked-row-meta { color: var(--muted); font-size: 11.5px; white-space: nowrap; }
@media (max-width: 720px) {
  .sourcing-grid-2up { grid-template-columns: 1fr; gap: 12px; }
  .locked-decisions-banner > summary .locked-hint { display: none; }
  .locked-row { grid-template-columns: 1fr; gap: 2px; padding: 8px 0; }
  /* R2-UX4: /sourcing filter bar wraps in <details class="mobile-filters">.
   * Default closed on mobile; summary is the always-visible tap-target.
   * Desktop default (below the @media block): summary hidden,
   * wrapper transparent — bar renders inline as before. */
  details.mobile-filters { display: block; margin: 0 0 14px; }
  details.mobile-filters > summary.mobile-filters-summary {
    display: flex; justify-content: space-between; align-items: center;
    background: var(--card-bg); border: 1px solid var(--border);
    border-radius: 999px; padding: 8px 14px; font-size: 13px;
    font-weight: 600; cursor: pointer; user-select: none;
    list-style: none; min-height: 44px; box-sizing: border-box; }
  details.mobile-filters > summary.mobile-filters-summary::-webkit-details-marker { display: none; }
  details.mobile-filters > summary.mobile-filters-summary::marker { display: none; }
  details.mobile-filters > summary.mobile-filters-summary .mobile-filters-chevron {
    transition: transform .15s; }
  details.mobile-filters[open] > summary.mobile-filters-summary .mobile-filters-chevron {
    transform: rotate(180deg); }
  details.mobile-filters:not([open]) > .filter-bar { display: none; }
  details.mobile-filters[open] > .filter-bar { display: flex;
    border-top: 1px solid var(--border); margin-top: 8px; padding-top: 12px; }
}
/* R2-UX4: desktop default — wrapper transparent so the filter bar lays out
 * exactly as it did pre-wrap. Summary hidden; <details>'s default open/closed
 * has no visual effect because the bar is shown unconditionally above 720px. */
details.mobile-filters { display: contents; }
details.mobile-filters > summary.mobile-filters-summary { display: none; }
"""


def _build_topnav_html(current: str = "sourcing") -> str:
    """Render the shared topnav with Rooms ▾ + Canon ▾ collapsed into <details> dropdowns.
    `current` is one of: home, mood, spectrum, decisions, budget, sourcing, suppliers,
    vendors, annika, spec, kitchen, master, baths, lr, nursery, office, cathie-hong,
    owiu, sss, jenni-kayne, materials, rejected. Marks the matching link with class="current".
    """
    def cls(name: str) -> str:
        return ' class="current"' if name == current else ""

    rooms_open = current in {"kitchen", "master", "baths", "lr", "nursery", "office"}
    canon_open = current in {"cathie-hong", "owiu", "sss", "jenni-kayne"}
    rooms_attr = " open" if rooms_open else ""
    canon_attr = " open" if canon_open else ""

    return f"""<nav class="topnav">
  <div class="topnav-scroller">
    <div class="topnav-inner">
      <a href="/" class="home">&larr; 1490 Lively Ridge</a>
      <a href="/"{cls('home')}>Home</a><a href="/mood-board"{cls('mood')}>Mood</a><a href="/spectrum"{cls('spectrum')}>Spectrum</a><a href="/decisions"{cls('decisions')}>Decisions</a><a href="/budget"{cls('budget')}>Budget</a><a href="/sourcing"{cls('sourcing')}>Sourcing</a><a href="/suppliers"{cls('suppliers')}>Suppliers</a><a href="/vendors"{cls('vendors')}>Vendors</a><a href="/for-annika"{cls('annika')}>Annika</a><a href="/spec"{cls('spec')}>Spec</a>
      <details class="nav-dropdown"{rooms_attr} aria-label="Rooms"><summary>Rooms</summary><div class="nav-dropdown-menu" role="menu"><a href="/kitchen"{cls('kitchen')}>Kitchen</a><a href="/master"{cls('master')}>Master</a><a href="/baths"{cls('baths')}>Baths</a><a href="/lr"{cls('lr')}>LR</a><a href="/nursery"{cls('nursery')}>Nursery</a><a href="/office"{cls('office')}>Office</a></div></details>
      <details class="nav-dropdown"{canon_attr} aria-label="Canon designers"><summary>Canon</summary><div class="nav-dropdown-menu" role="menu"><a href="/cathie-hong"{cls('cathie-hong')}>Cathie Hong</a><a href="/owiu"{cls('owiu')}>OWIU</a><a href="/sss"{cls('sss')}>SSS</a><a href="/jenni-kayne"{cls('jenni-kayne')}>Jenni Kayne</a></div></details>
      <a href="/materials"{cls('materials')}>Materials</a><a href="/rejected"{cls('rejected')}>Rejected</a>
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
</script>"""


TOPNAV_HTML = _build_topnav_html("sourcing")


def _render_option(opt) -> str:
    star = '<span class="star">★</span> ' if opt.recommend else ""
    # Main image
    img_html = ""
    if opt.image and (SITE_DIR / opt.image).exists():
        img_html = f'<img class="option-img-main" src="/{opt.image}" alt="{escape(opt.sku)}" loading="lazy" onerror="this.style.opacity=0.3;">'
    # Supplementary images (-b, -c) — only use item-level fallback for recommended option
    supp_paths = _supplementary_paths(opt.image, recommend=opt.recommend)
    supp_html = ""
    if supp_paths:
        thumbs = "".join(
            f'<img class="option-img-supp" src="/{p}" alt="{escape(opt.sku)} detail" loading="lazy" onerror="this.style.opacity=0.3;">'
            for p in supp_paths
        )
        supp_html = f'<div class="option-img-supps">{thumbs}</div>'
    # Details block (new)
    details_html = f'<div class="option-details">{escape(opt.details)}</div>' if opt.details else ""
    # Product URL link (new)
    sku_html = (
        f'<a href="{escape(opt.product_url)}" target="_blank" rel="noopener" class="sku-link">{star}{escape(opt.sku)} →</a>'
        if opt.product_url
        else f'{star}{escape(opt.sku)}'
    )
    return f"""<div class="option-card {'recommend' if opt.recommend else ''}">
      <div class="vendor">{escape(opt.vendor)}</div>
      <div class="sku">{sku_html}</div>
      <div class="price">${opt.price_usd:,.0f}</div>
      {img_html}
      {supp_html}
      {details_html}
      <div class="reasoning">{escape(opt.reasoning)}</div>
    </div>"""


def _schedule_locked_for_item(item: Item, lookup: Optional[ScheduleLookup]) -> bool:
    """T3 doesn't depend on a phase date. For T0/T1/T2, check the relevant phase(s)."""
    if lookup is None or item.urgency == "T3":
        return True
    if item.urgency == "T0":
        return all(lookup.days_until(p)[1] for p in T0_PHASES)
    if item.urgency == "T1":
        return lookup.days_until("finish_phase_start")[1]
    if item.urgency == "T2":
        return lookup.days_until("move_back_in")[1]
    return True


def _render_revision_history(item: Item) -> str:
    if not item.revision_history:
        return ""
    last_three = item.revision_history[-3:]
    entries = []
    for entry in last_three:
        # entry is a dict like {"2026-05-16": "stub created"}
        for d, msg in entry.items():
            entries.append(f'<span><strong>{escape(str(d))}:</strong> {escape(str(msg))}</span>')
    return '<div class="revision-history">' + " · ".join(entries) + '</div>'


def _render_item_card(item: Item, schedule_lookup: Optional[ScheduleLookup] = None,
                      suppress_sched_badge: bool = False,
                      last_changed: Optional[str] = None,
                      vendor_matches: Optional[List[str]] = None) -> str:
    badge_class, badge_text = STATUS_BADGE.get(item.decision_status, ("", item.decision_status))
    annika_flag = ' · 👩 Annika' if item.annika_loop else ''
    sample_flag = ' · ⚠️ sample required' if item.sample_required else ''
    sched_locked = _schedule_locked_for_item(item, schedule_lookup)
    # Per-card badge only shown when banner mode is off (< 50% unlocked)
    sched_badge = '' if (sched_locked or suppress_sched_badge) else '<span class="schedule-not-locked">⚠️ schedule not locked</span>'
    body = ""

    if item.decided_sku:
        body = f'<div class="decided-line">✅ {escape(item.decided_sku)}</div>'
        # Top-level image takes precedence for canon-decided items without options.
        if item.image and (SITE_DIR / item.image.lstrip("/")).exists():
            body += (
                f'<img class="option-img-main item-img-main" '
                f'src="/{item.image.lstrip("/")}" alt="{escape(item.title)}" '
                f'loading="lazy" onerror="this.style.opacity=0.3;">'
            )
        else:
            # Show placeholder if no option images exist for decided items
            has_img = any(
                (SITE_DIR / o.image).exists()
                for o in (item.options or [])
                if o.image
            )
            if not has_img and not item.options:
                body += f'<div class="img-placeholder">{escape(item.title)}<br><small>locked · no image on file</small></div>'
    elif item.vintage_brief:
        v = item.vintage_brief
        body = f'''<div class="vintage-brief">
          <div><strong>Style:</strong> {escape(v.style)}</div>
          <div><strong>Avoid:</strong> {escape(v.not_)}</div>
          <div><strong>Target $:</strong> {escape(v.target_price_usd)}</div>
          <div><strong>Hunt at:</strong> {escape(', '.join(v.hunt_venues))}</div>
        </div>'''
        # Top-level image (representative) for vintage_brief items.
        if item.image and (SITE_DIR / item.image.lstrip("/")).exists():
            body += (
                f'<img class="option-img-main item-img-main" '
                f'src="/{item.image.lstrip("/")}" alt="{escape(item.title)} (representative)" '
                f'loading="lazy" onerror="this.style.opacity=0.3;">'
            )
        # Placeholder if watch_list item has no image at all
        elif not item.options:
            body += f'<div class="img-placeholder">{escape(item.title)}<br><small>vintage hunt · no image yet</small></div>'
    elif item.options:
        body = '<div class="options-grid">' + "".join(_render_option(o) for o in item.options) + '</div>'

    notes_html = f'<div class="notes-line">{escape(item.notes)}</div>' if item.notes else ""

    history_html = _render_revision_history(item)

    # Catalog reconciliation banner (yellow tint) for items whose spec'd SKU does
    # not match the live vendor catalog. Surfaces above the body so owners see
    # the gap before reading the decided-SKU line.
    catalog_gap_html = ""
    extra_card_class = ""
    catalog_gap_pill = ""
    if item.catalog_status == "needs_reselection":
        extra_card_class = " catalog-gap"
        catalog_gap_pill = '<span class="catalog-gap-pill" title="vendor catalog moved — see notes">⚠ CATALOG GAP</span>'
        catalog_gap_html = (
            f'<div class="catalog-gap-banner">'
            f'<strong>⚠ CATALOG GAP — see notes</strong>'
            f'Spec\'d SKU is no longer in the current vendor catalog with no clean successor; owner reselect required.'
            + (f' <em>{escape(item.catalog_status_note)}</em>' if item.catalog_status_note else "")
            + '</div>'
        )
    elif item.catalog_status == "spec_error":
        extra_card_class = " catalog-gap"
        catalog_gap_pill = '<span class="catalog-gap-pill" title="spec does not exist at this vendor">⚠ SPEC ERROR</span>'
        catalog_gap_html = (
            f'<div class="catalog-gap-banner">'
            f'<strong>⚠ CATALOG GAP — see notes</strong>'
            f'Spec\'d product does not exist in this vendor\'s catalog (wrong line/format). Owner reselect required.'
            + (f' <em>{escape(item.catalog_status_note)}</em>' if item.catalog_status_note else "")
            + '</div>'
        )
    elif item.catalog_status == "verified":
        catalog_gap_pill = '<span class="catalog-gap-pill" style="background:#e8efe2;color:#3a5a3a;border-color:#a4c08a;" title="spec confirmed against live vendor PDP">✓ CATALOG VERIFIED</span>'

    last_changed_html = (
        f'<div class="item-last-changed">Last changed {escape(last_changed)}</div>'
        if last_changed else ""
    )

    # R2 Fix C5 — emit data-vendor-matches so /sourcing can filter to items
    # whose vendor strings match a supplier-id from the supplier_directory.
    vendor_attr = ""
    if vendor_matches:
        vendor_attr = f' data-vendor-matches="{escape(" ".join(vendor_matches))}"'

    return f"""<article class="item-card{extra_card_class}" id="item-{escape(item.id)}" data-id="{escape(item.id)}"
       data-urgency="{escape(item.urgency)}" data-room="{escape(item.room)}"
       data-category="{escape(item.category)}" data-status="{escape(item.decision_status)}"
       data-annika="{str(item.annika_loop).lower()}"
       data-catalog-status="{escape(item.catalog_status or '')}"
       data-schedule-locked="{str(sched_locked).lower()}"{vendor_attr}>
      <div class="item-card-header">
        <span class="item-id">{escape(item.id)}</span>
        <h3>{escape(item.title)}{catalog_gap_pill}</h3>
        <span class="status-badge {badge_class}">{badge_text}</span>
        {sched_badge}
      </div>
      <div class="item-meta">
        <strong>Room:</strong> {escape(item.room)} ·
        <strong>Category:</strong> {escape(item.category)} ·
        <strong>Urgency:</strong> {escape(item.urgency)} ·
        <strong>Lead:</strong> {item.lead_time_weeks} wk ·
        <strong>Budget:</strong> ${item.budget_target_usd:,.0f} ({escape(item.budget_source)}) ·
        <strong>Actor:</strong> {escape(item.sourcing_actor)}{annika_flag}{sample_flag}
      </div>
      {last_changed_html}
      {catalog_gap_html}
      {body}
      {notes_html}
      {history_html}
    </article>"""


# R7-I1: keyword-based overshoot detection.
# Per HARD RULE "revisions UP only", budget always covers the ★ rec — so the legacy
# rec.price > budget condition never fired, leaving the visible 6 items unrendered.
# Instead, look for explicit overshoot-acknowledgement keywords in the item's notes
# OR the ★ option's reasoning prose.  These keywords indicate the owner has consciously
# accepted a price-over-baseline outcome and wants it tracked publicly.
_APPROVED_OVERSHOOT_KEYWORDS = (
    "approved overshoot",
    "approved_overshoot",
    "approved-overshoot",
    "owner confirm",
    "audit ratified",
    "ratified overshoot",
)


def _approved_overshoots_block(items: List[Item]) -> str:
    """Show items the owner has flagged as approved overshoots in a distinct slate block so
    they remain publicly visible.

    Trigger (R7-I1): the keyword presence in the item's notes OR the ★ option's reasoning
    field (case-insensitive). Examples that match: "approved_overshoot: true", "approved-
    overshoot per Annika", "OWNER CONFIRM", "audit ratified", "ratified overshoot".

    For each match, display: item id — recommended-option price vs prior budget target,
    and the percent gap (which may be 0% or negative now that the budget has been revised
    UP to match — the publication value is in showing the audit trail, not enforcing math).
    """
    overshoots = []
    for item in items:
        haystack = (item.notes or "").lower()
        # Also scan the ★ option's reasoning prose for the keyword
        rec = None
        if item.options:
            rec = next((o for o in item.options if o.recommend), None)
            if rec:
                haystack += " " + (rec.reasoning or "").lower()
                haystack += " " + (rec.details or "").lower()
        if not any(kw in haystack for kw in _APPROVED_OVERSHOOT_KEYWORDS):
            continue
        # Require a ★ option so price-vs-target can be displayed.  Items with no priced
        # option (decided_sku only) can't show this comparison, so skip.
        if not rec:
            continue
        # Percent gap may be 0 or negative now that revisions-UP brought budget into line —
        # still display so the audit trail stays visible.
        target = item.budget_target_usd or 0
        if target > 0:
            pct = (rec.price_usd / target - 1) * 100
        else:
            pct = 0.0
        overshoots.append((item.id, rec.price_usd, target, pct))
    if not overshoots:
        return ""
    rows = "".join(
        f"<li>{escape(i)} &mdash; ${p:,.0f} vs target ${b:,.0f} ({pct:+.0f}%)</li>"
        for i, p, b, pct in overshoots
    )
    return (
        f'<div class="approved-overshoots-block">'
        f'<h4>Approved overshoots ({len(overshoots)})</h4>'
        f'<ul>{rows}</ul>'
        f'</div>'
    )


# ---------------------------------------------------------------------------
# D1: Pinned decisions-needed banner — surfaces items whose vendor catalog
# disagrees with spec (catalog_status in {needs_reselection, spec_error}).
# Sits atop /sourcing main page (and on /for-annika with tailored copy).
# Renders nothing when N=0.
# ---------------------------------------------------------------------------

_CATALOG_FLAGGED = {"needs_reselection", "spec_error"}


def _flagged_items(items: List[Item]) -> List[Item]:
    return [it for it in items if it.catalog_status in _CATALOG_FLAGGED]


def _decisions_needed_banner(items: List[Item], variant: str = "default") -> str:
    """Render a pinned banner listing items with catalog_status in {needs_reselection,
    spec_error}. Each item is a clickable jump-link to its in-page card anchor.

    variant="default" — generic copy for /sourcing.
    variant="annika"  — copy tuned for /for-annika ("need your design eye").

    Returns "" when no items are flagged.
    """
    flagged = _flagged_items(items)
    if not flagged:
        return ""
    n = len(flagged)
    if variant == "annika":
        heading = f"&#9888; {n} picks need your design eye before reorder"
        summary = (
            "Vendor catalog moved or original spec doesn&rsquo;t exist anymore. "
            "I&rsquo;ve flagged these so you can weigh in on the replacement direction."
        )
    else:
        heading = f"&#9888; {n} decision{'s' if n != 1 else ''} need your reselection"
        summary = (
            "Vendor catalog disagrees with spec on the items below. "
            "Each needs an owner reselect before re-order. Tap any item to jump to its card."
        )
    items_html = []
    for it in flagged:
        kind = "CATALOG GAP" if it.catalog_status == "needs_reselection" else "SPEC ERROR"
        items_html.append(
            f'<li><a href="#item-{escape(it.id)}">'
            f'<span class="gap-kind">{kind}</span>'
            f'{escape(it.id)} &middot; {escape(it.title)}'
            f'</a></li>'
        )
    return (
        f'<div class="decisions-needed-banner" role="region" aria-label="Decisions needed">'
        f'<h3>{heading}</h3>'
        f'<p class="summary-line">{summary}</p>'
        f'<ul>{"".join(items_html)}</ul>'
        f'</div>'
    )


# ---------------------------------------------------------------------------
# D2: Budget × sourcing rollup — compact summary showing total budgeted across
# all items vs the $342K cap, plus a per-category breakdown.
# ---------------------------------------------------------------------------

# Category display labels and ordering (matches the VALID_CATEGORIES schema enum).
_CATEGORY_LABELS = [
    ("plumbing_fixture", "Plumbing"),
    ("lighting_fixture", "Lighting"),
    ("hardware", "Hardware"),
    ("tile_stone", "Tile / stone"),
    ("cabinetry_millwork", "Cabinetry"),
    ("appliance", "Appliance"),
    ("paint_finish", "Paint / finish"),
    ("window_treatment", "Window"),
    ("furniture", "Furniture"),
    ("decor_softgoods", "Decor"),
]


def _budget_rollup_block(items: List[Item], meta: Meta) -> str:
    """Compact summary block showing total $ budgeted across all visible items vs the
    construction cap (read from meta.budgets.construction_cap, currently $342,000),
    plus per-category breakdown. Skips items with null/0 budget_target_usd."""
    cap = meta.budgets.construction_cap
    total = sum((it.budget_target_usd or 0) for it in items)
    delta = cap - total
    delta_cls = "delta-positive" if delta >= 0 else "delta-negative"
    delta_sign = "+" if delta >= 0 else "-"

    # Per-category breakdown
    rows_html = []
    for cat_key, cat_label in _CATEGORY_LABELS:
        cat_items = [it for it in items if it.category == cat_key]
        if not cat_items:
            continue
        cat_count = len(cat_items)
        cat_sum = sum((it.budget_target_usd or 0) for it in cat_items)
        pct_of_cap = (cat_sum / cap * 100) if cap else 0
        rows_html.append(
            f'<tr><td>{escape(cat_label)}</td>'
            f'<td class="num">{cat_count}</td>'
            f'<td class="num">${cat_sum:,.0f}</td>'
            f'<td class="num">{pct_of_cap:.1f}%</td></tr>'
        )

    return (
        f'<div class="budget-rollup">'
        f'<h3>Budget rollup</h3>'
        f'<div class="totals-row">'
        f'<span>Total budgeted: <strong>${total:,.0f}</strong></span>'
        f'<span>Construction cap: <strong>${cap:,.0f}</strong></span>'
        f'<span class="{delta_cls}">Delta vs cap: {delta_sign}${abs(delta):,.0f}</span>'
        f'</div>'
        f'<div class="table-wrapper">'
        f'<table>'
        f'<thead><tr><th>Category</th><th class="num">Count</th>'
        f'<th class="num">Budgeted</th><th class="num">% of cap</th></tr></thead>'
        f'<tbody>{"".join(rows_html)}</tbody>'
        f'</table>'
        f'</div>'
        f'</div>'
    )


def _render_lint_alerts(findings: List[LintFinding]) -> str:
    if not findings:
        return ""
    errors = [f for f in findings if f.severity == "error"]
    warnings = [f for f in findings if f.severity == "warning"]
    infos = [f for f in findings if f.severity == "info"]
    parts = []
    if errors:
        parts.append('<div class="lint-alert lint-error"><h4>Lint errors ({})</h4><ul>{}</ul></div>'.format(
            len(errors), "".join(f'<li>{escape(f.message)}</li>' for f in errors)))
    if warnings:
        parts.append('<div class="lint-alert lint-warning"><h4>Lint warnings ({})</h4><ul>{}</ul></div>'.format(
            len(warnings), "".join(f'<li>{escape(f.message)}</li>' for f in warnings)))
    if infos:
        parts.append('<div class="lint-alert"><h4>Lint info ({})</h4><ul>{}</ul></div>'.format(
            len(infos), "".join(f'<li>{escape(f.message)}</li>' for f in infos)))
    return "\n".join(parts)


def _render_filter_bar() -> str:
    rooms = ["kitchen", "master_br", "master_bath", "hall_bath", "basement_bath",
             "lr", "dining", "office", "nursery", "mudroom_carport", "basement",
             "exterior", "common"]
    categories = ["plumbing_fixture", "lighting_fixture", "hardware", "tile_stone",
                  "cabinetry_millwork", "appliance", "paint_finish", "window_treatment",
                  "furniture", "decor_softgoods"]
    statuses = ["options_drafted", "awaiting_sample", "sample_in_hand", "decided",
                "ordered", "received", "installed", "deferred_p2", "cancelled",
                "watch_list", "found_candidate"]
    # R2-UX4: filter bar is wrapped in <details class="mobile-filters"> so it
    # collapses behind a tap-target on phone, freeing ~180px of vertical real
    # estate. Desktop CSS makes the wrapper transparent (display: contents) so
    # the bar renders inline as before.
    return f"""<details class="mobile-filters">
      <summary class="mobile-filters-summary">
        <span>Filters</span>
        <span class="mobile-filters-chevron">&#9662;</span>
      </summary>
      <div class="filter-bar">
        <button data-filter="all" class="active">All</button>
        <button data-filter="decide-now" title="All items with options drafted — schedule not yet locked so &#39;this week&#39; is heuristic">Currently drafted</button>
        <button data-filter="annika">Annika queue</button>
        <select id="room-filter"><option value="">By room</option>{
          "".join(f'<option value="{r}">{r}</option>' for r in rooms)
        }</select>
        <select id="category-filter"><option value="">By category</option>{
          "".join(f'<option value="{c}">{c}</option>' for c in categories)
        }</select>
        <select id="status-filter"><option value="">By status</option>{
          "".join(f'<option value="{s}">{s}</option>' for s in statuses)
        }</select>
      </div>
    </details>"""


FILTER_JS = """
<script>
(function() {
  // R9 declutter: also pick up compact .locked-row rows inside the collapsed details
  // block so room/category/status filters still work when the user expands it.
  const cards = Array.from(document.querySelectorAll('.item-card, .locked-row'));
  const buttons = Array.from(document.querySelectorAll('.filter-bar button'));
  const roomSel = document.getElementById('room-filter');
  const catSel = document.getElementById('category-filter');
  const statSel = document.getElementById('status-filter');
  let activeFilter = 'all';

  function apply() {
    const room = roomSel.value;
    const cat = catSel.value;
    const stat = statSel.value;
    cards.forEach(c => {
      let show = true;
      if (activeFilter === 'decide-now') show = c.dataset.status === 'options_drafted';
      else if (activeFilter === 'annika') show = c.dataset.annika === 'true';
      if (show && room) show = c.dataset.room === room;
      if (show && cat) show = c.dataset.category === cat;
      if (show && stat) show = c.dataset.status === stat;
      c.classList.toggle('hidden', !show);
    });
  }

  buttons.forEach(b => b.addEventListener('click', () => {
    activeFilter = b.dataset.filter;
    buttons.forEach(x => x.classList.toggle('active', x === b));
    apply();
  }));
  [roomSel, catSel, statSel].forEach(s => s.addEventListener('change', apply));

  // ?filter=annika URL state
  const params = new URLSearchParams(window.location.search);
  const f = params.get('filter');
  if (f === 'annika') {
    activeFilter = 'annika';
    buttons.forEach(x => x.classList.toggle('active', x.dataset.filter === 'annika'));
    apply();
  }

  // R2 Fix C5 — ?vendor=<supplier-id> filter. Filters visible cards to those
  // whose data-vendor-matches attribute contains the requested supplier-id.
  // Used by /suppliers cross-link ("Tracked in /sourcing: N items").
  const vendor = params.get('vendor');
  if (vendor) {
    let kept = 0;
    cards.forEach(c => {
      const m = (c.dataset.vendorMatches || '').split(' ').filter(Boolean);
      const keep = m.indexOf(vendor) >= 0;
      if (!keep) c.classList.add('hidden');
      else kept++;
    });
    // Insert a 1-line vendor banner at the top of <main> so the user knows
    // they're looking at a filtered view, with a clear-filter affordance.
    // R3 Fix C1 — build banner via DOM nodes / textContent, never innerHTML
    // with a query-param. Reflected-XSS via ?vendor=<script>... is neutralized.
    const mainEl = document.querySelector('main');
    if (mainEl) {
      const banner = document.createElement('div');
      banner.className = 'vendor-filter-banner';
      banner.style.cssText = 'background:var(--warm-tint);border:1px solid #c9b88a;border-radius:8px;padding:10px 14px;margin:0 0 14px;font-size:13px;display:flex;justify-content:space-between;align-items:center;gap:10px;';
      const msg = document.createElement('span');
      msg.appendChild(document.createTextNode('Filtered to vendor '));
      const strong = document.createElement('strong');
      strong.textContent = vendor;
      msg.appendChild(strong);
      msg.appendChild(document.createTextNode(
        ' — ' + kept + ' item' + (kept !== 1 ? 's' : '') + '.'
      ));
      const clear = document.createElement('a');
      clear.href = window.location.pathname;
      clear.style.cssText = 'color:var(--accent);font-weight:600;';
      clear.textContent = 'Show all ×';
      banner.appendChild(msg);
      banner.appendChild(clear);
      mainEl.insertBefore(banner, mainEl.firstChild);
    }
  }
})();
</script>
"""


ROOM_LINKS_HTML = """<div style="max-width:1200px;margin:8px auto 0;padding:0 28px;font-size:13px;color:var(--muted);">
  <strong style="color:var(--ink);">Per-room views:</strong>
  <a href="/sourcing-kitchen">Kitchen</a> ·
  <a href="/sourcing-master">Master Suite</a> ·
  <a href="/sourcing-baths">Baths</a> ·
  <a href="/sourcing-lr">Living + Dining</a> ·
  <a href="/sourcing-nursery">Nursery</a> ·
  <a href="/sourcing-office">Office</a>
</div>"""


def _schedule_banner_mode(items: List[Item], schedule_lookup: Optional[ScheduleLookup]) -> bool:
    """Return True (banner mode) when >50% of non-T3 visible items have unlocked schedules."""
    if schedule_lookup is None:
        return False
    urgency_sensitive = [it for it in items if it.urgency != "T3" and it.decision_status != "stub"]
    if not urgency_sensitive:
        return False
    unlocked_count = sum(
        1 for it in urgency_sensitive if not _schedule_locked_for_item(it, schedule_lookup)
    )
    return unlocked_count > len(urgency_sensitive) * 0.5


def _is_locked_decision(item: Item) -> bool:
    """R9 declutter: an item is 'locked' (canon-decided) when there is no options array
    OR the decision_status is 'decided' (covers canon-locks set in DESIGN_SPEC).

    Vintage watch_list / found_candidate items have a vintage_brief instead of options —
    those are NOT locked decisions; they remain inline in the drafted grid so the hunt
    stays visible. Stub items are filtered upstream by visibility, not here.
    """
    if item.decision_status == "decided":
        return True
    # No options AND no vintage_brief => canon-locked text card (paint/finish-only spec items).
    if item.options is None and item.vintage_brief is None:
        return True
    return False


def _render_locked_row(item: Item, last_changed: Optional[str] = None,
                        vendor_matches: Optional[List[str]] = None) -> str:
    """R9 declutter: compact one-line representation of a canon-decided item used inside the
    collapsed <details> block on /sourcing. Carries the data-* attributes the filter JS
    expects so room/category/status filters still work when the block is expanded.

    Shows: id · title · decided_sku (or 'see card') · room · category. The full item card
    is still available on the per-room page for in-room decision context.

    R3 Fix C5 — locked rows also emit data-vendor-matches so the /sourcing
    `?vendor=` filter (Fix C5 in R2 Beta) does not silently hide canon-decided
    items that match the requested vendor.
    """
    decided_sku = item.decided_sku or "see per-room page for detail"
    # Yellow tint + pill on rows whose vendor catalog disagrees with spec.
    row_extra = " catalog-gap" if item.catalog_status in ("needs_reselection", "spec_error") else ""
    gap_pill = ""
    if item.catalog_status == "needs_reselection":
        gap_pill = '<span class="catalog-gap-pill">⚠ CATALOG GAP</span>'
    elif item.catalog_status == "spec_error":
        gap_pill = '<span class="catalog-gap-pill">⚠ SPEC ERROR</span>'
    changed_meta = f" · changed {escape(last_changed)}" if last_changed else ""
    vendor_attr = ""
    if vendor_matches:
        vendor_attr = f' data-vendor-matches="{escape(" ".join(vendor_matches))}"'
    return (
        f'<div class="locked-row{row_extra}" id="item-{escape(item.id)}" data-id="{escape(item.id)}" '
        f'data-urgency="{escape(item.urgency)}" data-room="{escape(item.room)}" '
        f'data-category="{escape(item.category)}" data-status="{escape(item.decision_status)}" '
        f'data-annika="{str(item.annika_loop).lower()}" '
        f'data-catalog-status="{escape(item.catalog_status or "")}" '
        f'data-schedule-locked="true"{vendor_attr}>'
        f'<span class="locked-row-id">{escape(item.id)}</span>'
        f'<span class="locked-row-title">{escape(item.title)}{gap_pill}</span>'
        f'<span class="locked-row-sku">{escape(decided_sku)}</span>'
        f'<span class="locked-row-meta">{escape(item.room)} · {escape(item.category)}{changed_meta}</span>'
        f'</div>'
    )


# Sourcing category → supplier-directory category-suffix map (R2 Fix C6).
# Used to scope vendor-matching to compatible category buckets so e.g.
# `west-elm-bedroom` only matches sourcing items in the furniture/bedroom space
# (not seating). Each sourcing.yaml `category` lists which supplier suffixes
# may match. An empty list / missing key means "no category-scoping" (the
# match is brand-wide, e.g. paint where the supplier-id has no category suffix).
_SOURCING_CAT_TO_SUPPLIER_SUFFIXES = {
    "furniture": ["-seating", "-tables", "-bedroom", "-bedding"],
    "lighting_fixture": ["-lighting"],
    "appliance": ["-appliances"],
    "hardware": ["-hardware"],
    "window_treatment": ["-window"],
    "tile_stone": ["-tile", "-counters", "-stone"],
    "paint_finish": ["-paint", "-finish"],
    "plumbing_fixture": ["-plumbing"],
    "cabinetry_millwork": ["-cabinetry", "-millwork"],
    "decor_softgoods": ["-decor", "-rugs", "-bedding", "-art"],
}


def _vendor_matches_for_item(item, suppliers_by_id_and_brand) -> List[str]:
    """R4 Fix C1 — Compute which supplier-ids this sourcing item matches,
    scoped by the SAME predicate that `_supplier_sourcing_links()` uses to
    drive `/suppliers` counts. Returns list of supplier-ids.

    suppliers_by_id_and_brand is a list of (supplier_id, supplier_name,
    supplier_category_string) tuples loaded from supplier_directory.yaml.

    Previously this function used a parent-category allow-list of suffixes,
    which meant every WE subcategory (-seating / -tables / -bedroom) tagged
    EVERY furniture item the same way. As a result `/sourcing?vendor=west-elm-bedroom`
    returned 22 furniture rows, even though the supplier card on
    `/suppliers` correctly reported only 5 bedroom items. R4 closes the
    integrity split by reusing `_item_in_supplier_category_scope()` so
    the data attribute matches the displayed count exactly.
    """
    if not suppliers_by_id_and_brand:
        return []
    # Build the candidate vendor strings off this item.
    vendor_strs = []
    if getattr(item, "vendor", None):
        vendor_strs.append(item.vendor)
    for o in (item.options or []):
        if o.vendor:
            vendor_strs.append(o.vendor)
    if not vendor_strs:
        return []

    # R4 Fix C1 — adapt the Item dataclass into the dict shape that
    # `_item_in_supplier_category_scope()` reads (it expects "title",
    # "category", "room" keys). Built once per item.
    item_dict = {
        "title": getattr(item, "title", "") or "",
        "category": getattr(item, "category", "") or "",
        "room": getattr(item, "room", "") or "",
    }

    matches = []
    seen = set()
    for sid, sname, scat in suppliers_by_id_and_brand:
        # Brand-match against any vendor string on the item.
        brand_matched = False
        for vstr in vendor_strs:
            if _vendor_string_matches_supplier(vstr, sid, sname):
                brand_matched = True
                break
        if not brand_matched:
            continue
        # R4 Fix C1 — apply the same supplier-category scope used by
        # `_supplier_sourcing_links()`. When the supplier has no recognized
        # supplier-category (or the map has no rule for it), the predicate
        # falls through to True (brand-only match), matching the legacy
        # behavior for non-furniture brand-wide suppliers.
        if scat and not _item_in_supplier_category_scope(item_dict, scat):
            continue
        if sid not in seen:
            matches.append(sid)
            seen.add(sid)
    return matches


def _load_suppliers_brand_index() -> List[tuple]:
    """Return list of (supplier_id, supplier_name, supplier_category) tuples
    for vendor-matching from /sourcing pages. Returns [] when yaml missing or
    unreadable — vendor-matching is a *progressive enhancement* of the
    /sourcing pages, so a broken supplier yaml degrades gracefully rather
    than crashing the build of unrelated pages.
    """
    try:
        directory = _load_supplier_directory()
    except Exception:
        return []
    if not directory:
        return []
    return [
        (s.get("id", ""), s.get("name", ""), s.get("category", ""))
        for s in (directory.get("suppliers") or [])
    ]


def render_site_page(items: List[Item], meta: Meta, lint_findings: List[LintFinding],
                     schedule_lookup: Optional[ScheduleLookup] = None,
                     last_changed_map: Optional[Dict[str, str]] = None) -> str:
    visible = [it for it in items if it.decision_status != "stub"]
    lint_html = _render_lint_alerts(lint_findings)
    overshoot_html = _approved_overshoots_block(visible)
    decisions_banner_html = _decisions_needed_banner(visible)
    budget_rollup_html = _budget_rollup_block(visible, meta)
    banner_mode = _schedule_banner_mode(visible, schedule_lookup)
    schedule_banner_html = (
        '<div class="schedule-banner">⚠️ Construction schedule not yet locked — urgency badges deferred until dates are confirmed.</div>'
        if banner_mode else ""
    )

    lc = last_changed_map or {}

    # R9 declutter: split items into drafted (active decisions, render in 2-up grid) and
    # locked (canon-decided, hidden behind a collapsed <details> block). Per-room pages
    # use the separate render_room_page() and are unaffected.
    drafted_items = [it for it in visible if not _is_locked_decision(it)]
    locked_items = [it for it in visible if _is_locked_decision(it)]

    # R2 Fix C5+C6 — load supplier-brand index once and emit per-item vendor matches.
    suppliers_idx = _load_suppliers_brand_index()
    drafted_cards_html = "\n".join(
        _render_item_card(it, schedule_lookup, suppress_sched_badge=banner_mode,
                          last_changed=lc.get(it.id),
                          vendor_matches=_vendor_matches_for_item(it, suppliers_idx))
        for it in drafted_items
    )
    drafted_grid_html = (
        f'<div class="sourcing-grid-2up">\n{drafted_cards_html}\n</div>'
        if drafted_items else ""
    )

    if locked_items:
        # R9: compact one-line rows inside the collapsed details block. Cuts ~20 lines per
        # locked item out of the rendered HTML while preserving filter data-attrs.
        # R3 Fix C5 — also pass vendor_matches so the ?vendor= filter on /sourcing
        # finds canon-decided items, not only options-bearing items.
        locked_rows_html = "\n".join(
            _render_locked_row(
                it, last_changed=lc.get(it.id),
                vendor_matches=_vendor_matches_for_item(it, suppliers_idx),
            )
            for it in locked_items
        )
        locked_block_html = (
            f'<details class="locked-decisions-banner">'
            f'<summary>'
            f'<span class="locked-count">{len(locked_items)} decisions locked</span>'
            f'<span>(paint, hardwood, tile, plumbing, appliances)</span>'
            f'<span class="locked-hint">Tap to show all locked decisions</span>'
            f'</summary>'
            f'<div class="locked-decisions-inner">\n{locked_rows_html}\n</div>'
            f'</details>'
        )
    else:
        locked_block_html = ""

    cards_html = f"{drafted_grid_html}\n{locked_block_html}"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Sourcing · 1490 Lively Ridge</title>
<meta name="description" content="Sourcing tracker for every design-decision item — vendor, SKU, lead time, status. {len(visible)} items.">
<style>{SHARED_CSS}
{SOURCING_MAIN_CSS}</style>
</head>
<body>
{TOPNAV_HTML}
<header class="page-header">
  <h1>Sourcing</h1>
  <p class="subtitle">Every design-decision item the renovation will consume. {len(visible)} items tracked. Updated {escape(meta.last_updated)}.</p>
</header>
{ROOM_LINKS_HTML}
<main>
{decisions_banner_html}
<details class="admin-section">
<summary class="admin-section-summary">Admin &amp; status</summary>
<div class="admin-section-inner">
{schedule_banner_html}
{budget_rollup_html}
{overshoot_html}
{lint_html}
</div>
</details>
{_render_filter_bar()}
{cards_html}
</main>
<div style="max-width:900px;margin:0 auto 48px;padding:0 16px;">
<details style="border:1px solid #e8e2d6;border-radius:10px;overflow:hidden;">
  <summary style="padding:11px 16px;cursor:pointer;font-size:13.5px;font-weight:600;color:#8a7a5a;background:#f0e8d8;list-style:none;user-select:none;">
    &#9654;&nbsp; Design jargon quick-reference (tap to expand)
  </summary>
  <div style="padding:14px 18px;font-size:14px;line-height:1.7;color:#4a4540;">
    <dl style="margin:0;display:grid;grid-template-columns:auto 1fr;gap:4px 12px;">
      <dt style="font-weight:600;white-space:nowrap;">Boucle</dt>
      <dd style="margin:0 0 6px;">Textured loop-pile fabric — soft, casual, slightly nubby.</dd>
      <dt style="font-weight:600;white-space:nowrap;">Crypton</dt>
      <dd style="margin:0 0 6px;">Stain/spill-resistant performance fabric — wipe-clean, pet-safe, washable.</dd>
      <dt style="font-weight:600;white-space:nowrap;">Thermostatic</dt>
      <dd style="margin:0 0 6px;">Shower valve that holds set temperature regardless of pressure fluctuations — no scalding when someone flushes.</dd>
      <dt style="font-weight:600;white-space:nowrap;">GREENGUARD Gold</dt>
      <dd style="margin:0 0 6px;">Low-VOC emissions certification — required for nursery furniture per spec.</dd>
      <dt style="font-weight:600;white-space:nowrap;">CFM</dt>
      <dd style="margin:0 0 6px;">Cubic Feet per Minute — airflow measure for range hoods. Higher = more powerful extraction.</dd>
      <dt style="font-weight:600;white-space:nowrap;">T0 / T1 / T2 / T3</dt>
      <dd style="margin:0 0 6px;">Urgency tier: T0 = order now, T1 = week 4, T2 = week 8, T3 = year 1+.</dd>
    </dl>
  </div>
</details>
</div>
{FILTER_JS}
</body>
</html>
"""


def render_room_page(room_label: str, rooms_filter: List[str], items: List[Item], meta: Meta,
                     schedule_lookup: Optional[ScheduleLookup] = None,
                     design_hub_url: Optional[str] = None,
                     last_changed_map: Optional[Dict[str, str]] = None) -> str:
    """Render a single-room view. rooms_filter is a list of room IDs to include
    (e.g., ['master_br','master_bath'] for master suite).
    design_hub_url: optional URL to the corresponding design hub page (e.g. '/kitchen').

    N2 TRADE-OFF NOTE: The topnav highlights /sourcing (not the current room page) when on
    a room sourcing view (e.g. /sourcing-kitchen). Per-room topnav entries would clutter the
    nav bar significantly. The breadcrumb at the top of this page ("Sourcing › Kitchen") is
    the accepted "you are here" signal. This is an intentional design trade-off, not a bug.
    """
    visible = [it for it in items if it.decision_status != "stub" and it.room in rooms_filter]
    banner_mode = _schedule_banner_mode(visible, schedule_lookup)
    schedule_banner_html = (
        '<div class="schedule-banner">⚠️ Construction schedule not yet locked — urgency badges deferred until dates are confirmed.</div>'
        if banner_mode else ""
    )
    lc = last_changed_map or {}
    # R2 Fix C5+C6 — emit per-item vendor matches for /sourcing?vendor= filter.
    suppliers_idx = _load_suppliers_brand_index()
    cards_html = "\n".join(
        _render_item_card(it, schedule_lookup, suppress_sched_badge=banner_mode,
                          last_changed=lc.get(it.id),
                          vendor_matches=_vendor_matches_for_item(it, suppliers_idx))
        for it in visible
    )

    subtitle = f"{len(visible)} items in {room_label}. Updated {meta.last_updated}."

    # Cross-link to design hub page if available
    crosslink_html = ""
    if design_hub_url:
        crosslink_html = (
            f'<div style="margin-top:8px;padding:8px 12px;background:var(--note-tint);border-radius:6px;'
            f'font-size:13px;color:var(--muted);">'
            f'Design vision, mood, and constraints: <a href="{escape(design_hub_url)}" '
            f'style="color:var(--accent);">{escape(room_label)} design hub →</a>'
            f'</div>'
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Sourcing · {escape(room_label)} · 1490 Lively Ridge</title>
<meta name="description" content="Sourcing for {escape(room_label)} — {len(visible)} items.">
<style>{SHARED_CSS}</style>
</head>
<body>
{TOPNAV_HTML}
<header class="page-header">
  <p style="font-size:13px;color:var(--muted);margin:0 0 4px;">
    <a href="/sourcing" style="color:var(--accent);">Sourcing</a> › {escape(room_label)}
  </p>
  <h1>Sourcing · {escape(room_label)}</h1>
  <p class="subtitle">{escape(subtitle)}</p>
  {crosslink_html}
</header>
<main>
{schedule_banner_html}
{cards_html if visible else '<p style="color:var(--muted);">No items yet for this room.</p>'}
</main>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# for-annika page — auto-generated from sourcing.yaml + external data files
# ---------------------------------------------------------------------------

ANNIKA_CSS = """
.cover { max-width: 760px; margin: 60px auto 30px; padding: 0 28px; }
.cover h1 { font-size: 38px; font-weight: 600; letter-spacing: -0.7px; margin: 0 0 6px; }
.cover .draft-meta { color: var(--muted); font-size: 13px; margin: 0 0 30px; font-style: italic; }
.cover p { font-size: 17px; line-height: 1.7; margin: 0 0 18px; color: #3a3530; }
.cover p.callout { background: var(--warm-tint); border-left: 3px solid #c9b88a;
  padding: 14px 18px; border-radius: 4px; font-size: 15.5px; }
.cover a { color: var(--accent); }
.cta-block { max-width: 760px; margin: 0 auto 40px; padding: 0 28px; }
.cta-inner { background: #fff; border: 2px solid #c9b88a; border-radius: 12px;
  padding: 20px 24px; display: flex; gap: 18px; align-items: center; flex-wrap: wrap; }
.cta-inner .cta-deadline { font-size: 18px; font-weight: 700; color: var(--ink); }
.cta-inner .cta-sub { font-size: 14px; color: var(--muted); line-height: 1.5; }
.toc { max-width: 760px; margin: 18px auto 50px; padding: 18px 28px;
  background: var(--card-bg); border: 1px solid var(--border); border-radius: 12px; }
.toc h3 { margin: 0 0 10px; font-size: 13px; text-transform: uppercase;
  letter-spacing: 0.8px; color: var(--muted); font-weight: 700; }
.toc ul { margin: 0; padding-left: 18px; }
.toc li { margin: 4px 0; font-size: 15px; }
.toc a { color: var(--ink); text-decoration: none; }
.toc a:hover { color: var(--accent); }
.toc .count { color: var(--muted); font-size: 13px; margin-left: 6px; }
.section-divider { max-width: 900px; margin: 60px auto 30px; padding: 0 28px;
  border-top: 1px solid #efe7d4; padding-top: 30px; }
.section-divider h2 { font-size: 26px; font-weight: 600; letter-spacing: -0.4px;
  margin: 0 0 4px; color: var(--ink); }
.section-divider .section-sub { color: var(--muted); font-size: 14px; }
.section-note { max-width: 900px; margin: 0 auto 10px; padding: 0 28px;
  font-size: 14px; color: var(--muted); font-style: italic; }
main.annika-main { max-width: 900px; margin: 0 auto; padding: 0 28px 100px; }
.annika-item { background: var(--card-bg); border: 1px solid var(--border);
  border-radius: 14px; padding: 26px 30px; margin: 22px 0; }
.annika-item-header { display: flex; gap: 14px; align-items: baseline; flex-wrap: wrap;
  margin-bottom: 18px; padding-bottom: 14px; border-bottom: 1px dashed #efe7d4; }
.annika-item-id { font-family: ui-monospace, Menlo, monospace; font-size: 12px;
  color: var(--muted); background: var(--note-tint); padding: 2px 8px; border-radius: 4px; }
.annika-item-title { margin: 0; font-size: 21px; font-weight: 600; flex: 1; letter-spacing: -0.2px; }
.annika-tagline { margin: -10px 0 16px; color: var(--muted); font-size: 14.5px; font-style: italic; }
.annika-status-pill { font-size: 11px; padding: 3px 10px; border-radius: 999px;
  color: white; text-transform: uppercase; letter-spacing: 0.5px; font-weight: 600;
  background: #c94d4d; }
.annika-status-pill.decided { background: #5a8a5a; }
.annika-status-pill.watch-list { background: #8a85a0; }
.annika-item-body { display: grid; grid-template-columns: 260px 1fr; gap: 28px; align-items: start; }
.annika-pick-image { width: 100%; aspect-ratio: 1/1; object-fit: cover;
  border-radius: 10px; border: 1px solid var(--border); background: #f3ede0; }
.annika-pick-image-wrap { text-align: center; }
.annika-pick-image-caption { font-size: 11.5px; color: var(--muted); margin-top: 6px;
  font-family: ui-monospace, Menlo, monospace; }
.annika-brief-block { font-size: 15.5px; line-height: 1.7; }
.annika-label { display: inline-block; font-size: 11px; text-transform: uppercase;
  letter-spacing: 0.7px; color: var(--accent); font-weight: 700; margin-top: 14px;
  margin-bottom: 4px; }
.annika-label:first-child { margin-top: 0; }
.annika-pick { font-size: 15px; color: var(--ink); margin: 4px 0 0; font-weight: 500; }
.annika-question { margin: 10px 0 0; padding: 12px 16px;
  background: var(--warm-tint); border-radius: 8px; color: var(--ink);
  border-left: 3px solid #c9b88a; font-style: italic; }
.annika-decided { padding: 12px 16px; background: #e8efe2;
  border-radius: 8px; color: #3a5a3a; font-weight: 500; }
.annika-locked-note { margin-top: 10px; color: var(--muted); font-size: 14px; font-style: italic; }
.annika-sku-flag { margin-top: 10px; padding: 8px 12px; background: #fef8ec;
  border-left: 3px solid #d4a96b; border-radius: 6px;
  font-size: 13px; color: #7a5a20; }
details.annika-why { margin-top: 12px; border: 1px solid #efe7d4;
  border-radius: 8px; overflow: hidden; }
details.annika-why summary { padding: 9px 14px; cursor: pointer; font-size: 13px;
  font-weight: 600; color: var(--accent); list-style: none; background: var(--note-tint);
  user-select: none; }
details.annika-why summary::-webkit-details-marker { display: none; }
details.annika-why summary::before { content: "\\25B6  "; font-size: 10px; }
details.annika-why[open] summary::before { content: "\\25BC  "; }
details.annika-why .why-inner { padding: 12px 14px; font-size: 14.5px; color: #4a4540;
  line-height: 1.6; }
details.annika-why .why-inner p { margin: 0 0 8px; }
details.annika-why .why-inner p:last-child { margin-bottom: 0; }
.annika-img-placeholder { width: 100%; height: 200px; background: var(--note-tint);
  border-radius: 10px; border: 1px dashed var(--border); display: flex; align-items: center;
  justify-content: center; font-size: 12px; color: var(--muted); text-align: center; padding: 8px; }
.annika-summary-cta { max-width: 760px; margin: 60px auto 80px; padding: 30px;
  background: var(--card-bg); border: 2px solid #c9b88a; border-radius: 14px; }
.annika-summary-cta h2 { margin: 0 0 14px; font-size: 22px; font-weight: 600; }
.annika-summary-cta p { margin: 0 0 12px; font-size: 15.5px; line-height: 1.65; }
.annika-summary-cta .deadline-line { font-size: 18px; font-weight: 700; color: var(--ink);
  margin: 16px 0 8px; }
.annika-summary-cta .format-line { font-size: 14.5px; color: var(--muted); }
.annika-summary-cta a { color: var(--accent); }
/* R4-5: overflow auto so unbreakable glossary terms can scroll horizontally
 * inside the panel rather than getting clipped. Higher specificity selector
 * overrides the inline style="overflow:hidden" on the <details> element. */
details.annika-glossary { overflow: auto; }
@media (max-width: 720px) {
  .annika-item-body { grid-template-columns: 1fr; }
  .cover { margin-top: 30px; padding: 0 16px; }
  .cover h1 { font-size: 26px; }
  .cta-block { padding: 0 16px; }
  main.annika-main { padding: 0 16px 80px; }
  .section-divider { padding: 0 16px; padding-top: 24px; }
  .section-note { padding: 0 16px; }
  /* R4-5: on phones, scope to horizontal scroll only so the vertical content
   * (definitions) can expand naturally. */
  details.annika-glossary { overflow-x: auto; overflow-y: visible; -webkit-overflow-scrolling: touch; }
}
"""

# ANNIKA topnav is identical to main but marks /for-annika as current
ANNIKA_TOPNAV_HTML = _build_topnav_html("annika")

ANNIKA_GLOSSARY_HTML = """<details class="annika-glossary" style="max-width:760px;margin:0 auto 32px;border:1px solid #e8e2d6;border-radius:10px;">
  <summary style="padding:11px 16px;cursor:pointer;font-size:13.5px;font-weight:600;color:#8a7a5a;background:#f0e8d8;list-style:none;user-select:none;">
    &#9654;&nbsp; Design jargon quick-reference (tap to expand)
  </summary>
  <div style="padding:14px 18px;font-size:14px;line-height:1.7;color:#4a4540;">
    <dl style="margin:0;display:grid;grid-template-columns:auto 1fr;gap:4px 12px;">
      <dt style="font-weight:600;white-space:nowrap;">Boucle</dt>
      <dd style="margin:0 0 6px;">Textured loop-pile fabric — soft, casual, slightly nubby. Very current in Californian interiors.</dd>
      <dt style="font-weight:600;white-space:nowrap;">Crypton</dt>
      <dd style="margin:0 0 6px;">Stain/spill-resistant performance fabric — wipe-clean, pet-safe, washable. The practical choice for high-use pieces.</dd>
      <dt style="font-weight:600;white-space:nowrap;">Thermostatic</dt>
      <dd style="margin:0 0 6px;">Shower valve that holds your set temperature regardless of pressure fluctuations (so no scalding when someone flushes). More expensive than pressure-balance but more comfortable.</dd>
      <dt style="font-weight:600;white-space:nowrap;">GREENGUARD Gold</dt>
      <dd style="margin:0 0 6px;">Low-VOC emissions certification for indoor air quality — required for nursery furniture per our spec.</dd>
      <dt style="font-weight:600;white-space:nowrap;">CFM</dt>
      <dd style="margin:0 0 6px;">Cubic Feet per Minute — airflow measure for range hoods. Higher = more powerful extraction.</dd>
      <dt style="font-weight:600;white-space:nowrap;">T0 / T1 / T2 / T3</dt>
      <dd style="margin:0 0 6px;">Urgency tier: T0 = critical-path (order now), T1 = order by week 4, T2 = order by week 8, T3 = year 1+ / no rush.</dd>
    </dl>
  </div>
</details>"""

# Room groupings for the Annika page sections (display-label, [room ids], anchor, locked-note)
ANNIKA_ROOM_SECTIONS = [
    (
        "Master Suite",
        ["master_br", "master_bath"],
        "master-suite",
        "Bedroom + bath",
        "Already locked (no input needed): floor tile, wall tile, vanity, sink faucet, medicine cabinet. (Bath accent paint is in the whole-house paint section below.)",
    ),
    (
        "Nursery",
        ["nursery"],
        "nursery",
        "Nursery",
        None,
    ),
    (
        "Kitchen + dining",
        ["kitchen", "dining"],
        "kitchen-dining",
        "Kitchen + dining",
        "Already locked (no input needed): counters, floor tile, backsplash, cabinets, kitchen faucet, cabinet finish.",
    ),
    (
        "Living room",
        ["lr"],
        "living-room",
        "Living room",
        None,
    ),
    (
        "Office",
        ["office"],
        "office",
        "Office",
        None,
    ),
    (
        "Whole-house paint",
        ["common"],
        "finishes",
        "Both locked — no input needed, just so you've seen them",
        None,
    ),
    (
        "Long-horizon watch list",
        None,  # special: watch_list status across all rooms
        "watch-list",
        "Deferred — no decision needed now, just awareness",
        None,
    ),
]

ANNIKA_ACTIVE_STATUSES = {
    "options_drafted", "awaiting_sample", "sample_in_hand", "decided", "watch_list"
}


def _load_annika_questions(questions_path: Optional[Path]) -> Dict[str, str]:
    """Load per-item question overrides from YAML. Returns {} on any error."""
    if questions_path is None or not questions_path.exists():
        return {}
    try:
        raw = yaml.safe_load(questions_path.read_text())
        return dict(raw.get("questions", {}))
    except Exception:
        return {}


def _load_cover_note(cover_note_path: Optional[Path]) -> str:
    """Load cover note markdown and return as plain text paragraphs. Returns '' on error."""
    import sys
    if cover_note_path is None:
        return ""
    if not cover_note_path.exists():
        print(f"WARNING: cover note file not found at {cover_note_path}", file=sys.stderr)
        return ""
    content = cover_note_path.read_text()
    if not content.strip():
        print(f"WARNING: cover note file is empty at {cover_note_path}", file=sys.stderr)
        return ""
    return content


def _render_annika_cover(cover_md: str, meta: Meta, item_count: int) -> str:
    """Render the cover block + CTA from the markdown file."""
    # Parse version/date/deadline from frontmatter if present
    version = "v3"
    date_str = meta.last_updated
    deadline = "May 23"
    lines = cover_md.splitlines()
    in_fm = False
    body_lines = []
    for line in lines:
        if line.strip() == "---":
            in_fm = not in_fm
            continue
        if in_fm:
            if line.startswith("version:"):
                version = line.split(":", 1)[1].strip()
            elif line.startswith("date:"):
                date_str = line.split(":", 1)[1].strip()
            elif line.startswith("deadline:"):
                deadline = line.split(":", 1)[1].strip()
        else:
            body_lines.append(line)

    # Convert first h1 heading to title, bold/italic left as plain text
    title = "Annika, your design review pass"
    body_paragraphs = []
    for line in body_lines:
        stripped = line.strip()
        if stripped.startswith("# "):
            title = stripped[2:]
        elif stripped.startswith("---"):
            continue
        elif stripped:
            # Preserve **bold** as <strong> and *italic* as <em> inline
            p = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", stripped)
            p = re.sub(r"\*(.+?)\*", r"<em>\1</em>", p)
            body_paragraphs.append(p)

    # First paragraph with callout styling if it contains "What I'm asking"
    paragraphs_html = ""
    for para in body_paragraphs:
        if "What I'm asking" in para or "Please react" in para or "Once you send" in para or "SKU verification" in para:
            paragraphs_html += f'<p class="callout">{para}</p>\n  '
        else:
            paragraphs_html += f'<p>{para}</p>\n  '

    deadline_display = f"Please react by {deadline}" if not deadline.startswith("Please") else deadline

    return f"""<div class="cover">
  <h1>{escape(title)}</h1>
  <p class="draft-meta">{escape(date_str)} &middot; Omid + Claude &middot; {escape(version)}</p>
  {paragraphs_html}
</div>

<div class="cta-block">
  <div class="cta-inner">
    <div>
      <div class="cta-deadline">{escape(deadline_display)}</div>
      <div class="cta-sub">Text or voicemail as you scroll &mdash; that&rsquo;s all I need.<br>That&rsquo;s when I lock the long-lead orders.</div>
    </div>
  </div>
</div>"""


def _pick_image_for_item(item: "Item") -> Optional[str]:
    """Return the image path for the recommended option, or first option image, or None."""
    if not item.options:
        return None
    for opt in item.options:
        if opt.recommend and opt.image and (SITE_DIR / opt.image).exists():
            return opt.image
    for opt in item.options:
        if opt.image and (SITE_DIR / opt.image).exists():
            return opt.image
    # Return the first image path regardless (may be a placeholder)
    for opt in item.options:
        if opt.image:
            return opt.image
    return None


def _pick_option_for_item(item: "Item") -> Optional["Option"]:
    """Return the recommended option, or first option."""
    if not item.options:
        return None
    for opt in item.options:
        if opt.recommend:
            return opt
    return item.options[0] if item.options else None


def _alts_text_for_item(item: "Item") -> str:
    """Build vs-alternates text from non-recommended options."""
    if not item.options:
        return ""
    alts = [o for o in item.options if not o.recommend]
    if not alts:
        return ""
    parts = []
    for a in alts[:3]:
        parts.append(f"{escape(a.vendor)} {escape(a.sku)} (${a.price_usd:,.0f})")
    return "vs " + "; ".join(parts)


def _render_annika_item(item: "Item", questions: Dict[str, str]) -> str:
    """Render a single item card in the Annika page style."""
    # Status pill
    if item.decision_status == "decided":
        pill_class = "decided"
        pill_text = "Locked"
    elif item.decision_status == "watch_list":
        pill_class = "watch-list"
        pill_text = "Watch list"
    else:
        pill_class = ""
        pill_text = "Your read"

    # Image
    img_path = _pick_image_for_item(item)
    pick_opt = _pick_option_for_item(item)

    if img_path and (SITE_DIR / img_path).exists():
        img_caption = escape(pick_opt.sku) if pick_opt else escape(item.title)
        img_html = f"""<div class="annika-pick-image-wrap">
          <img class="annika-pick-image" src="/{img_path}" alt="{img_caption}" loading="lazy" onerror="this.style.opacity=0.3;">
          <div class="annika-pick-image-caption">{img_caption}</div>
        </div>"""
    elif img_path:
        # Referenced but not on disk — show placeholder
        img_html = f'<div class="annika-pick-image-wrap"><div class="annika-img-placeholder">{escape(item.title)}<br><small>image pending</small></div></div>'
    else:
        img_html = f'<div class="annika-pick-image-wrap"><div class="annika-img-placeholder">{escape(item.title)}<br><small>no image on file</small></div></div>'

    # Tagline from notes or a synthesized one-liner
    tagline = item.notes if item.notes else ""

    # Body: decided vs options vs vintage
    if item.decision_status == "decided" and item.decided_sku:
        body_html = f"""<div class="annika-brief-block">
          <div class="annika-label">Locked</div>
          <p class="annika-decided">{escape(item.decided_sku)}</p>
          <p class="annika-locked-note">No input needed &mdash; just FYI on the direction.</p>
        </div>"""
        img_html = ""  # decided items: skip image column, full-width text
        grid_style = ' style="grid-template-columns: 1fr;"'
    elif item.vintage_brief:
        v = item.vintage_brief
        q = questions.get(item.id, "Does this approach feel right for this space?")
        body_html = f"""<div class="annika-brief-block" style="grid-column: 1 / -1;">
          <div class="annika-label">Hunting for</div>
          <p class="annika-pick">{escape(v.style)}</p>
          <div class="annika-label">Budget</div>
          <p class="annika-pick">{escape(v.target_price_usd)}</p>
          <div class="annika-label">Question for you</div>
          <p class="annika-question">{escape(q)}</p>
        </div>"""
        img_html = ""
        grid_style = ' style="grid-template-columns: 1fr;"'
    elif pick_opt:
        q = questions.get(item.id, "Does this feel right?")
        # Build why/alts detail block
        alts_html = ""
        alt_opts = [o for o in (item.options or []) if not o.recommend]
        if alt_opts:
            alt_parts = []
            for a in alt_opts[:3]:
                # Avoid double-vendor: if SKU already starts with the vendor name, skip vendor prefix
                vendor_str = escape(a.vendor)
                sku_str = escape(a.sku)
                # Compare normalised (lowercase, strip punctuation) to catch "West Elm" + "West Elm Andes..."
                _vendor_norm = (a.vendor or "").strip().lower()
                _sku_norm = (a.sku or "").strip().lower()
                if _sku_norm.startswith(_vendor_norm):
                    label = sku_str
                else:
                    label = f"{vendor_str} {sku_str}"
                alt_parts.append(f"<strong>vs</strong> {label} (${a.price_usd:,.0f}) &mdash; {escape(a.reasoning[:120])}")
            alts_html = "".join(f"<p>{p}</p>" for p in alt_parts)

        why_html = ""
        if pick_opt.reasoning or alts_html:
            reasoning_html = f"<p>{escape(pick_opt.reasoning)}</p>" if pick_opt.reasoning else ""
            why_html = f"""<details class="annika-why">
            <summary>Why this pick / vs alternates</summary>
            <div class="why-inner">
              {reasoning_html}
              {alts_html}
            </div>
          </details>"""

        # SKU flag if sample_required or has sku-verify note
        sku_flag_html = ""
        # R7-I2: Detect wrong-product-class language ONLY in the SKU field itself (not in
        # reasoning/details prose).  Past-tense corrective prose like "the original SKU
        # does not exist; we substituted X" describes what was rejected and replaced — the
        # current SKU is the correct pick, so red escalation against past-tense prose
        # generated 5/5 false positives in R6.  By restricting the signal scope to
        # pick_opt.sku, only literal contradictions baked into the SKU string itself fire.
        _wrong_class_signals = ["not a pot filler", "wrong product", "not a ", "doesn't exist",
                                 "does not exist", "not found", "bar/prep faucet", "wrong product class"]
        _sku_text_lower = (pick_opt.sku or "").lower()
        _has_wrong_class = any(sig in _sku_text_lower for sig in _wrong_class_signals)
        if item.sample_required:
            sku_flag_html = '<div class="annika-sku-flag">&#9733; Sample required before ordering.</div>'
        elif _has_wrong_class:
            sku_flag_html = (
                '<div class="annika-sku-flag" style="border-left-color:#c94d4d;background:#fde8e6;color:#7a2020;">'
                '&#9888; Wrong product class flagged &mdash; verify exact model before order.</div>'
            )
        elif pick_opt.details and ("SKU verify" in pick_opt.details or "verify" in pick_opt.details.lower()):
            sku_flag_html = '<div class="annika-sku-flag">&#9733; SKU verification in progress &mdash; concept stands, exact model being confirmed.</div>'

        # URL link for SKU
        sku_display = escape(pick_opt.sku)
        if pick_opt.product_url:
            sku_display = f'<a href="{escape(pick_opt.product_url)}" target="_blank" rel="noopener" style="color:var(--ink);text-decoration:none;border-bottom:1px dotted var(--accent);">{sku_display} &rarr;</a>'

        body_html = f"""<div class="annika-brief-block">
          <div class="annika-label">Pick</div>
          <p class="annika-pick">{sku_display} &mdash; ${pick_opt.price_usd:,.0f}</p>
          <div class="annika-label">Question for you</div>
          <p class="annika-question">{escape(q)}</p>
          {why_html}
          {sku_flag_html}
        </div>"""
        grid_style = ""
    else:
        # No options — stub or incomplete
        body_html = '<div class="annika-brief-block"><p style="color:var(--muted);">Details pending.</p></div>'
        grid_style = ""

    tagline_html = f'<p class="annika-tagline">{escape(tagline)}</p>' if tagline else ""

    # For decided items, collapse image column
    if item.decision_status == "decided" and item.decided_sku:
        body_content = body_html
        grid_start = f'<div class="annika-item-body"{grid_style}>'
    else:
        body_content = img_html + "\n" + body_html
        grid_start = f'<div class="annika-item-body"{grid_style}>'

    return f"""<article class="annika-item">
      <div class="annika-item-header">
        <span class="annika-item-id">{escape(item.id)}</span>
        <h3 class="annika-item-title">{escape(item.title)}</h3>
        <span class="annika-status-pill {pill_class}">{pill_text}</span>
      </div>
      {tagline_html}
      {grid_start}
        {body_content}
      </div>
    </article>"""


def _build_toc(sections_with_counts: list) -> str:
    """Build table of contents from (label, anchor, count_text) tuples."""
    items_html = ""
    for label, anchor, count_text in sections_with_counts:
        items_html += f'<li><a href="#{anchor}">{escape(label)}</a><span class="count">&mdash; {escape(count_text)}</span></li>\n    '
    return f"""<div class="toc">
  <h3>Sections</h3>
  <ul>
    {items_html}
  </ul>
</div>"""


def render_for_annika(
    items: List[Item],
    meta: Meta,
    cover_note_path: Optional[Path] = None,
    questions_path: Optional[Path] = None,
) -> str:
    """Generate /for-annika page. Filters to annika_loop items in actionable statuses.

    Reads cover note from cover_note_path (markdown with optional YAML frontmatter).
    Reads per-item questions from questions_path (YAML: questions: {ITEM-ID: "text"}).
    Both files are optional — sensible fallbacks apply if absent.
    """
    questions = _load_annika_questions(questions_path)
    cover_md = _load_cover_note(cover_note_path)

    # Filter to annika-loop items in actionable statuses
    annika_items = [
        it for it in items
        if it.annika_loop and it.decision_status in ANNIKA_ACTIVE_STATUSES
    ]

    cover_html = _render_annika_cover(cover_md, meta, len(annika_items))

    # D5: surface catalog gaps prominently on /for-annika — same banner as /sourcing
    # but with copy tailored to Annika's review ("need your design eye").
    # Banner scopes to ALL flagged items (not just annika_loop) so she sees the full
    # reselection picture during a single review pass.
    decisions_banner_html = _decisions_needed_banner(items, variant="annika")
    decisions_banner_wrapped = (
        f'<div style="max-width:900px;margin:0 auto 32px;padding:0 28px;">{decisions_banner_html}</div>'
        if decisions_banner_html else ""
    )

    # Build per-section content
    sections_html = ""
    toc_entries = []

    for section_label, room_ids, anchor, section_sub, section_locked_note in ANNIKA_ROOM_SECTIONS:
        if room_ids is None:
            # Watch list: filter by watch_list status across all rooms
            section_items = [it for it in annika_items if it.decision_status == "watch_list"]
        else:
            section_items = [it for it in annika_items if it.room in room_ids]

        if not section_items:
            continue

        decided_count = sum(1 for it in section_items if it.decision_status == "decided")
        active_count = len(section_items) - decided_count
        if decided_count > 0:
            count_text = f"{len(section_items)} items ({decided_count} already locked, {active_count} need your read)"
        else:
            count_text = f"{len(section_items)} items"

        toc_entries.append((section_label, anchor, count_text))

        locked_note_html = ""
        if section_locked_note:
            locked_note_html = f'<p class="section-note">{escape(section_locked_note)}</p>'

        cards_html = "\n".join(_render_annika_item(it, questions) for it in section_items)

        sections_html += f"""
<div class="section-divider"><a id="{anchor}"></a>
  <h2>{escape(section_label)}</h2>
  <div class="section-sub">{escape(section_sub)}</div>
</div>
{locked_note_html}
<main class="annika-main">
{cards_html}
</main>
"""

    toc_html = _build_toc(toc_entries)

    # Summary CTA at bottom
    summary_cta_html = f"""<div class="annika-summary-cta" style="margin: 60px auto 80px;">
  <h2>What happens next</h2>
  <p>Once you send reactions, I&rsquo;ll lock the long-lead orders &mdash; the items that need 4&ndash;8 weeks to arrive before the contractor is ready for them. You don&rsquo;t need to have an opinion on every item. &ldquo;Looks fine&rdquo; is a complete answer.</p>
  <p>A few items are marked <strong>&#9733; SKU verification in progress</strong> &mdash; I&rsquo;m confirming those products are in stock and current before ordering. The concept for each stands; just the exact model is being confirmed.</p>
  <div class="deadline-line">Please react by Friday May 23.</div>
  <div class="format-line">Text as you scroll, or a short voicemail. No need to reference item IDs unless you want to be precise.</div>
  <p style="margin-top: 16px;"><a href="https://1490-design-site.vercel.app/for-annika">https://1490-design-site.vercel.app/for-annika</a> &mdash; forward this link to view later.</p>
</div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>For Annika &middot; Design review &middot; 1490 Lively Ridge</title>
<meta name="description" content="Design review for Annika &mdash; {len(annika_items)} items across master suite, nursery, kitchen, and more. Reactions needed.">
<style>{SHARED_CSS}
{ANNIKA_CSS}</style>
</head>
<body>
{ANNIKA_TOPNAV_HTML}
{cover_html}
{decisions_banner_wrapped}
{toc_html}
{ANNIKA_GLOSSARY_HTML}
{sections_html}
{summary_cta_html}
</body>
</html>
"""


# ---------------------------------------------------------------------------
# D6: /vendors page — items grouped by vendor for batch ordering + sample
# requests, plus a canon-mix coherence check against DESIGN_SPEC §5d targets.
# ---------------------------------------------------------------------------

VENDORS_TOPNAV_HTML = _build_topnav_html("vendors")

VENDORS_CSS = """
.vendors-page main { max-width: 1080px; }
.vendor-mix-summary { background: #fff; border: 1px solid var(--border);
  border-radius: 10px; padding: 14px 18px; margin: 0 0 24px; }
.vendor-mix-summary h3 { margin: 0 0 6px; font-size: 14px; font-weight: 700;
  text-transform: uppercase; letter-spacing: 0.6px; color: var(--accent); }
.vendor-mix-summary p.lead { margin: 0 0 10px; font-size: 13px; color: var(--muted); }
.vendor-mix-summary table { width: 100%; border-collapse: collapse; font-size: 13px; }
.vendor-mix-summary th, .vendor-mix-summary td { padding: 6px 10px; text-align: left;
  border-bottom: 1px dashed #efe7d4; }
.vendor-mix-summary th { color: var(--muted); font-weight: 600; text-transform: uppercase;
  letter-spacing: 0.4px; font-size: 11px; }
.vendor-mix-summary td.num { text-align: right; font-variant-numeric: tabular-nums;
  font-family: ui-monospace, Menlo, monospace; }
.vendor-mix-summary .within { color: #3a6a3a; font-weight: 600; }
.vendor-mix-summary .out { color: #a63a3a; font-weight: 600; }
.vendor-section { background: var(--card-bg); border: 1px solid var(--border);
  border-radius: 12px; padding: 16px 20px; margin: 0 0 14px; }
.vendor-section-header { display: flex; flex-wrap: wrap; align-items: baseline;
  gap: 14px; margin: 0 0 12px; padding-bottom: 8px; border-bottom: 1px dashed #efe7d4; }
/* R4-6: text-wrap: balance keeps long vendor names from breaking awkwardly
 * at narrow widths. Modern browsers honor; older ignore gracefully. */
.vendor-section-header h2 { margin: 0; font-size: 18px; font-weight: 600;
  flex: 1; letter-spacing: -0.2px; text-wrap: balance; }
.vendor-section-header .meta { font-size: 12px; color: var(--muted); }
.vendor-section-header .meta strong { color: var(--ink); }
.vendor-section table { width: 100%; border-collapse: collapse; font-size: 13px; }
.vendor-section td { padding: 6px 8px; border-bottom: 1px dashed #efe7d4;
  vertical-align: top; }
.vendor-section tr:last-child td { border-bottom: none; }
.vendor-section td.num { text-align: right; font-variant-numeric: tabular-nums;
  font-family: ui-monospace, Menlo, monospace; white-space: nowrap; }
.vendor-section td.id-col { font-family: ui-monospace, Menlo, monospace; font-size: 11.5px;
  color: var(--muted); white-space: nowrap; }
.vendor-section td.title-col { font-weight: 500; }
.vendor-section td.sku-col { color: var(--muted); font-size: 12px; word-break: break-word; }
.vendor-section td.status-col { white-space: nowrap; }
.vendor-section .status-badge-mini { display: inline-block; font-size: 10px;
  padding: 2px 7px; border-radius: 999px; text-transform: uppercase;
  letter-spacing: 0.4px; font-weight: 700; }
.vendor-section .status-decided { background: #e8efe2; color: #3a5a3a; }
.vendor-section .status-drafted { background: #fef0d6; color: #6e4f1a; }
.vendor-section .status-watch { background: #ece8f4; color: #4a4566; }
.vendor-section .status-other { background: #efe7d4; color: var(--muted); }
/* R2-UX3 + R2-T5: vendors page on mobile — relax white-space: nowrap on
 * non-SKU cells + lift in-cell anchors + status pills to 44px hit area. */
@media (max-width: 720px) {
  .vendor-section td.id-col,
  .vendor-section td.title-col,
  .vendor-section td.num,
  .vendor-section td.status-col { white-space: normal; word-break: break-word; }
  .vendor-section td.sku-col { white-space: normal; }
  /* R2-T5: vendor id-col anchors lift to 44px hit area. */
  .vendor-section td.id-col a { min-height: 44px;
    display: inline-flex; align-items: center; padding: 8px 0;
    box-sizing: border-box; }
  /* R2-T5: status badge floor — bumped from 10px/2px-7px (~18px tall) to a
   * comfortable 28px+. Not 44px (it's a non-interactive label, not a button)
   * but visually readable + matches the audit recommendation. */
  .vendor-section .status-badge-mini { min-height: 28px;
    padding: 6px 10px; font-size: 12px;
    display: inline-flex; align-items: center; box-sizing: border-box; }
}
"""


# Map each normalised vendor name to a canon bucket per DESIGN_SPEC §5d (locked
# 2026-05-16). Lower-cased substring match. Order matters: more specific buckets
# first. Anything unmatched falls into "(other / TCW / specialty)".
_CANON_BUCKETS = [
    ("west_elm",         "West Elm",                ["west elm", "westelm"]),
    ("article_cb_rb",    "Article / C&B / R&B",     ["article", "crate & barrel", "crate and barrel",
                                                     "room & board", "room and board", " cb2"]),
    ("schoolhouse_rej",  "Schoolhouse + Rejuv.",    ["schoolhouse", "rejuvenation"]),
    ("pb_anthro_sl",     "Pottery Barn / Anthro / S&L", ["pottery barn", "anthropologie", "anthro", "serena", "lily"]),
    ("ferm_hay_muuto",   "ferm LIVING / HAY / Muuto", ["ferm living", "ferm-living", "hay", "muuto"]),
    ("vintage",          "Vintage",                 ["vintage", "chairish", "1stdibs", "city issue",
                                                     "westside modern", "etsy vintage"]),
]

_CANON_BUCKET_TARGETS = {
    # min_pct, max_pct from DESIGN_SPEC §5d
    "west_elm": (35.0, 40.0),
    "article_cb_rb": (20.0, 25.0),
    "schoolhouse_rej": (15.0, 15.0),
    "pb_anthro_sl": (8.0, 8.0),
    "ferm_hay_muuto": (3.0, 3.0),
    "vintage": (8.0, 12.0),
}


def _bucket_for_vendor(vendor: str) -> str:
    v = (vendor or "").lower()
    for key, _label, needles in _CANON_BUCKETS:
        if any(needle in v for needle in needles):
            return key
    return "other"


def _vendor_for_item(item: Item) -> Optional[str]:
    """Return the vendor string to attribute this item to in /vendors.

    Strategy (per spec):
    - Top-level item.vendor wins when set. Canon-decided items where the
      vendor lived in `decided_sku` prose now carry a structured vendor on
      the item itself, so we route them to the right bucket directly.
    - Items with options: use the ★ recommend option's vendor; fallback to
      options[0].
    - Vintage items: bucket under "Vintage" string.
    - Canon-decided with no top-level vendor and no options: return None and
      pool under "(canon-locked — vendor in spec text)".
    """
    if item.vendor:
        return item.vendor.strip()
    if item.vintage_brief is not None:
        return "Vintage"
    if item.options:
        rec = next((o for o in item.options if o.recommend), None)
        if rec and rec.vendor:
            return rec.vendor.strip()
        if item.options[0].vendor:
            return item.options[0].vendor.strip()
    return None


def _status_class_mini(status: str) -> str:
    if status == "decided":
        return "status-decided"
    if status in {"watch_list", "found_candidate"}:
        return "status-watch"
    if status in {"options_drafted", "awaiting_sample", "sample_in_hand"}:
        return "status-drafted"
    return "status-other"


def render_vendors_page(items: List[Item], meta: Meta,
                        last_changed_map: Optional[Dict[str, str]] = None) -> str:
    """Render /vendors — items grouped by vendor, sorted by total $ desc, with a
    canon-mix coherence check against DESIGN_SPEC §5d brand-share targets.
    Items with no resolvable vendor (canon-decided text spec, no options) are pooled
    under "(canon-locked, vendor in spec text)" so the sum stays accurate."""
    visible = [it for it in items if it.decision_status != "stub"]
    lc = last_changed_map or {}

    # Group items by resolved vendor string
    groups: Dict[str, List[Item]] = {}
    unattributed: List[Item] = []
    for it in visible:
        vendor = _vendor_for_item(it)
        if vendor is None:
            unattributed.append(it)
        else:
            groups.setdefault(vendor, []).append(it)

    if unattributed:
        groups["(canon-locked — vendor in spec text)"] = unattributed

    cap = meta.budgets.construction_cap

    # Compute per-vendor totals
    vendor_rows = []
    bucket_sums: Dict[str, float] = {k: 0.0 for k, _, _ in _CANON_BUCKETS}
    bucket_sums["other"] = 0.0
    total_budgeted = 0.0
    for vendor, vitems in groups.items():
        sub_total = sum((it.budget_target_usd or 0) for it in vitems)
        total_budgeted += sub_total
        bucket_key = _bucket_for_vendor(vendor)
        bucket_sums[bucket_key] = bucket_sums.get(bucket_key, 0.0) + sub_total
        vendor_rows.append((vendor, vitems, sub_total))

    vendor_rows.sort(key=lambda x: -x[2])

    # Build canon-mix summary block
    mix_rows_html = []
    for key, label, _needles in _CANON_BUCKETS:
        sub = bucket_sums.get(key, 0.0)
        pct = (sub / cap * 100) if cap else 0.0
        lo, hi = _CANON_BUCKET_TARGETS[key]
        # Within band if pct is inside [lo - 5, hi + 5] window? Spec says >5pp outside.
        within = (pct >= lo - 5.0) and (pct <= hi + 5.0)
        target_text = f"{lo:.0f}-{hi:.0f}%" if lo != hi else f"{lo:.0f}%"
        status_cls = "within" if within else "out"
        status_text = "within band" if within else f"&#9888; >5pp outside"
        mix_rows_html.append(
            f'<tr><td>{escape(label)}</td>'
            f'<td class="num">${sub:,.0f}</td>'
            f'<td class="num">{pct:.1f}%</td>'
            f'<td class="num">{target_text}</td>'
            f'<td class="{status_cls}">{status_text}</td></tr>'
        )
    # Plus the unbucketed
    other_sum = bucket_sums.get("other", 0.0)
    other_pct = (other_sum / cap * 100) if cap else 0.0
    mix_rows_html.append(
        f'<tr><td>(other / TCW / specialty)</td>'
        f'<td class="num">${other_sum:,.0f}</td>'
        f'<td class="num">{other_pct:.1f}%</td>'
        f'<td class="num">&mdash;</td>'
        f'<td>&mdash;</td></tr>'
    )

    canon_summary_html = (
        f'<div class="vendor-mix-summary">'
        f'<h3>Canon brand-mix coherence</h3>'
        f'<p class="lead">Share of ${cap:,.0f} construction cap by canon bucket vs DESIGN_SPEC '
        f'&sect;5d targets. Warns if a bucket is more than 5pp outside its target band.</p>'
        f'<div class="table-wrapper">'
        f'<table>'
        f'<thead><tr><th>Bucket</th><th class="num">$</th><th class="num">% of cap</th>'
        f'<th class="num">Target</th><th>Status</th></tr></thead>'
        f'<tbody>{"".join(mix_rows_html)}</tbody>'
        f'</table>'
        f'</div>'
        f'</div>'
    )

    # Build per-vendor sections
    sections_html_parts = []
    for vendor, vitems, sub_total in vendor_rows:
        pct_of_cap = (sub_total / cap * 100) if cap else 0.0
        rows_inner = []
        for it in sorted(vitems, key=lambda x: -(x.budget_target_usd or 0)):
            badge_class, badge_text = STATUS_BADGE.get(it.decision_status, ("", it.decision_status))
            badge_class_mini = _status_class_mini(it.decision_status)
            # SKU column: decided_sku for canon-locks, ★ option SKU otherwise
            if it.decided_sku:
                sku_display = it.decided_sku
            elif it.options:
                rec = next((o for o in it.options if o.recommend), None)
                if rec:
                    sku_display = rec.sku
                else:
                    sku_display = it.options[0].sku if it.options else ""
            elif it.vintage_brief:
                sku_display = "(vintage hunt)"
            else:
                sku_display = ""
            # Price column
            if it.options:
                rec = next((o for o in it.options if o.recommend), None)
                price_val = rec.price_usd if rec else it.options[0].price_usd
                price_display = f"${price_val:,.0f}"
            else:
                price_display = f"${(it.budget_target_usd or 0):,.0f}"
            changed_str = lc.get(it.id, "")
            changed_display = f"<br><small style=\"color:var(--muted);\">changed {escape(changed_str)}</small>" if changed_str else ""
            rows_inner.append(
                f'<tr>'
                f'<td class="id-col"><a href="/sourcing#item-{escape(it.id)}" style="color:var(--ink);text-decoration:none;border-bottom:1px dotted var(--accent);">{escape(it.id)}</a>{changed_display}</td>'
                f'<td class="title-col">{escape(it.title)}</td>'
                f'<td class="sku-col">{escape(sku_display[:120])}</td>'
                f'<td class="num">{price_display}</td>'
                f'<td class="status-col"><span class="status-badge-mini {badge_class_mini}">{escape(badge_text)}</span></td>'
                f'</tr>'
            )
        bucket_key = _bucket_for_vendor(vendor)
        bucket_label = next((lbl for k, lbl, _ in _CANON_BUCKETS if k == bucket_key), "other")
        sections_html_parts.append(
            f'<section class="vendor-section">'
            f'<div class="vendor-section-header">'
            f'<h2>{escape(vendor)}</h2>'
            f'<span class="meta"><strong>{len(vitems)}</strong> items &middot; '
            f'<strong>${sub_total:,.0f}</strong> budgeted &middot; '
            f'<strong>{pct_of_cap:.1f}%</strong> of cap &middot; '
            f'bucket: {escape(bucket_label)}</span>'
            f'</div>'
            f'<div class="table-wrapper"><table><tbody>{"".join(rows_inner)}</tbody></table></div>'
            f'</section>'
        )

    sections_html = "\n".join(sections_html_parts)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Vendors &middot; Sourcing &middot; 1490 Lively Ridge</title>
<meta name="description" content="Items grouped by vendor for batch ordering and sample requests. {len(visible)} items across {len(groups)} vendors.">
<style>{SHARED_CSS}
{VENDORS_CSS}</style>
</head>
<body class="vendors-page">
{VENDORS_TOPNAV_HTML}
<header class="page-header">
  <h1>Vendors</h1>
  <p class="subtitle">{len(visible)} items grouped by vendor for batch ordering. Total budgeted across vendors: ${total_budgeted:,.0f} of ${cap:,.0f} cap. Updated {escape(meta.last_updated)}.</p>
</header>
<main>
{canon_summary_html}
{sections_html}
</main>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# /suppliers — supplier directory browse surface
# Reads scope/supplier_directory.yaml (separate from sourcing.yaml). Browse-style
# discovery for where to look across the 15 design categories. Not a tracker.
# ---------------------------------------------------------------------------

SUPPLIERS_TOPNAV_HTML = _build_topnav_html("suppliers")

SUPPLIERS_CSS = """
.suppliers-page main { max-width: 1200px; }
.suppliers-anchor-block { background: var(--card-bg); border: 1px solid var(--border);
  border-radius: 10px; padding: 16px 20px; margin: 0 0 20px; }
.suppliers-anchor-block h3 { margin: 0 0 8px; font-size: 14px; font-weight: 700;
  text-transform: uppercase; letter-spacing: 0.6px; color: var(--accent); }
.suppliers-anchor-block p { margin: 4px 0; font-size: 13.5px; color: var(--ink);
  line-height: 1.55; }
.suppliers-anchor-block strong { color: var(--ink); }
.suppliers-filter-bar { display: flex; gap: 10px; flex-wrap: wrap; padding: 12px 0;
  margin: 0 0 18px; border-top: 1px solid var(--border);
  border-bottom: 1px solid var(--border);
  position: sticky; top: var(--topnav-h); background: var(--bg); z-index: 40; align-items: center; }
.suppliers-filter-bar label { font-size: 11.5px; color: var(--muted); font-weight: 600;
  text-transform: uppercase; letter-spacing: 0.5px; margin-right: 4px; }
.suppliers-filter-bar input[type=search] { background: var(--card-bg);
  border: 1px solid var(--border); border-radius: 999px; padding: 6px 14px;
  font-size: 13px; color: var(--ink); min-width: 220px; }
.suppliers-filter-bar select { background: var(--card-bg); border: 1px solid var(--border);
  border-radius: 999px; padding: 5px 12px; font-size: 13px; color: var(--ink); }
.suppliers-filter-bar button { background: var(--card-bg); border: 1px solid var(--border);
  border-radius: 999px; padding: 5px 14px; font-size: 13px; cursor: pointer;
  color: var(--ink); }
.suppliers-filter-bar button:hover { background: var(--warm-tint); border-color: #c9b88a; }
.suppliers-filter-bar .filter-stats { margin-left: auto; font-size: 12px; color: var(--muted); }

.suppliers-page-layout { display: grid; grid-template-columns: 200px 1fr; gap: 24px;
  align-items: flex-start; }
/* R2-C5: sticky offset derives from --topnav-h plus the suppliers filter-bar
 * row so the side nav lands below both, not at a hardcoded 100px. */
.category-side-nav { position: sticky; top: calc(var(--topnav-h) + 52px);
  align-self: flex-start;
  font-size: 12.5px; background: var(--card-bg); border: 1px solid var(--border);
  border-radius: 10px; padding: 14px 6px; }
.category-side-nav h4 { margin: 0 0 8px; padding: 0 8px; font-size: 11px;
  text-transform: uppercase; letter-spacing: 0.5px; color: var(--muted); }
.category-side-nav a { display: block; padding: 5px 8px; border-radius: 4px;
  color: var(--ink); text-decoration: none; line-height: 1.35; margin-bottom: 1px; }
.category-side-nav a:hover { background: var(--warm-tint); color: var(--accent); }
.category-side-nav a .count { color: var(--muted); font-size: 10.5px; margin-left: 4px; }
/* R2-C6: collapse the supplier two-column layout at the unified 720px breakpoint
 * (was 900px, an outlier vs. the site-wide 720/480 baseline). */
@media (max-width: 720px) {
  .suppliers-page-layout { grid-template-columns: 1fr; }
  .category-side-nav { position: static; }
}

.category-section { margin: 0 0 36px; scroll-margin-top: calc(var(--topnav-h) + 62px); }
.category-section-header { display: flex; align-items: baseline; gap: 14px;
  padding: 0 0 8px; border-bottom: 1px solid var(--border); margin: 0 0 16px; }
/* R5-UX2: Single Japandi serif moment — category h2 only. Other headings
 * stay sans, body stays sans. The lone serif anchors visual hierarchy
 * per DESIGN_SPEC §4 principle 1 (restraint). DM Serif Display is loaded
 * as a CDN-free fallback chain; Georgia is the safe Japandi-warm fallback
 * so we don't ship a webfont request. */
.category-section-header h2 { margin: 0; font-size: 24px; font-weight: 400;
  letter-spacing: -0.3px; flex: 1;
  font-family: "DM Serif Display", "Cormorant Garamond", "Playfair Display",
    Georgia, "Times New Roman", serif; }
.category-section-header .cat-count { font-size: 12px; color: var(--muted);
  font-variant-numeric: tabular-nums; }

.supplier-card-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 14px; }
.supplier-card { background: var(--card-bg); border: 1px solid var(--border);
  border-radius: 10px; padding: 14px 16px; display: flex; flex-direction: column;
  gap: 8px; transition: border-color .15s, box-shadow .15s; }
.supplier-card.hidden { display: none; }
.supplier-card:hover { border-color: #c9b88a;
  box-shadow: 0 2px 8px rgba(42, 38, 34, 0.06); }
.supplier-card-header { display: flex; align-items: baseline; gap: 8px;
  flex-wrap: wrap; }
.supplier-card-header h3 { margin: 0; font-size: 16px; font-weight: 600; flex: 1;
  letter-spacing: -0.1px; }
.supplier-pill { display: inline-block; font-size: 10px; padding: 2px 8px;
  border-radius: 999px; text-transform: uppercase; letter-spacing: 0.5px;
  font-weight: 700; white-space: nowrap; }
.supplier-pill.tier-entry { background: #e8efe2; color: #3a5a3a; }
/* R5-UX1: tier-mid swapped from cool-blue #dde6f0 → warm-sand #ebe5d8 to
 * eliminate the only cool tone in an otherwise warm Japandi palette. */
.supplier-pill.tier-mid { background: #ebe5d8; color: #5a4e30; }
.supplier-pill.tier-premium { background: #f7e6cb; color: #8a5a10; }
.supplier-pill.tier-aspirational { background: #f8e6df; color: #973a1c; }
.supplier-pill.fit-strong { background: #d9ead2; color: #2a5a2a; }
.supplier-pill.fit-good { background: #e8efe2; color: #3a5a3a; }
.supplier-pill.fit-mixed { background: #fef0d6; color: #6e4f1a; }
.supplier-pill.fit-canon-adjacent { background: #ece8f4; color: #4a4566; }
/* R5-UX5: merged tier·fit pill. Keeps the fit pill's load-bearing color,
 * adds a quieter prefix carrying the tier label. Drops spec-strip element
 * count 6 → 5 to satisfy DESIGN_SPEC §4 principle 1 (5-7 elements). */
.supplier-pill.supplier-pill-merged { padding: 2px 10px; }
.supplier-pill.supplier-pill-merged .merged-tier { font-weight: 600;
  opacity: 0.65; text-transform: none; letter-spacing: 0; font-size: 9.5px; }
.supplier-pill.supplier-pill-merged .merged-sep { opacity: 0.45;
  margin: 0 2px; font-weight: 400; }
.supplier-pill.supplier-pill-merged .merged-fit { font-weight: 700; }
.supplier-card .fingerprint { font-size: 13px; color: var(--ink); line-height: 1.5;
  margin: 0; }
.supplier-card .fit-line { font-size: 12px; color: var(--muted); line-height: 1.45; }
.supplier-card .fit-line strong { color: var(--ink); }
/* R5-UX1: warning-line darkened from #f8e6df/#fbe9df → #f0d6c0 to
 * differentiate from aspirational pill (same family, deeper saturation
 * signals "needs attention"). */
.supplier-card .warning-line { font-size: 12px; color: #7a3010;
  background: #f0d6c0; border-radius: 5px; padding: 5px 8px; line-height: 1.45; }
.supplier-card .collections { display: flex; flex-wrap: wrap; gap: 5px; margin: 4px 0; }
.supplier-card .collection-chip { font-size: 11.5px; padding: 3px 9px;
  border-radius: 999px; background: var(--warm-tint); color: var(--ink);
  text-decoration: none; border: 1px solid #e9d4a2; }
.supplier-card .collection-chip:hover { background: #f1dba0; }
.supplier-card .footer-line { font-size: 11px; color: var(--muted);
  border-top: 1px dashed var(--border); padding-top: 7px; margin-top: 4px;
  line-height: 1.5; }
.supplier-card .footer-line strong { color: var(--ink); text-transform: uppercase;
  letter-spacing: 0.4px; font-size: 10px; margin-right: 3px; }
.supplier-card .explore-btn { display: inline-block; align-self: flex-start;
  background: var(--accent); color: white; text-decoration: none;
  padding: 6px 14px; border-radius: 999px; font-size: 12px; font-weight: 600;
  margin-top: 2px; }
.supplier-card .explore-btn:hover { background: #6e6346; }
.suppliers-empty { background: var(--note-tint); border-radius: 8px; padding: 24px;
  text-align: center; color: var(--muted); font-size: 14px; }

/* === Hero image === */
.supplier-hero { width: 100%; height: 130px; border-radius: 8px; overflow: hidden;
  background: var(--warm-tint); border: 1px solid var(--border); margin: 0 0 6px;
  display: flex; align-items: center; justify-content: center; }
.supplier-hero img { width: 100%; height: 100%; object-fit: cover; display: block; }
.supplier-hero-placeholder { font-family: Georgia, 'Times New Roman', serif;
  font-size: 18px; color: #8a7e60; letter-spacing: 0.3px; text-align: center;
  padding: 8px 12px; background: linear-gradient(135deg, #f4ecd6, #ece4cc); }
.supplier-hero-placeholder span { display: block; line-height: 1.2; }

/* === Verification badge === */
.supplier-card-header .verif-badge { margin-left: auto; font-size: 10px;
  padding: 2px 7px; border-radius: 999px; cursor: help; border: 1px solid transparent;
  text-transform: uppercase; letter-spacing: 0.4px; font-weight: 700; font-family: inherit;
  position: relative; }
.verif-badge.verif-ok { background: #d9ead2; color: #2a5a2a; border-color: #b9d2af; }
/* R5-UX1: verif-warn shifted from peach (#fbe9df) → muted cream (#f4ebd0)
 * to differentiate from aspirational pill + warning-line. A subtler tone
 * matches the badge's advisory role (URL un-verified, not "AVOID"). */
.verif-badge.verif-warn { background: #f4ebd0; color: #6e4f1a; border-color: #e2d5a8; }
/* Hover tooltip now lives in the .verif-tooltip span (see R2 UX6 block below). */

/* === /sourcing cross-link === */
.sourcing-crosslink { font-size: 11.5px; border-top: 1px dashed var(--border);
  padding: 7px 0 0; margin-top: 4px; line-height: 1.45; }
.sourcing-crosslink.has-matches a { color: var(--ink); text-decoration: none;
  display: inline-block; }
.sourcing-crosslink.has-matches a:hover { color: var(--accent); }
.sourcing-crosslink .crosslink-ids { color: var(--muted); font-variant-numeric: tabular-nums;
  font-size: 11px; }
.sourcing-crosslink.no-matches { color: var(--muted); font-style: italic; }

/* === Tri-state action selector === */
.supplier-action { display: flex; gap: 4px; margin-top: 4px; }
.supplier-action .action-btn { flex: 1; font-size: 11px; padding: 4px 6px;
  border-radius: 6px; border: 1px solid var(--border); background: var(--card-bg);
  color: var(--muted); cursor: pointer; font-family: inherit;
  transition: background .12s, color .12s, border-color .12s; }
.supplier-action .action-btn:hover { background: var(--warm-tint); }
/* R5-UX1: action-visit shifted from cool-blue #dde6f0 → warm dusty
 * terracotta to (a) eliminate the last cool tone in the palette and
 * (b) distinguish from tier-mid (now warm-sand). */
.supplier-action .action-btn.active.action-visit { background: #ead6c2; color: #6a3f1a;
  border-color: #c8a279; }
.supplier-action .action-btn.active.action-saved { background: #d9ead2; color: #2a5a2a;
  border-color: #aac9a0; }
.supplier-action .action-btn.active.action-ruled { background: #ececec; color: #555;
  border-color: #c5c5c5; }
/* Card border-color shift based on action state */
.supplier-card[data-action-state="visit"] { border-color: #c8a279; box-shadow: 0 0 0 1px rgba(200, 162, 121, 0.3); }
.supplier-card[data-action-state="saved"] { border-color: #aac9a0; box-shadow: 0 0 0 1px rgba(170, 201, 160, 0.3); }
.supplier-card[data-action-state="ruled"] { border-color: #c5c5c5; opacity: 0.55; }

/* === Filter additions === */
.suppliers-filter-bar .action-filter { display: flex; gap: 4px; align-items: center;
  margin-left: 4px; }
.suppliers-filter-bar .action-filter button { padding: 4px 10px; font-size: 12px;
  background: var(--card-bg); border: 1px solid var(--border); border-radius: 999px;
  cursor: pointer; color: var(--muted); }
.suppliers-filter-bar .action-filter button.active { background: var(--accent);
  color: white; border-color: var(--accent); }
.suppliers-filter-bar #copy-filter-url { background: var(--card-bg); color: var(--ink);
  border-color: var(--border); }
.suppliers-filter-bar #copy-filter-url:hover { background: var(--warm-tint); }
.suppliers-filter-bar #copy-filter-url.copied { background: #d9ead2; color: #2a5a2a;
  border-color: #b9d2af; }
.suppliers-filter-bar select#sort-by { background: var(--card-bg);
  border: 1px solid var(--border); border-radius: 999px; padding: 5px 12px;
  font-size: 13px; color: var(--ink); }

/* === R2 UX1: spec strip (replaces 4-pill header row) === */
.supplier-spec-strip { display: flex; gap: 6px; align-items: center;
  flex-wrap: wrap; margin: 2px 0 0; }
.supplier-spec-strip .spec-price { font-size: 11.5px; color: var(--muted);
  font-variant-numeric: tabular-nums; }

/* === R2 UX1: collapsible details expander === */
.supplier-details { margin-top: 4px; }
.supplier-details summary { cursor: pointer; font-size: 11.5px;
  color: var(--accent); font-weight: 600; padding: 4px 0;
  letter-spacing: 0.3px; user-select: none;
  border-top: 1px dashed var(--border); }
.supplier-details summary:hover { color: var(--ink); }
.supplier-details[open] summary { margin-bottom: 6px; }

/* === R2 UX5: hero visual-class badge === */
.supplier-hero { position: relative; }
.hero-class-badge { position: absolute; top: 6px; right: 6px; font-size: 13px;
  background: rgba(42, 38, 34, 0.78); color: #f7f1e3; border-radius: 999px;
  padding: 2px 6px; line-height: 1; backdrop-filter: blur(4px);
  cursor: help; user-select: none; }
.hero-class-placeholder { background: rgba(138, 122, 90, 0.85); }
.hero-class-broken { background: rgba(151, 58, 28, 0.92); color: #fff5ed; }

/* === R2 UX6: verification badge :focus-visible fallback for touch/keyboard === */
.verif-badge { position: relative; }
.verif-badge .verif-tooltip { display: none; position: absolute; right: 0;
  top: 100%; margin-top: 4px; z-index: 50;
  background: #2a2622; color: #f7f1e3; padding: 6px 10px; border-radius: 6px;
  font-size: 11px; font-weight: 500; text-transform: none; letter-spacing: 0;
  white-space: normal; min-width: 200px; max-width: 320px; line-height: 1.4;
  box-shadow: 0 2px 10px rgba(0,0,0,0.18); }
.verif-badge:hover .verif-tooltip,
.verif-badge:focus-visible .verif-tooltip,
.verif-badge:focus .verif-tooltip { display: block; }
.verif-badge:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }

/* === R2 UX8: ruled-out default-hide toggle === */
.suppliers-page.hide-ruled .supplier-card[data-action-state="ruled"] { display: none; }
.suppliers-ruled-toggle { display: inline-flex; align-items: center;
  gap: 6px; font-size: 11.5px; color: var(--muted); cursor: pointer;
  margin-left: 4px; user-select: none; }
.suppliers-ruled-toggle input { margin: 0; cursor: pointer; }

/* === R2 UX9: active-filter pills under filter bar === */
.active-filter-pills { display: flex; flex-wrap: wrap; gap: 6px;
  margin: 0 0 14px; padding: 4px 0; min-height: 24px; }
.active-filter-pills:empty { display: none; }
.active-filter-pill { background: var(--warm-tint);
  border: 1px solid #e9d4a2; color: var(--ink); font-size: 11.5px;
  padding: 3px 9px; border-radius: 999px; display: inline-flex;
  align-items: center; gap: 4px; }
.active-filter-pill button { background: none; border: none; color: var(--muted);
  cursor: pointer; padding: 0 2px; font-size: 13px; line-height: 1; }
.active-filter-pill button:hover { color: #973a1c; }

/* === R2 UX1: empty-state message === */
.suppliers-empty-state { background: var(--note-tint); border-radius: 8px;
  padding: 24px; text-align: center; color: var(--muted); font-size: 14px;
  margin: 20px 0; display: none; }
.suppliers-empty-state.is-visible { display: block; }
.suppliers-empty-state button { background: var(--accent); color: white;
  border: none; padding: 6px 14px; border-radius: 999px; font-size: 12px;
  font-weight: 600; cursor: pointer; margin-top: 8px; }

/* === R3 Fix UX3: Mobile filter-bar collapse via <details class="mobile-filters"> ===
 * Desktop default: summary hidden, panel always shown. Mobile: summary becomes
 * a tap-target; panel collapses unless [open]. Closes Claude's "dead CSS" critical. */
details.mobile-filters > summary.mobile-filters-summary { display: none; }
details.mobile-filters > .suppliers-filter-bar { display: flex; }

/* === R2 UX2: Mobile media queries (≤720px) === */
@media (max-width: 720px) {
  /* R4-3: tighten .suppliers-anchor-block so the orientation block doesn't
   * eat ~140px above the filter drawer on phones. ~60px total now.
   * Note: rendered markup uses <h3> not <h2>; selector targets both for
   * robustness in case the block grows other heading levels later. */
  .suppliers-anchor-block { padding: 12px 16px; margin-bottom: 12px; font-size: 14px; }
  .suppliers-anchor-block h2,
  .suppliers-anchor-block h3 { font-size: 1.15rem; margin: 0 0 6px; }
  /* R3 Fix UX3: <details class="mobile-filters"> becomes collapsible.
   * Summary is the always-visible tap-target. The filter-bar inside is shown
   * only when the details is [open]. */
  details.mobile-filters > summary.mobile-filters-summary {
    display: flex; justify-content: space-between; align-items: center;
    background: var(--card-bg); border: 1px solid var(--border);
    border-radius: 999px; padding: 8px 14px; font-size: 13px;
    font-weight: 600; cursor: pointer; user-select: none;
    list-style: none; min-height: 44px; box-sizing: border-box; }
  details.mobile-filters > summary.mobile-filters-summary::-webkit-details-marker { display: none; }
  details.mobile-filters > summary.mobile-filters-summary::marker { display: none; }
  details.mobile-filters > summary.mobile-filters-summary .mobile-filters-chevron {
    transition: transform .15s; }
  details.mobile-filters[open] > summary.mobile-filters-summary .mobile-filters-chevron {
    transform: rotate(180deg); }
  details.mobile-filters:not([open]) > .suppliers-filter-bar { display: none; }
  details.mobile-filters[open] > .suppliers-filter-bar { display: flex;
    border-top: 1px solid var(--border); margin-top: 8px; padding-top: 12px; }
  /* Filter bar itself: looser sticky behavior on mobile */
  .suppliers-filter-bar { padding: 8px 0; }
  /* Single-column card grid */
  .supplier-card-grid { grid-template-columns: 1fr; gap: 12px; }
  /* Hero shorter on mobile */
  .supplier-hero { height: 140px; }
  /* Tap-targets: action selector becomes 44px tall on touch */
  .supplier-action .action-btn { padding: 10px 6px; min-height: 44px;
    font-size: 12px; }
  .supplier-action { gap: 6px; }
  .collection-chip { padding: 10px 14px; min-height: 44px;
    display: inline-flex; align-items: center; }
  /* Verification tooltip can't overflow viewport */
  .verif-badge .verif-tooltip { right: auto; left: 0;
    max-width: calc(100vw - 60px); }
  /* Topnav already shrinks; nothing extra */
}
"""

# JavaScript filter + random-pick + action persistence + URL sync + sort
# — interpolated as string to avoid double-braces. Note: keep ALL { } as JS braces.
SUPPLIERS_JS = """
<script>
(function() {
  const cards = Array.from(document.querySelectorAll('.supplier-card'));
  const sections = Array.from(document.querySelectorAll('.category-section'));
  const searchInput = document.getElementById('supplier-search');
  const catSelect = document.getElementById('cat-filter');
  const tierSelect = document.getElementById('tier-filter');
  const fitSelect = document.getElementById('fit-filter');
  const sortSelect = document.getElementById('sort-by');
  const resetBtn = document.getElementById('reset-filters');
  const randomBtn = document.getElementById('random-pick');
  const copyBtn = document.getElementById('copy-filter-url');
  const actionFilterBtns = Array.from(document.querySelectorAll('.action-filter button'));
  const stats = document.getElementById('filter-stats');
  const hideRuledToggle = document.getElementById('hide-ruled-toggle');
  const activeFilterPills = document.getElementById('active-filter-pills');
  const emptyState = document.getElementById('suppliers-empty-state');
  const emptyStateClear = document.getElementById('empty-state-clear');
  const totalCards = cards.length;
  const ACTION_STORE_KEY = 'suppliers.actions.v1';
  const HIDE_RULED_KEY = 'suppliers.hideRuled.v1';
  let currentActionFilter = 'all';

  // R2 Fix UX8 — restore hide-ruled toggle state from localStorage (default ON).
  try {
    const stored = localStorage.getItem(HIDE_RULED_KEY);
    if (stored === 'false') hideRuledToggle.checked = false;
  } catch (e) {}
  function syncHideRuledClass() {
    document.body.classList.toggle('hide-ruled', hideRuledToggle.checked);
  }
  syncHideRuledClass();

  // --- localStorage actions ---
  function loadActions() {
    try { return JSON.parse(localStorage.getItem(ACTION_STORE_KEY) || '{}'); }
    catch (e) { return {}; }
  }
  function saveActions(actions) {
    try { localStorage.setItem(ACTION_STORE_KEY, JSON.stringify(actions)); }
    catch (e) { /* quota or disabled */ }
  }
  function applyActionToCard(card, state) {
    card.dataset.actionState = state || '';
    const btns = card.querySelectorAll('.supplier-action .action-btn');
    let firstFocusable = null;
    btns.forEach(b => {
      const isActive = state && b.dataset.action === state;
      b.classList.toggle('active', isActive);
      // R3 Fix UX6 — keep aria-checked in sync with active state.
      b.setAttribute('aria-checked', isActive ? 'true' : 'false');
      if (isActive) {
        b.setAttribute('tabindex', '0');
      } else {
        b.setAttribute('tabindex', '-1');
      }
      if (!firstFocusable) firstFocusable = b;
    });
    // Roving tabindex: when nothing selected, the first button is the entry point.
    if (!state && firstFocusable) firstFocusable.setAttribute('tabindex', '0');
  }
  function setAction(card, state) {
    const actions = loadActions();
    const id = card.dataset.supplierId;
    if (!state) delete actions[id]; else actions[id] = state;
    saveActions(actions);
    applyActionToCard(card, state);
    applyFilters();
  }

  // --- Wire tri-state buttons per card ---
  cards.forEach(card => {
    const id = card.dataset.supplierId;
    const actions = loadActions();
    if (actions[id]) applyActionToCard(card, actions[id]);
    else applyActionToCard(card, ''); // ensure roving-tabindex entry point exists.
    const groupBtns = Array.from(card.querySelectorAll('.supplier-action .action-btn'));
    groupBtns.forEach((btn, idx) => {
      btn.addEventListener('click', e => {
        e.preventDefault();
        const wanted = btn.dataset.action;
        const cur = card.dataset.actionState || '';
        setAction(card, cur === wanted ? '' : wanted);
      });
      // R3 Fix UX6 — arrow-key navigation across the radio group + space/enter to select.
      // R4 Fix V2 — arrow keys must also UPDATE the selected radio (call
      // setAction with the target value) and the roving tabindex, not just
      // move DOM focus. This matches the standard ARIA radiogroup pattern;
      // R3 Beta's claim that this was implemented was rejected by Codex
      // because the original handler only focused without selecting.
      btn.addEventListener('keydown', e => {
        const key = e.key;
        if (key === 'ArrowRight' || key === 'ArrowDown') {
          e.preventDefault();
          const next = groupBtns[(idx + 1) % groupBtns.length];
          // Select the target radio (updates aria-checked + roving tabindex
          // via applyActionToCard inside setAction) then move focus.
          setAction(card, next.dataset.action);
          next.focus();
        } else if (key === 'ArrowLeft' || key === 'ArrowUp') {
          e.preventDefault();
          const prev = groupBtns[(idx - 1 + groupBtns.length) % groupBtns.length];
          setAction(card, prev.dataset.action);
          prev.focus();
        } else if (key === ' ' || key === 'Enter') {
          e.preventDefault();
          const wanted = btn.dataset.action;
          const cur = card.dataset.actionState || '';
          setAction(card, cur === wanted ? '' : wanted);
        }
      });
    });
  });

  // --- URL parameter sync ---
  function readUrlParams() {
    const p = new URLSearchParams(window.location.search);
    if (p.has('q')) searchInput.value = p.get('q');
    if (p.has('category')) catSelect.value = p.get('category');
    if (p.has('tier')) tierSelect.value = p.get('tier');
    if (p.has('fit')) fitSelect.value = p.get('fit');
    if (p.has('sort') && sortSelect) sortSelect.value = p.get('sort');
    if (p.has('action')) {
      // R2 Fix C8 — allow-list the action query param.
      const VALID_ACTION_FILTERS = ['all', 'visit', 'saved', 'ruled', 'unrated'];
      const requested = p.get('action');
      currentActionFilter = VALID_ACTION_FILTERS.indexOf(requested) >= 0 ? requested : 'all';
      actionFilterBtns.forEach(b => b.classList.toggle('active', b.dataset.actionFilter === currentActionFilter));
    }
    // /sourcing cross-link uses ?vendor=<id> on the /sourcing page itself, but if someone
    // lands on /suppliers with ?vendor= we treat it as a search seed.
    if (p.has('vendor')) {
      const v = p.get('vendor');
      // Find that card and scroll to it, highlight briefly.
      const target = cards.find(c => c.dataset.supplierId === v);
      if (target) {
        setTimeout(() => {
          target.scrollIntoView({behavior: 'smooth', block: 'center'});
          target.style.boxShadow = '0 0 0 3px #c9b88a';
          setTimeout(() => { target.style.boxShadow = ''; }, 2000);
        }, 50);
      }
    }
  }
  function writeUrlParams() {
    const p = new URLSearchParams();
    if (searchInput.value) p.set('q', searchInput.value);
    if (catSelect.value) p.set('category', catSelect.value);
    if (tierSelect.value) p.set('tier', tierSelect.value);
    if (fitSelect.value) p.set('fit', fitSelect.value);
    if (sortSelect && sortSelect.value && sortSelect.value !== 'category') p.set('sort', sortSelect.value);
    if (currentActionFilter && currentActionFilter !== 'all') p.set('action', currentActionFilter);
    const qs = p.toString();
    const newUrl = window.location.pathname + (qs ? '?' + qs : '');
    history.replaceState(null, '', newUrl);
  }

  // --- Sorting ---
  function applySort() {
    if (!sortSelect) return;
    const mode = sortSelect.value;
    const tierOrder = {'entry': 0, 'mid': 1, 'premium': 2, 'aspirational': 3};
    const fitOrder = {'STRONG': 0, 'GOOD': 1, 'MIXED': 2, 'CANON-ADJACENT': 3};
    sections.forEach(sec => {
      const grid = sec.querySelector('.supplier-card-grid');
      if (!grid) return;
      const localCards = Array.from(grid.querySelectorAll('.supplier-card'));
      const sorted = localCards.slice();
      if (mode === 'tier') {
        // R2 Fix C4 — `|| 9` would push rank-0 ('entry', 'STRONG') to the bottom.
        // Use `??` so only nullish ranks fall through to the default.
        sorted.sort((a, b) => (tierOrder[a.dataset.tier] ?? 9) - (tierOrder[b.dataset.tier] ?? 9));
      } else if (mode === 'fit') {
        sorted.sort((a, b) => (fitOrder[a.dataset.fit] ?? 9) - (fitOrder[b.dataset.fit] ?? 9));
      } else if (mode === 'verified') {
        sorted.sort((a, b) => (b.dataset.verifiedDate || '').localeCompare(a.dataset.verifiedDate || ''));
      } else if (mode === 'random') {
        for (let i = sorted.length - 1; i > 0; i--) {
          const j = Math.floor(Math.random() * (i + 1));
          [sorted[i], sorted[j]] = [sorted[j], sorted[i]];
        }
      } else {
        // default: by name within section
        sorted.sort((a, b) => {
          const an = a.querySelector('h3') ? a.querySelector('h3').textContent : '';
          const bn = b.querySelector('h3') ? b.querySelector('h3').textContent : '';
          return an.localeCompare(bn);
        });
      }
      sorted.forEach(c => grid.appendChild(c));
    });
  }

  // --- Filter ---
  function applyFilters() {
    const q = (searchInput.value || '').toLowerCase().trim();
    const cat = catSelect.value;
    const tier = tierSelect.value;
    const fit = fitSelect.value;
    const actions = loadActions();
    let visible = 0;
    cards.forEach(card => {
      const matchCat = !cat || card.dataset.category === cat;
      const matchTier = !tier || card.dataset.tier === tier;
      const matchFit = !fit || card.dataset.fit === fit;
      const haystack = card.dataset.search;
      const matchQuery = !q || haystack.indexOf(q) !== -1;
      const state = actions[card.dataset.supplierId] || '';
      let matchAction = true;
      if (currentActionFilter === 'visit') matchAction = state === 'visit';
      else if (currentActionFilter === 'saved') matchAction = state === 'saved';
      else if (currentActionFilter === 'ruled') matchAction = state === 'ruled';
      else if (currentActionFilter === 'unrated') matchAction = !state;
      const shown = matchCat && matchTier && matchFit && matchQuery && matchAction;
      card.classList.toggle('hidden', !shown);
      if (shown) visible++;
    });
    sections.forEach(sec => {
      const any = Array.from(sec.querySelectorAll('.supplier-card')).some(c => !c.classList.contains('hidden'));
      sec.style.display = any ? '' : 'none';
    });
    stats.textContent = visible + ' of ' + totalCards + ' suppliers';
    // R2 Fix UX1 — empty-state UI when filters return zero results.
    if (emptyState) {
      emptyState.classList.toggle('is-visible', visible === 0 && totalCards > 0);
    }
    renderActiveFilterPills();
    writeUrlParams();
  }

  // R2 Fix UX9 — render a row of active-filter pills below the bar with × to clear.
  function renderActiveFilterPills() {
    if (!activeFilterPills) return;
    const pills = [];
    if (searchInput.value) {
      pills.push({label: 'search: "' + searchInput.value + '"', clear: () => { searchInput.value = ''; }});
    }
    if (catSelect.value) {
      pills.push({label: 'category: ' + catSelect.value, clear: () => { catSelect.value = ''; }});
    }
    if (tierSelect.value) {
      pills.push({label: 'tier: ' + tierSelect.value, clear: () => { tierSelect.value = ''; }});
    }
    if (fitSelect.value) {
      pills.push({label: 'fit: ' + fitSelect.value, clear: () => { fitSelect.value = ''; }});
    }
    if (currentActionFilter && currentActionFilter !== 'all') {
      pills.push({label: 'action: ' + currentActionFilter, clear: () => {
        currentActionFilter = 'all';
        actionFilterBtns.forEach(b => b.classList.toggle('active', b.dataset.actionFilter === 'all'));
      }});
    }
    activeFilterPills.innerHTML = '';
    pills.forEach(p => {
      const span = document.createElement('span');
      span.className = 'active-filter-pill';
      span.textContent = p.label + ' ';
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.textContent = '×';
      btn.setAttribute('aria-label', 'Remove ' + p.label + ' filter');
      btn.addEventListener('click', () => { p.clear(); applyFilters(); });
      span.appendChild(btn);
      activeFilterPills.appendChild(span);
    });
  }

  // --- Random pick (respects current filter) ---
  function pickRandom() {
    const visible = cards.filter(c => !c.classList.contains('hidden'));
    if (!visible.length) return;
    const pick = visible[Math.floor(Math.random() * visible.length)];
    pick.scrollIntoView({behavior: 'smooth', block: 'center'});
    pick.style.boxShadow = '0 0 0 3px #c9b88a';
    setTimeout(() => { pick.style.boxShadow = ''; }, 1800);
  }

  function resetAll() {
    searchInput.value = '';
    catSelect.value = '';
    tierSelect.value = '';
    fitSelect.value = '';
    if (sortSelect) sortSelect.value = 'category';
    currentActionFilter = 'all';
    actionFilterBtns.forEach(b => b.classList.toggle('active', b.dataset.actionFilter === 'all'));
    // Note: hide-ruled toggle state is intentionally preserved (it's a
    // user preference, not a filter). localStorage actions also preserved.
    applySort();
    applyFilters();
  }

  // --- Copy filter URL ---
  function copyFilterUrl() {
    const url = window.location.href;
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(url).then(() => {
        copyBtn.textContent = 'Copied!';
        copyBtn.classList.add('copied');
        setTimeout(() => { copyBtn.textContent = 'Copy link'; copyBtn.classList.remove('copied'); }, 1500);
      });
    } else {
      // Legacy
      const ta = document.createElement('textarea');
      ta.value = url; document.body.appendChild(ta); ta.select();
      try { document.execCommand('copy'); } catch (e) {}
      document.body.removeChild(ta);
      copyBtn.textContent = 'Copied!';
      setTimeout(() => { copyBtn.textContent = 'Copy link'; }, 1500);
    }
  }

  searchInput.addEventListener('input', applyFilters);
  catSelect.addEventListener('change', applyFilters);
  tierSelect.addEventListener('change', applyFilters);
  fitSelect.addEventListener('change', applyFilters);
  if (sortSelect) sortSelect.addEventListener('change', () => { applySort(); writeUrlParams(); });
  resetBtn.addEventListener('click', resetAll);
  randomBtn.addEventListener('click', pickRandom);
  if (copyBtn) copyBtn.addEventListener('click', copyFilterUrl);
  actionFilterBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      currentActionFilter = btn.dataset.actionFilter;
      actionFilterBtns.forEach(b => b.classList.toggle('active', b === btn));
      applyFilters();
    });
  });

  // R2 Fix UX8 — hide-ruled toggle handler.
  if (hideRuledToggle) {
    hideRuledToggle.addEventListener('change', () => {
      syncHideRuledClass();
      try { localStorage.setItem(HIDE_RULED_KEY, hideRuledToggle.checked ? 'true' : 'false'); }
      catch (e) {}
    });
  }
  if (emptyStateClear) {
    emptyStateClear.addEventListener('click', () => {
      searchInput.value = ''; catSelect.value = ''; tierSelect.value = ''; fitSelect.value = '';
      currentActionFilter = 'all';
      actionFilterBtns.forEach(b => b.classList.toggle('active', b.dataset.actionFilter === 'all'));
      applyFilters();
    });
  }

  // --- Init ---
  readUrlParams();
  applySort();
  applyFilters();
})();
</script>
"""


def _load_supplier_directory():
    """Load supplier_directory.yaml from HomeAI/scope.

    R2 Fix C2 — route through `sourcing_schema.load_supplier_directory()` which
    validates each supplier (id/name/category required; price_tier + fit checked
    against allow-lists) before the renderer touches the data. Returns None only
    when the file is genuinely absent — malformed YAML or invalid rows raise.

    The fallback (missing file) is preserved for tests that exercise the empty
    placeholder branch; build_sourcing.py treats missing-on-real-build as a
    loud failure (R2 Fix C9).
    """
    homeai_scope = Path.home() / "Desktop" / "HomeAI" / "scope"
    directory_path = homeai_scope / "supplier_directory.yaml"
    if not directory_path.exists():
        return None
    from sourcing_schema import load_supplier_directory
    return load_supplier_directory(str(directory_path))


# Tokens to ignore when normalizing a supplier name for vendor matching.
_VENDOR_NAME_NOISE = re.compile(r"[^a-z0-9]+")
# Aliases/expansions some vendor strings use vs the supplier brand name.
_VENDOR_ALIAS_MAP = {
    "west-elm": ["west elm", "westelm", "we"],
    "crate-barrel": ["crate barrel", "crateandbarrel", "crate and barrel", "c&b", "cb"],
    "room-board": ["room board", "roomandboard", "room and board", "r&b"],
    "pottery-barn": ["pottery barn", "potterybarn", "pb"],
    "rejuvenation": ["rejuvenation"],
    "schoolhouse": ["schoolhouse"],
    "ferm-living": ["ferm living", "fermliving"],
    "delta": ["delta", "delta faucet"],
    "kohler": ["kohler"],
    "toto": ["toto"],
    "babyletto": ["babyletto"],
    "kraftmaid": ["kraftmaid"],
    "ikea": ["ikea"],
    "benjamin-moore": ["benjamin moore"],
    "sherwin-williams": ["sherwin williams", "sherwin-williams", "sw"],
    "farrow-ball": ["farrow ball", "farrow & ball", "farrow and ball"],
    "daltile": ["daltile"],
    "cle-tile": ["cle", "cle tile"],
    "heath-ceramics": ["heath ceramics", "heath"],
    "fireclay": ["fireclay"],
    "anthropologie": ["anthropologie"],
    "lulu-georgia": ["lulu and georgia", "lulu & georgia", "lulu georgia"],
    "loloi": ["loloi"],
    "westside-modern-atlanta": ["westside modern"],
    "city-issue-atlanta": ["city issue"],
    "mid-mod-market-atlanta": ["mid mod market", "midmodmarket"],
    "chairish": ["chairish"],
    "1stdibs": ["1stdibs"],
    "industry-west": ["industry west"],
    "interior-define": ["interior define"],
    "cb2": ["cb2"],
    "burrow": ["burrow"],
    "sundays": ["sundays"],
    "rh": ["rh", "restoration hardware"],
    "bosch": ["bosch"],
    "miele": ["miele"],
    "wolf": ["wolf"],
    "sub-zero": ["sub-zero", "sub zero"],
    "ge-cafe": ["ge cafe", "ge café"],
    "kitchenaid": ["kitchenaid"],
    "lg": ["lg"],
    "samsung": ["samsung"],
    "vent-a-hood": ["vent-a-hood", "vent a hood"],
    "emtek": ["emtek"],
    "rejuvenation-hardware": ["rejuvenation"],
    "schoolhouse-hardware": ["schoolhouse"],
    "top-knobs": ["top knobs"],
    "hapny": ["hapny"],
    "baldwin": ["baldwin"],
    "phylrich": ["phylrich"],
    "brizo": ["brizo"],
    "hansgrohe": ["hansgrohe"],
    "perrin-rowe": ["perrin", "perrin rowe", "perrin and rowe"],
    "watermark-designs": ["watermark"],
    "signature-hardware": ["signature hardware"],
    "lewis-dolin": ["lewis dolin"],
    "house-of-antique-hardware": ["house of antique"],
    "hamilton-sinkler": ["hamilton sinkler"],
    "muuto": ["muuto"],
    "hay": ["hay"],
    "flos": ["flos"],
    "visual-comfort": ["visual comfort"],
    "lumens": ["lumens"],
    "allied-maker": ["allied maker"],
    "workstead": ["workstead"],
    "cedar-moss": ["cedar moss", "cedar & moss"],
    "fireclay-tile": ["fireclay"],
    "zia-tile": ["zia"],
    "clay-imports": ["clay imports"],
    "riad-tile": ["riad"],
    "bedrosians": ["bedrosians"],
    "floor-decor": ["floor & decor", "floor and decor"],
    "pratt-larson": ["pratt larson", "pratt & larson"],
    "parachute": ["parachute"],
    "nestig": ["nestig"],
    "armadillo": ["armadillo"],
    "revival-rugs": ["revival"],
    "beni-rugs": ["beni"],
    "tigmi-trading": ["tigmi"],
    "lawrence-of-labrea": ["lawrence of la brea", "lawrence of labrea"],
    "abc-carpet-home": ["abc carpet"],
    "etsy-curated": ["etsy"],
    "saatchi-art": ["saatchi"],
    "artfully-walls": ["artfully walls"],
    "minted": ["minted"],
    "tappan-collective": ["tappan"],
    "cb2-decor": ["cb2"],
    "anthropologie-home": ["anthropologie"],
    "shade-store": ["shade store", "the shade store"],
    "smith-noble": ["smith & noble", "smith and noble", "smith noble"],
    "hunter-douglas": ["hunter douglas"],
    "tonic-living": ["tonic living"],
    "ikea-window": ["ikea"],
    "gloster": ["gloster"],
    "tropitone": ["tropitone"],
    "terrain": ["terrain"],
    "bauer-pottery": ["bauer pottery"],
    "campania-planters": ["campania"],
    "caesarstone": ["caesarstone"],
    "silestone": ["silestone"],
    "cambria": ["cambria"],
    "dekton-cosentino": ["dekton", "cosentino"],
    "msi-surfaces": ["msi"],
    "concreteworks": ["concreteworks"],
    "natural-stone-source": ["natural stone source"],
    "semihandmade": ["semihandmade"],
    "reform": ["reform"],
    "plain-english": ["plain english"],
    "cabinetnow-custom": ["cabinetnow"],
    "portola-paints": ["portola"],
    "backdrop": ["backdrop"],
    "clare": ["clare"],
    "dunn-edwards": ["dunn edwards", "dunn-edwards"],
    "best-hoods": ["best", "best hoods"],
}


def _normalize_vendor_name(s):
    if not s:
        return ""
    return _VENDOR_NAME_NOISE.sub(" ", s.lower()).strip()


def _vendor_string_matches_supplier(vendor_str: str, supplier_id: str, supplier_name: str) -> bool:
    """Return True if a sourcing.yaml vendor string matches the given supplier.

    Strategy: build a list of candidate tokens from (supplier_id, supplier_name, alias_map),
    then check substring match (whole-word, case-insensitive) against the normalized vendor string.
    """
    if not vendor_str:
        return False
    norm = _normalize_vendor_name(vendor_str)
    # Build candidate aliases. Strip category suffix from supplier id (e.g. west-elm-seating → west-elm).
    base = supplier_id
    for suf in ("-seating", "-tables", "-bedroom", "-lighting", "-appliances",
                "-outdoor", "-decor", "-window", "-bedding", "-hardware"):
        if base.endswith(suf):
            base = base[: -len(suf)]
    candidates = set()
    # alias map keyed by full id and by base
    for key in (supplier_id, base):
        for alias in _VENDOR_ALIAS_MAP.get(key, []):
            candidates.add(alias)
    # Always include the supplier name itself, lowercased.
    if supplier_name:
        candidates.add(supplier_name.lower())
        candidates.add(_normalize_vendor_name(supplier_name))
    # And the base id dehyphenated.
    candidates.add(base.replace("-", " "))
    candidates.discard("")
    for c in candidates:
        cnorm = _normalize_vendor_name(c)
        if not cnorm:
            continue
        # whole-word match — boundaries are spaces in the normalized string
        if cnorm == norm:
            return True
        if (" " + cnorm + " ") in (" " + norm + " "):
            return True
    return False


def _load_sourcing_for_cross_link():
    """Load sourcing.yaml items minimally (id + vendor strings + scope keys).

    R3 Fix C2 — also surface (title, category, room) so supplier cross-link
    counts can be category-scoped (see `_item_in_supplier_category_scope`).
    Returns list of dicts: {id, title, category, room, top_vendor,
    option_vendors}. Returns [] if file missing or unreadable — cross-link
    rendering degrades gracefully.
    """
    sourcing_yaml = Path.home() / "Desktop" / "HomeAI" / "scope" / "sourcing.yaml"
    if not sourcing_yaml.exists():
        return []
    try:
        raw = yaml.safe_load(sourcing_yaml.read_text())
    except Exception:
        return []
    out = []
    for it in (raw.get("items") or []):
        out.append({
            "id": it.get("id", ""),
            "title": it.get("title", "") or "",
            "category": it.get("category", "") or "",
            "room": it.get("room", "") or "",
            "top_vendor": it.get("vendor") or "",
            "option_vendors": [
                (o or {}).get("vendor", "")
                for o in (it.get("options") or [])
            ],
        })
    return out


#
# R3 Fix C2 — supplier-category scoping for /suppliers cross-link counts.
#
# Each supplier-directory category maps to a predicate over a sourcing.yaml
# item: the (sourcing-item category, sourcing-item room, sourcing-item
# title) tuple. A supplier only counts a sourcing item if it both
# brand-matches AND falls inside its category's scope.
#
# Supplier-directory category vocabulary (15):
#   furniture-seating, furniture-tables, furniture-bedroom,
#   lighting, tile, plumbing, hardware, paint, cabinetry,
#   counters, appliances, rugs, decor-art, window-treatments, outdoor
#
# Mapping rules:
#  - Each entry maps to a dict with:
#      "categories": set of sourcing item categories that are ALWAYS in scope
#      "title_keywords": iterable of title substrings (case-insensitive) — when present, item is in scope
#      "title_excludes": iterable of substrings that disqualify an item even if category matches
#      "rooms": optional set of sourcing item rooms — when set, item room MUST be in this set
# If a sourcing item matches by category OR by title_keyword and is NOT in title_excludes (and room
# matches when rooms is set), it counts.
#
# A supplier whose id has no recognized category-suffix (or whose
# supplier-directory category is missing from this map) falls through to
# the legacy brand-only match (no scoping).
#
_SUPPLIER_CATEGORY_SCOPE = {
    "furniture-seating": {
        "title_keywords": (
            "sofa", "sectional", "chair", "bench", "glider", "stool",
            "loveseat", "ottoman", "armchair", "settee",
        ),
        "title_excludes": ("dining chair", "dining-chair"),  # dining chairs go w/ tables
        "categories": set(),
    },
    "furniture-tables": {
        "title_keywords": (
            "table", "desk", "sideboard", "credenza", "console",
            "buffet", "dining chair", "dining chairs",
        ),
        "title_excludes": (),
        "categories": set(),
    },
    "furniture-bedroom": {
        "title_keywords": (
            "bed ", "bed,", "bedframe", "headboard", "nightstand",
            "dresser", "crib", "wardrobe", "armoire", "chifforobe",
        ),
        "title_excludes": ("bed bench", "bedding"),
        "categories": set(),
        # Bedrooms / nursery only.
        "rooms": {"master_br", "nursery", "guest_br"},
    },
    "lighting": {
        "categories": {"lighting_fixture"},
        "title_keywords": (),
        "title_excludes": (),
    },
    "tile": {
        "categories": {"tile_stone"},
        "title_keywords": (),
        "title_excludes": ("counter", "vanity-top"),
    },
    "plumbing": {
        "categories": {"plumbing_fixture"},
        "title_keywords": (),
        "title_excludes": (),
    },
    "hardware": {
        "categories": {"hardware"},
        "title_keywords": (),
        "title_excludes": (),
    },
    "paint": {
        "categories": {"paint_finish"},
        "title_keywords": (),
        "title_excludes": (),
    },
    "cabinetry": {
        "categories": {"cabinetry_millwork"},
        "title_keywords": (),
        "title_excludes": (),
    },
    "counters": {
        "categories": set(),
        "title_keywords": ("counter", "counters", "vanity-top", "countertop"),
        "title_excludes": (),
    },
    "appliances": {
        "categories": {"appliance"},
        "title_keywords": (),
        "title_excludes": (),
    },
    "rugs": {
        "categories": set(),
        "title_keywords": ("rug",),
        "title_excludes": (),
    },
    "decor-art": {
        "categories": {"decor_softgoods"},
        "title_keywords": ("mirror", "art", "ceramic", "pillow", "throw", "vase"),
        "title_excludes": ("rug",),
    },
    "window-treatments": {
        "categories": {"window_treatment"},
        "title_keywords": (),
        "title_excludes": (),
    },
    "outdoor": {
        "categories": set(),
        "title_keywords": ("outdoor", "deck", "patio"),
        "title_excludes": (),
        # Outdoor scope: only exterior or items with explicit outdoor in title.
    },
}


def _item_in_supplier_category_scope(item: dict, supplier_category: str) -> bool:
    """Return True when the sourcing item is in-scope for the supplier's
    directory category. Falls through to True (no scoping) for suppliers
    whose directory category isn't in the map (e.g. legacy / unknown).
    """
    scope = _SUPPLIER_CATEGORY_SCOPE.get(supplier_category)
    if scope is None:
        # No scope rule for this supplier category — brand-only match preserved.
        return True
    title = (item.get("title") or "").lower()
    cat = item.get("category") or ""
    room = item.get("room") or ""

    # Room gate (only relevant for furniture-bedroom right now).
    if "rooms" in scope and scope["rooms"]:
        if room and room not in scope["rooms"]:
            return False

    # Hard category match.
    if cat in scope["categories"]:
        # Apply title_excludes even on category match (so e.g. furniture-bedroom
        # never accepts a "bedding" item even if the item is in furniture).
        for kw in scope["title_excludes"]:
            if kw in title:
                return False
        return True

    # Title-keyword fallback (for furniture subcategories etc.).
    if scope["title_keywords"]:
        for kw in scope["title_keywords"]:
            if kw in title:
                # Title hits — but make sure no exclude triggers.
                for ex in scope["title_excludes"]:
                    if ex in title:
                        return False
                return True

    return False


def _supplier_sourcing_links(supplier_id: str, supplier_name: str,
                              sourcing_items: list,
                              supplier_category: Optional[str] = None) -> List[str]:
    """Return list of sourcing item IDs that reference this supplier
    (top vendor or option vendor), scoped by supplier_category.

    R3 Fix C2 — Previously the function matched on brand alone, which caused
    every WE-* sub-supplier (seating / tables / bedroom) to count all 35 WE
    items. The supplier_category arg + the per-category scope rules above
    fix the bleed: WE-bedroom now only counts bedroom-room furniture items,
    WE-seating only counts seating-title furniture items, etc.

    When `supplier_category` is None, the legacy brand-only behavior is
    preserved for back-compat.
    """
    matches = []
    for it in sourcing_items:
        # Brand-match first (cheap).
        brand_matched = False
        if _vendor_string_matches_supplier(it["top_vendor"], supplier_id, supplier_name):
            brand_matched = True
        else:
            for ov in it["option_vendors"]:
                if _vendor_string_matches_supplier(ov, supplier_id, supplier_name):
                    brand_matched = True
                    break
        if not brand_matched:
            continue
        # Category scope (R3 Fix C2).
        if supplier_category is None:
            matches.append(it["id"])
        elif _item_in_supplier_category_scope(it, supplier_category):
            matches.append(it["id"])
    return matches


_SAFE_HREF_SCHEMES = ("http://", "https://", "mailto:")


def _safe_href(url) -> str:
    """R2 Fix C1 — scheme-sanitize external URLs before rendering as href.

    Codex flagged that yaml-sourced URLs are HTML-escaped but not scheme-validated:
    a malicious `javascript:` URL in supplier_directory.yaml would render as a
    clickable link. Return the URL unchanged (HTML-escaped by caller) if it's
    a recognized safe scheme; otherwise return "#" so the link is inert.

    R3 Fix C3 — explicitly reject scheme-relative URLs (`//evil.com`). They
    are protocol-relative and would inherit the current page scheme, which
    we treat as untrusted external. Return "#" for them.
    """
    if url is None:
        return "#"
    s = str(url).strip()
    if not s:
        return "#"
    # R3 Fix C3 — reject scheme-relative URLs (e.g. //evil.com) BEFORE the
    # "starts with /" internal-path check below.
    if s.startswith("//"):
        return "#"
    lower = s.lower()
    for scheme in _SAFE_HREF_SCHEMES:
        if lower.startswith(scheme):
            return s
    # Internal-relative paths (e.g. "/sourcing", "#anchor") are safe.
    if s.startswith("/") or s.startswith("#"):
        return s
    return "#"


def _supplier_fit_pill(fit: str) -> str:
    """Return HTML pill for fit category."""
    cls_map = {
        "STRONG": "fit-strong",
        "GOOD": "fit-good",
        "MIXED": "fit-mixed",
        "CANON-ADJACENT": "fit-canon-adjacent",
    }
    cls = cls_map.get(fit, "fit-mixed")
    return f'<span class="supplier-pill {cls}">{escape(fit)}</span>'


def _supplier_tier_pill(tier: str) -> str:
    cls = f"tier-{tier}"
    return f'<span class="supplier-pill {cls}">{escape(tier)}</span>'


# Fit-pill mapping, hoisted so the merged tier·fit pill (R5-UX5) can reuse it.
_FIT_PILL_CLASS_MAP = {
    "STRONG": "fit-strong",
    "GOOD": "fit-good",
    "MIXED": "fit-mixed",
    "CANON-ADJACENT": "fit-canon-adjacent",
}


def _supplier_tier_fit_merged_pill(tier: str, fit: str) -> str:
    """R5-UX5 — spec-strip consolidation: render tier and fit as a single
    merged pill ("Mid . STRONG") instead of two separate pills.

    DESIGN_SPEC section 4 principle 1 caps visible elements at 5-7 per
    surface. The R3 spec strip showed 6 elements (name + verif-badge +
    tier-pill + fit-pill + price-range + hero-badge). Merging tier and fit
    into one pill drops the visible-element count to 5 — comfortably inside
    the envelope and giving each remaining signal more breathing room.

    Visual treatment: the merged pill keeps the FIT background/foreground
    (the load-bearing canon signal) and embeds the tier as a quieter prefix.
    Operators can still scan tier via the first token; the fit pill's color
    code (green/cream/lavender) remains unchanged.
    """
    fit_cls = _FIT_PILL_CLASS_MAP.get(fit, "fit-mixed")
    tier_label = escape((tier or "mid").capitalize())
    fit_label = escape(fit or "MIXED")
    return (
        f'<span class="supplier-pill supplier-pill-merged {fit_cls}" '
        f'data-tier="{escape(tier or "mid")}" data-fit="{escape(fit or "MIXED")}">'
        f'<span class="merged-tier">{tier_label}</span>'
        f'<span class="merged-sep" aria-hidden="true"> &middot; </span>'
        f'<span class="merged-fit">{fit_label}</span>'
        f'</span>'
    )


_FIT_PREFIX_RE = None


def _strip_redundant_fit_prefix(text) -> str:
    """R3 Fix UX5 — strip leading 'STRONG — ' / 'GOOD — ' / 'MIXED — '
    / 'CANON-ADJACENT — ' prefix from fit_for_project at render time.

    The fit pill (top of card) already conveys the category; the prose
    line beneath restated it on 131 of 135 cards. Strip at render time so
    yaml stays editable and the prose reads as a sentence.
    """
    if not text:
        return ""
    s = str(text)
    import re as _re
    global _FIT_PREFIX_RE
    if _FIT_PREFIX_RE is None:
        # Match optional whitespace + label + dash/em-dash/hyphen + optional whitespace.
        _FIT_PREFIX_RE = _re.compile(
            r"^\s*(?:STRONG|GOOD|MIXED|CANON-ADJACENT|WATCH_LIST)\s*[—–\-]+\s*",
            _re.IGNORECASE,
        )
    stripped = _FIT_PREFIX_RE.sub("", s, count=1)
    # Capitalize the first letter if stripping leaves lowercase mid-sentence.
    if stripped and stripped[0].islower():
        stripped = stripped[0].upper() + stripped[1:]
    return stripped


def _sanitize_brackets_for_display(text) -> str:
    """R2 Fix UX3 — Strip/escape bracket sequences that could be interpreted as
    Markdown link syntax or that contain operator-marker placeholders like
    `[OWNER CONFIRM`. Browsers don't render [foo] as a link in plain HTML
    (markdown isn't involved here) but the YAML has unbalanced opening
    brackets (`Performance fabric upgrade per §7 [OWNER CONFIRM`) that look
    truncated to users. We:
      1. Replace `[OWNER CONFIRM ...` and similar in-flight operator markers
         with an em-dash so the sentence reads naturally.
      2. Pass everything else through unchanged (HTML escaping is applied by
         the caller).
    """
    if not text:
        return ""
    s = str(text)
    # Collapse "[OWNER CONFIRM ...]" or "[OWNER CONFIRM ..." (unclosed) into "".
    # The closing bracket may be missing in source data — drop everything from
    # the marker to either the next ']' or end of string.
    import re as _re
    s = _re.sub(r"\[OWNER CONFIRM[^\]]*\]?", "", s, flags=_re.IGNORECASE)
    # Same treatment for "[OWNER" / "[OPERATOR" / "[TODO" patterns.
    s = _re.sub(r"\[(?:OPERATOR|TODO)[^\]]*\]?", "", s, flags=_re.IGNORECASE)
    # Tidy up double-spaces left behind.
    s = _re.sub(r"\s+", " ", s).strip()
    return s


# R2 Fix UX5 — visual-class classifier for hero images. Three classes:
#   📷 photo: real product / PDP shot from brand CDN
#   🏷 logo: brand-mark / logo banner
#   📋 placeholder: text-on-color generated fallback
_LOGO_FILENAME_HINTS = ("logo", "wordmark", "branding", "_logo", "-logo", "_brand")

# R4 Fix I4 — hero_image is yaml-sourced and previously joined to SITE_DIR
# after only an lstrip("/"), with no normalization or root-check. A
# malicious entry like `../../etc/passwd` or `/../../tmp/x.png` could
# escape to other parts of the filesystem (read-side: disk_path.exists()
# checks, RTL: the rendered <img src=...> would leak the path back to
# browsers). The renderer locks all hero_image paths to the canonical
# images/suppliers/ subtree.
_HERO_IMAGE_ROOT_REL = "images/suppliers"


def _safe_hero_image_path(hero_path):
    """R4 Fix I4 — return the canonical site-relative path for a yaml-sourced
    hero_image string, or None if it's malformed / outside the
    images/suppliers/ subtree.

    Reject:
      - empty / non-string input
      - paths containing '..' segments (path-traversal)
      - paths that don't resolve under SITE_DIR/images/suppliers/

    Accept and return the normalized site-relative string (always starts
    with 'images/suppliers/'). Callers can build a URL by prepending '/'.
    """
    if not hero_path or not isinstance(hero_path, str):
        return None
    rel = hero_path.lstrip("/").strip()
    if not rel:
        return None
    # Reject any '..' parent-traversal segments BEFORE normalization to
    # close the door on dotted-segment escapes (Path('a/../b').parts will
    # not contain '..' but the input string carrying '..' is the signal we
    # need to reject malicious YAML).
    parts = rel.split("/")
    if any(p == ".." for p in parts):
        return None
    # Build the absolute candidate and ensure it stays under the canonical
    # images/suppliers/ subtree of SITE_DIR after normalization. We use
    # os.path.normpath to collapse any . segments and then compare relative
    # to the resolved hero root.
    import os as _os
    hero_root = (SITE_DIR / _HERO_IMAGE_ROOT_REL).resolve()
    try:
        candidate = (SITE_DIR / rel).resolve()
    except (OSError, ValueError):
        return None
    try:
        candidate.relative_to(hero_root)
    except ValueError:
        return None
    # Return the canonical site-relative string (rel of SITE_DIR).
    try:
        site_rel = candidate.relative_to(SITE_DIR.resolve()).as_posix()
    except ValueError:
        return None
    return site_rel


# R5 Fix I2 — supplier hero <img> tags previously emitted only src/alt/loading,
# so the browser reserved 0x0 until the image loaded — CLS on slow connections.
# Reading the real on-disk dimensions via PIL at build time gives the browser
# the correct aspect ratio for layout reservation. The CSS still controls the
# rendered size (.supplier-hero img { width:100%; height:100%; object-fit:cover }),
# so the intrinsic attrs only feed the aspect-ratio reservation.
_HERO_FALLBACK_W = 400
_HERO_FALLBACK_H = 240


def _hero_image_dimensions(disk_path):
    """Return (width, height) of the on-disk image, or fallback dimensions if
    PIL is unavailable or the file can't be read. Best-effort: never raises.
    """
    try:
        from PIL import Image  # type: ignore
    except ImportError:
        return (_HERO_FALLBACK_W, _HERO_FALLBACK_H)
    try:
        with Image.open(disk_path) as im:
            w, h = im.size
            if w > 0 and h > 0:
                return (int(w), int(h))
    except Exception:
        pass
    return (_HERO_FALLBACK_W, _HERO_FALLBACK_H)


def _is_real_image_on_disk(hero_path: str) -> bool:
    """Return True when hero_image points to a real on-disk image file that
    is NOT an HTML-as-image error page and is non-trivial (>1KB by default).

    R3 Fix UX1 — used by `_hero_visual_class()` to default to "photo" when a
    real product image is on disk, even if YAML lacks `hero_image_source*`.

    Heuristic boundaries:
      - <1KB: tiny stub / empty placeholder — reject (real product photos
        run from ~5KB upward; the previously-stub .png "files" were 9-22 bytes)
      - Starts with `<!doctype` / `<html` / contains `<head>` in first 200
        bytes: HTML masquerading as image (schoolhouse.jpg was a 1.1MB
        403 page). Reject.
    """
    if not hero_path:
        return False
    # R4 Fix I4 — validate path is under images/suppliers/ before touching
    # disk. Out-of-scope paths fall straight through to "not real".
    safe_rel = _safe_hero_image_path(hero_path)
    if not safe_rel:
        return False
    disk_path = SITE_DIR / safe_rel
    try:
        if not disk_path.exists() or not disk_path.is_file():
            return False
        size = disk_path.stat().st_size
        if size < 1024:  # < 1KB: tiny stub / empty placeholder
            return False
        # Defensive sniff: HTML-as-jpg leaks (schoolhouse.jpg was a 1.1MB
        # HTML 403/404 page). Read the first few bytes and reject obvious
        # HTML signatures.
        with open(disk_path, "rb") as f:
            head = f.read(256)
        if not head:
            return False
        # Lowercased ASCII first 200 bytes — easy markers.
        low = head[:200].lower()
        if low.startswith(b"<!doctype") or low.startswith(b"<html") or b"<head>" in low:
            return False
        return True
    except (OSError, ValueError):
        return False


def _hero_visual_class(sup: dict) -> str:
    """Return one of 'photo', 'logo', 'placeholder', 'broken' based on YAML
    hero_image_source tag, filename heuristics, AND the actual file on disk.

    R3 Fix UX1 — when YAML is silent (no hero_image_source / hero_image_source_url),
    fall back to checking whether a real image is on disk. Previously we
    returned "placeholder" in that case, which lied to the user on the 11
    cards that had a real photo but no source-tag in yaml. Now:
      1. Explicit `hero_image_source: text_placeholder` → placeholder
      2. Explicit `real_brand_cdn` / `brand_pdp` → photo (or logo if filename hints)
      3. No explicit tag but file is on disk + non-trivial + not-HTML →
         logo if filename suggests so, else photo
      4. File missing → placeholder
      5. File present but is HTML-as-image (e.g. schoolhouse.jpg 403 page)
         → broken (rendered as placeholder-style badge with broken tooltip)
    """
    source_url = (sup.get("hero_image_source_url") or "").lower()
    hero_path = (sup.get("hero_image") or "").lower()
    # Explicit source-source tag from yaml takes precedence.
    explicit = (sup.get("hero_image_source") or "").lower()
    if explicit == "text_placeholder":
        return "placeholder"
    if explicit in ("real_brand_cdn", "brand_pdp"):
        # Still could be a logo banner — check filename for logo hints.
        if any(h in source_url for h in _LOGO_FILENAME_HINTS) or any(
            h in hero_path for h in _LOGO_FILENAME_HINTS
        ):
            return "logo"
        return "photo"
    # No explicit tag — infer.
    if not hero_path:
        return "placeholder"
    # Filename-hint classification takes precedence over disk-state so test
    # fixtures (no on-disk file) still classify correctly.
    is_logo_hint = (
        any(h in source_url for h in _LOGO_FILENAME_HINTS)
        or any(h in hero_path for h in _LOGO_FILENAME_HINTS)
    )
    # R3 Fix UX1 — disk-check: if file is missing, mark placeholder; if it's
    # an HTML-as-jpg error page (Claude flagged schoolhouse.jpg as 1.1MB HTML),
    # mark broken; otherwise inherit photo / logo classification.
    # R4 Fix I4 — validate path-traversal-safety before touching disk.
    safe_rel = _safe_hero_image_path(hero_path)
    if not safe_rel:
        # Out-of-scope hero_image is treated identically to a missing file
        # (preserve logo-hint classification, otherwise placeholder).
        if is_logo_hint:
            return "logo"
        if source_url:
            return "photo"
        return "placeholder"
    disk_path = SITE_DIR / safe_rel
    if not disk_path.exists():
        # File missing on disk; preserve logo classification when filename
        # clearly signals it (tests rely on filename-only logo detection).
        if is_logo_hint:
            return "logo"
        # Source URL exists but no on-disk file — treat as photo (preserves
        # R2 behavior for "had a source url, never saved to disk" pre-curation).
        if source_url:
            return "photo"
        return "placeholder"
    if not _is_real_image_on_disk(hero_path):
        # File exists but failed sanity (HTML / <1KB stub) — broken.
        return "broken"
    # Real on-disk image: classify logo vs photo by filename hints + source URL.
    if is_logo_hint:
        return "logo"
    # R3 Fix UX1: no source_url required — disk file existence implies real photo.
    return "photo"


def _hero_visual_badge_html(cls: str) -> str:
    """Small corner badge announcing what kind of image the hero is.

    R3 Fix UX1 — adds 'broken' class for hero files that exist on disk but
    failed sanity (HTML-as-jpg, sub-30KB stubs). Distinguishes "no image"
    (placeholder) from "image is wrong on disk" (broken).
    """
    if cls == "photo":
        return (
            '<span class="hero-class-badge hero-class-photo" '
            'title="Product photo from brand CDN" aria-label="Product photo">'
            "&#128247;</span>"
        )
    if cls == "logo":
        return (
            '<span class="hero-class-badge hero-class-logo" '
            'title="Brand logo / banner" aria-label="Brand logo">'
            "&#127991;</span>"
        )
    if cls == "broken":
        return (
            '<span class="hero-class-badge hero-class-broken" '
            'title="Hero file failed sanity check (HTML-as-image or tiny stub) — needs re-fetch" '
            'aria-label="Broken hero image">&#9888;</span>'
        )
    return (
        '<span class="hero-class-badge hero-class-placeholder" '
        'title="Text placeholder — no real product image" '
        'aria-label="Placeholder image">&#128203;</span>'
    )


def _render_supplier_card(sup: dict, sourcing_match_ids: Optional[List[str]] = None,
                            verification_date: str = "") -> str:
    """Render a single supplier card with all rich detail.

    R2 layout (post-UX1 refactor):
      Default state (closed):
        - hero image with visual-class badge
        - compact spec strip: name + verif badge | tier + fit + price-range
        - 1-sentence style fingerprint
        - Explore button + tri-state action selector
      Expanded state (<details open>):
        - full fit_for_project justification
        - off-canon warning
        - collection chips
        - lead time + sample policy
        - notes
        - /sourcing cross-link

    Drops default density from ~14 elements to ~5; click-to-expand keeps the
    full detail available without a wall of text per card.
    """
    sid = sup.get("id", "")
    name = escape(sup.get("name", ""))
    # R2 Fix C1 — scheme-sanitize external URL before HTML-escaping.
    # R4 Fix I1 — track the sanitized result separately so we can suppress
    # the Explore CTA when _safe_href() rejected the URL (returns "#"),
    # instead of rendering a button that goes nowhere.
    safe_url = _safe_href(sup.get("url", ""))
    url = escape(safe_url)
    url_is_inert = safe_url == "#"
    tier = sup.get("price_tier", "mid")
    fit = sup.get("fit", "GOOD")
    # R2 Fix UX3 — sanitize bracket-truncation in source data (e.g. WE Notes
    # ending in "[OWNER CONFIRM" with no closing bracket).
    fingerprint = escape(_sanitize_brackets_for_display(sup.get("style_fingerprint", "")))
    # R3 Fix UX5 — strip "STRONG — " / "GOOD — " / "MIXED — " / "CANON-ADJACENT — "
    # prefix at render time so the prose line isn't redundant with the fit pill.
    fit_text = escape(_strip_redundant_fit_prefix(
        _sanitize_brackets_for_display(sup.get("fit_for_project", ""))
    ))
    warn_raw = _sanitize_brackets_for_display(sup.get("off_canon_warning"))
    sample_policy = sup.get("sample_policy")
    lead_time = sup.get("lead_time_typical")
    # R2 Fix UX4 — `operator_notes` is operator-internal and must NEVER render.
    # The schema's load_supplier_directory() already strips it, but defend
    # against direct-dict callers (tests) too.
    notes_raw = _sanitize_brackets_for_display(sup.get("notes"))
    hero_image = sup.get("hero_image") or ""
    url_verified = bool(sup.get("url_verified"))
    url_status = sup.get("url_status")
    price_validation = sup.get("price_validation") or []
    sourcing_match_ids = sourcing_match_ids or []

    # Collection chips (rendered inside expander)
    cols = sup.get("collections_to_browse") or []
    chips_html = ""
    if cols:
        chips = []
        for c in cols[:6]:
            cname = escape(_sanitize_brackets_for_display(c.get("name", "")))
            raw_curl = c.get("url") if isinstance(c, dict) else None
            curl = escape(_safe_href(raw_curl)) if raw_curl else url
            chips.append(
                f'<a class="collection-chip" href="{curl}" target="_blank" rel="noopener">{cname}</a>'
            )
        chips_html = f'<div class="collections">{"".join(chips)}</div>'

    # Price-range block — compact single line in the spec strip + fuller version
    # in the expander.
    pr = sup.get("price_range_typical") or {}
    pr_compact = ""
    pr_full_html = ""
    if pr:
        # Compact: just the lowest / highest range observed for the spec strip.
        try:
            pr_compact = next(iter(pr.values()))
            pr_compact = f"${escape(str(pr_compact))}"
        except StopIteration:
            pr_compact = ""
        pr_lines = []
        for k, v in pr.items():
            label = k.replace("_", " ")
            pr_lines.append(f"{escape(label)}: ${escape(str(v))}")
        pr_full_html = (
            f'<div class="footer-line"><strong>Price</strong>'
            f'{escape(" · ".join(pr_lines))}</div>'
        ) if pr_lines else ""

    # Lead / sample footer (expander only)
    lead_sample_parts = []
    if lead_time:
        lead_sample_parts.append(f"<strong>Lead</strong>{escape(str(lead_time))}")
    if sample_policy:
        lead_sample_parts.append(f"<strong>Samples</strong>{escape(str(sample_policy))}")
    lead_sample_html = ""
    if lead_sample_parts:
        lead_sample_html = (
            f'<div class="footer-line">{" · ".join(lead_sample_parts)}</div>'
        )

    warn_html = ""
    if warn_raw:
        warn_html = f'<div class="warning-line">&#9888; {escape(warn_raw)}</div>'

    notes_html = ""
    if notes_raw:
        notes_html = f'<div class="footer-line"><strong>Notes</strong>{escape(notes_raw)}</div>'

    fit_line_html = (
        f'<p class="fit-line">{fit_text}</p>'
        if fit_text else ""
    )

    # Searchable haystack
    haystack_bits = [
        sup.get("name", ""),
        sup.get("style_fingerprint", ""),
        sup.get("fit_for_project", ""),
        sup.get("off_canon_warning") or "",
        sup.get("notes") or "",
    ]
    for c in cols:
        haystack_bits.append(c.get("name", "") if isinstance(c, dict) else "")
    haystack = " ".join(haystack_bits).lower()
    haystack_attr = escape(haystack)

    # Hero with visual-class badge
    visual_cls = _hero_visual_class(sup)
    visual_badge_html = _hero_visual_badge_html(visual_cls)
    hero_html = ""
    if hero_image and visual_cls != "broken":
        # R4 Fix I4 — only render <img> when the hero_image path resolves
        # inside SITE_DIR/images/suppliers/. Malicious YAML can't escape to
        # other site directories or leak host paths via path traversal.
        safe_rel = _safe_hero_image_path(hero_image)
        if safe_rel:
            disk_path = SITE_DIR / safe_rel
            if disk_path.exists():
                # Render the canonical site-relative path with a leading slash
                # (matches existing yaml convention `/images/suppliers/...`).
                hero_src = "/" + safe_rel
                # R5 Fix I2 — intrinsic width/height let the browser reserve
                # aspect-ratio-correct space before the image loads, avoiding
                # CLS on slow connections. CSS still drives the rendered size.
                hero_w, hero_h = _hero_image_dimensions(disk_path)
                hero_html = (
                    f'<div class="supplier-hero" data-hero-class="{visual_cls}">'
                    f'<img src="{escape(hero_src)}" alt="{name}" '
                    f'width="{hero_w}" height="{hero_h}" loading="lazy">'
                    f'{visual_badge_html}'
                    f'</div>'
                )
    if not hero_html:
        # R3 Fix UX1 — broken hero (HTML-as-jpg etc.) falls back to a
        # placeholder-style block but keeps the BROKEN badge so the operator
        # can see which suppliers need a re-fetch.
        fallback_cls = "broken" if visual_cls == "broken" else "placeholder"
        hero_html = (
            f'<div class="supplier-hero supplier-hero-placeholder" data-hero-class="{fallback_cls}">'
            f'<span>{name}</span>'
            f'{_hero_visual_badge_html(fallback_cls)}'
            f'</div>'
        )

    # Verification badge — R2 Fix UX6: focus-visible + role + tabindex + aria-describedby
    # so touch / keyboard users can read the tooltip.
    tooltip_id = f"verif-tip-{escape(sid) or 'x'}"
    if url_verified:
        verif_label = f"&#10003; Verified {escape(verification_date or '2026-05-17')}"
        verif_cls = "verif-ok"
        verif_tip = (
            f"URL status: {escape(str(url_status))} · "
            f"{len(price_validation)} price probe(s) · "
            f"verified {escape(verification_date or '2026-05-17')}"
        )
    else:
        verif_label = "&#9888; Unverified"
        verif_cls = "verif-warn"
        verif_tip = "URL not verified in last pass"
    verif_html = (
        f'<button type="button" class="verif-badge {verif_cls}" '
        f'role="button" tabindex="0" '
        f'aria-label="Verification status: {verif_tip}" '
        f'aria-describedby="{tooltip_id}" '
        f'data-tooltip="{verif_tip}">{verif_label}'
        f'<span role="tooltip" id="{tooltip_id}" class="verif-tooltip">{verif_tip}</span>'
        f'</button>'
    )

    # /sourcing cross-link (in expander) — keep the count headline, drop the
    # raw-id token dump that Claude flagged as zero-signal.
    if sourcing_match_ids:
        match_count = len(sourcing_match_ids)
        cross_html = (
            f'<div class="sourcing-crosslink has-matches">'
            f'<a href="/sourcing?vendor={escape(sid)}" class="crosslink-line">'
            f'&#128230; Tracked in /sourcing: <strong>{match_count}</strong> '
            f'item{"s" if match_count != 1 else ""} &rarr;'
            f'</a></div>'
        )
    else:
        cross_html = (
            f'<div class="sourcing-crosslink no-matches">'
            f'&#128235; Not yet tracked'
            f'</div>'
        )

    # Tri-state action selector — R3 Fix UX4: rendered OUTSIDE the expander.
    # R3 Fix UX6 — `role="radio"` + `aria-checked="false"` on each button so
    # the `role="radiogroup"` container is no longer a lie. JS handler in
    # SUPPLIERS_JS wires arrow-key navigation + updates aria-checked.
    # R5 Fix I4 — the FIRST radio in each card gets `tabindex="0"` server-side
    # so keyboard users tabbing through the page before JS loads can still
    # enter the radiogroup. JS reapplies the roving tabindex on load
    # (applyActionToCard), so any previously-saved state still wins.
    action_html = (
        f'<div class="supplier-action" role="radiogroup" aria-label="Action for {name}">'
        f'<button type="button" class="action-btn action-visit" data-action="visit" '
        f'role="radio" aria-checked="false" tabindex="0" '
        f'aria-label="Mark to visit">&#128270; Visit</button>'
        f'<button type="button" class="action-btn action-saved" data-action="saved" '
        f'role="radio" aria-checked="false" tabindex="-1" '
        f'aria-label="Save">&#11088; Saved</button>'
        f'<button type="button" class="action-btn action-ruled" data-action="ruled" '
        f'role="radio" aria-checked="false" tabindex="-1" '
        f'aria-label="Rule out">&#128683; Ruled out</button>'
        f'</div>'
    )

    # Compact spec strip — single horizontal row of identity signals beneath the hero.
    pr_compact_html = (
        f'<span class="spec-price">{pr_compact}</span>' if pr_compact else ""
    )
    # R5-UX5 — spec strip consolidation: tier + fit collapsed into a single
    # merged pill ("Mid · STRONG") so the visible-element count drops from 6
    # to 5, satisfying DESIGN_SPEC §4 principle 1 (5-7 elements per surface).
    spec_strip_html = (
        f'<div class="supplier-card-header">'
        f'<h3>{name}</h3>'
        f'{verif_html}'
        f'</div>'
        f'<div class="supplier-spec-strip">'
        f'{_supplier_tier_fit_merged_pill(tier, fit)}'
        f'{pr_compact_html}'
        f'</div>'
    )

    # Expander body — everything else EXCEPT action (R3 Fix UX4: action stays visible).
    expander_inner = "".join([
        fit_line_html,
        warn_html,
        chips_html,
        pr_full_html,
        lead_sample_html,
        notes_html,
        cross_html,
    ])
    # R5 Fix I3 — every supplier card previously used the same
    # "Details & collections" summary text, so screen readers couldn't
    # distinguish 126 identical-looking expanders. Make the summary
    # supplier-specific by prefixing the name.
    expander_html = (
        '<details class="supplier-details">'
        f'<summary>{name} &mdash; details &amp; collections</summary>'
        f'{expander_inner}'
        '</details>'
    ) if expander_inner else ""

    # R3 Fix UX4 — tri-state action selector rendered OUTSIDE the <details>
    # expander. Triage workflow ("mark each supplier visit/saved/ruled once")
    # was degraded in R2 because the buttons were behind a click. Moving them
    # back to always-visible restores 1-click-per-card triage.
    #
    # R4 Fix I1 — suppress the Explore CTA when _safe_href() rejected the URL
    # (returns "#"). Rendering a clickable button that goes nowhere is a UX
    # lie; a missing button signals "supplier has no usable external URL".
    if url_is_inert:
        explore_html = (
            f'<span class="explore-btn explore-btn-disabled" '
            f'aria-disabled="true" title="No external URL available for this supplier">'
            f'No site for {name}</span>'
        )
    else:
        explore_html = (
            f'<a class="explore-btn" href="{url}" target="_blank" rel="noopener">'
            f'Explore {name} &rarr;</a>'
        )
    return f'''<article class="supplier-card" data-supplier-id="{escape(sid)}" data-category="{escape(sup.get("category") or "")}" data-tier="{escape(tier)}" data-fit="{escape(fit)}" data-verified="{str(url_verified).lower()}" data-verified-date="{escape(verification_date or "")}" data-search="{haystack_attr}">
  {hero_html}
  {spec_strip_html}
  <p class="fingerprint">{fingerprint}</p>
  {action_html}
  {expander_html}
  {explore_html}
</article>'''


def render_suppliers_page(directory: Optional[dict] = None) -> str:
    """Render /suppliers — browse-style supplier discovery surface.

    Reads supplier_directory.yaml (or accepts pre-loaded dict). Shows category-grouped
    supplier cards with filters (search, category, price tier, fit) and a random-pick
    serendipity button. Designed for browsing, not for tracking decisions —
    /sourcing is the tracker, /vendors is the rollup, /suppliers is the map.
    """
    if directory is None:
        directory = _load_supplier_directory()
    if directory is None:
        # Defensive fallback if the YAML hasn't been generated yet.
        return f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="UTF-8"><title>Suppliers &middot; 1490 Lively Ridge</title>
<style>{SHARED_CSS}{SUPPLIERS_CSS}</style></head><body class="suppliers-page">
{SUPPLIERS_TOPNAV_HTML}
<main><div class="suppliers-empty">Supplier directory not yet generated. Run <code>build_sourcing.py</code> after creating <code>~/Desktop/HomeAI/scope/supplier_directory.yaml</code>.</div></main>
</body></html>
"""

    meta = directory.get("meta", {})
    categories = directory.get("categories", [])
    suppliers = directory.get("suppliers", [])
    verification_date = str(meta.get("last_verification_pass") or meta.get("generated") or "")

    # Load sourcing.yaml once for /sourcing cross-link counting
    sourcing_items = _load_sourcing_for_cross_link()

    # Pre-compute matches per supplier id (R3 Fix C2 — pass supplier_category
    # so cross-link counts are scoped, not brand-wide).
    matches_by_supplier: Dict[str, List[str]] = {}
    for s in suppliers:
        sid = s.get("id", "")
        matches_by_supplier[sid] = _supplier_sourcing_links(
            sid, s.get("name", ""), sourcing_items,
            supplier_category=s.get("category"),
        )

    # Group suppliers by category, in the canonical category order.
    # R2 Fix C7 — suppliers with missing or unknown categories were silently
    # dropped. Collect them into an "uncategorized" bucket rendered at the
    # bottom of the page so nothing disappears from the surface.
    by_cat: Dict[str, List[dict]] = {c["id"]: [] for c in categories}
    uncategorized: List[dict] = []
    for s in suppliers:
        cid = s.get("category")
        if cid in by_cat:
            by_cat[cid].append(s)
        else:
            uncategorized.append(s)

    # Side nav
    sidenav_html_parts = [f'<h4>Categories</h4>']
    for c in categories:
        n = len(by_cat.get(c["id"], []))
        sidenav_html_parts.append(
            f'<a href="#cat-{escape(c["id"])}">{escape(c["label"])}'
            f' <span class="count">({n})</span></a>'
        )
    if uncategorized:
        sidenav_html_parts.append(
            f'<a href="#cat-uncategorized">Uncategorized'
            f' <span class="count">({len(uncategorized)})</span></a>'
        )
    sidenav_html = "\n".join(sidenav_html_parts)

    # Filter bar: search + 3 selects + sort + action chips + reset + random + copy URL
    cat_options = "".join(
        f'<option value="{escape(c["id"])}">{escape(c["label"])}</option>'
        for c in categories
    )
    # R3 Fix UX3 — wrap filter bar in a <details class="mobile-filters">.
    # On desktop, CSS forces the details panel open + hides summary; on
    # mobile (≤720px), the summary becomes a tap-target and the panel
    # collapses by default. Closes Claude's "dead CSS" critical.
    filter_bar_html = f'''<details class="mobile-filters">
<summary class="mobile-filters-summary"><span>Filters</span><span class="mobile-filters-chevron" aria-hidden="true">▾</span></summary>
<div class="suppliers-filter-bar">
  <!-- R4 Fix I5 — <label for=...> matched to each control id so screen
       readers announce the label when the field gains focus. -->
  <label for="supplier-search">Search</label>
  <input id="supplier-search" type="search" placeholder="Brand, style, finish..." autocomplete="off">
  <label for="cat-filter">Category</label>
  <select id="cat-filter">
    <option value="">All categories</option>
    {cat_options}
  </select>
  <label for="tier-filter">Tier</label>
  <select id="tier-filter">
    <option value="">All tiers</option>
    <option value="entry">Entry</option>
    <option value="mid">Mid</option>
    <option value="premium">Premium</option>
    <option value="aspirational">Aspirational</option>
  </select>
  <label for="fit-filter">Fit</label>
  <select id="fit-filter">
    <option value="">All fits</option>
    <option value="STRONG">Strong</option>
    <option value="GOOD">Good</option>
    <option value="MIXED">Mixed</option>
    <option value="CANON-ADJACENT">Canon-adjacent</option>
  </select>
  <label for="sort-by">Sort</label>
  <select id="sort-by">
    <option value="category">Category (default)</option>
    <option value="tier">Price tier &uarr;</option>
    <option value="fit">Fit (STRONG first)</option>
    <option value="verified">Recently verified</option>
    <option value="random">Random</option>
  </select>
  <span class="action-filter" role="group" aria-label="Filter by action">
    <button type="button" data-action-filter="all" class="active">All</button>
    <button type="button" data-action-filter="visit">&#128270; Visit</button>
    <button type="button" data-action-filter="saved">&#11088; Saved</button>
    <button type="button" data-action-filter="ruled">&#128683; Ruled</button>
    <button type="button" data-action-filter="unrated">&#9711; Unrated</button>
  </span>
  <label class="suppliers-ruled-toggle" title="Default: hide cards marked as Ruled out">
    <input type="checkbox" id="hide-ruled-toggle" checked>
    Hide ruled-out
  </label>
  <button id="reset-filters" type="button">Reset</button>
  <button id="random-pick" type="button" title="Pick a random visible supplier">&#127922; Random</button>
  <button id="copy-filter-url" type="button" title="Copy a sharable URL of the current filter state">Copy link</button>
  <span class="filter-stats" id="filter-stats"></span>
</div>
</details>
<div class="active-filter-pills" id="active-filter-pills" aria-live="polite"></div>
<div class="suppliers-empty-state" id="suppliers-empty-state">
  <p>No suppliers match the current filters.</p>
  <button id="empty-state-clear">Clear all filters</button>
</div>'''

    # Category sections
    sections_parts = []
    for c in categories:
        cid = c["id"]
        cat_suppliers = by_cat.get(cid, [])
        if not cat_suppliers:
            continue
        cards_html = "\n".join(
            _render_supplier_card(
                s,
                sourcing_match_ids=matches_by_supplier.get(s.get("id", ""), []),
                verification_date=verification_date,
            )
            for s in cat_suppliers
        )
        sections_parts.append(
            f'<section class="category-section" id="cat-{escape(cid)}">'
            f'<div class="category-section-header">'
            f'<h2>{escape(c["label"])}</h2>'
            f'<span class="cat-count">{len(cat_suppliers)} suppliers</span>'
            f'</div>'
            f'<div class="supplier-card-grid">{cards_html}</div>'
            f'</section>'
        )

    # R2 Fix C7 — uncategorized fallback section
    if uncategorized:
        unc_cards_html = "\n".join(
            _render_supplier_card(
                s,
                sourcing_match_ids=matches_by_supplier.get(s.get("id", ""), []),
                verification_date=verification_date,
            )
            for s in uncategorized
        )
        sections_parts.append(
            f'<section class="category-section category-uncategorized" id="cat-uncategorized">'
            f'<div class="category-section-header">'
            f'<h2>Uncategorized</h2>'
            f'<span class="cat-count">{len(uncategorized)} supplier(s) with unknown/missing category</span>'
            f'</div>'
            f'<div class="supplier-card-grid">{unc_cards_html}</div>'
            f'</section>'
        )

    sections_html = "\n".join(sections_parts)

    anchor_html = (
        f'<div class="suppliers-anchor-block">'
        f'<h3>Browse map</h3>'
        f'<p><strong>Aesthetic anchor:</strong> {escape(str(meta.get("aesthetic_anchor", "")))}</p>'
        f'<p><strong>Price tier:</strong> {escape(str(meta.get("project_price_tier", "")))} '
        f'against ${meta.get("cap_reference", 0):,} construction cap.</p>'
        f'<p><strong>Canon brand mix</strong> (DESIGN_SPEC &sect;5d): West Elm 35-40%, '
        f'Article / C&amp;B / R&amp;B 20-25%, Schoolhouse + Rejuvenation 15%, '
        f'Pottery Barn / Anthropologie / S&amp;L 8%, ferm LIVING / HAY / Muuto 3%, '
        f'Vintage 8-12%.</p>'
        f'<p><strong>Fit legend:</strong> '
        f'<span class="supplier-pill fit-strong">STRONG</span> explicit canon &middot; '
        f'<span class="supplier-pill fit-good">GOOD</span> canon-aligned &middot; '
        f'<span class="supplier-pill fit-mixed">MIXED</span> curate carefully &middot; '
        f'<span class="supplier-pill fit-canon-adjacent">CANON-ADJACENT</span> aspirational reference.</p>'
        f'</div>'
    )

    total_suppliers = len(suppliers)
    generated = escape(str(meta.get("generated", "")))

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Suppliers &middot; 1490 Lively Ridge</title>
<meta name="description" content="Browse-style supplier directory for 1490 Lively Ridge. {total_suppliers} suppliers across 15 categories matched to California Modern Japandi canon.">
<style>{SHARED_CSS}
{SUPPLIERS_CSS}</style>
</head>
<body class="suppliers-page">
{SUPPLIERS_TOPNAV_HTML}
<header class="page-header">
  <h1>Suppliers</h1>
  <p class="subtitle">{total_suppliers} suppliers across {len(categories)} categories. A map of where to look &mdash; not a tracker (that&rsquo;s /sourcing) and not a vendor rollup (that&rsquo;s /vendors). Generated {generated}.</p>
</header>
<main>
{anchor_html}
{filter_bar_html}
<div class="suppliers-page-layout">
  <aside class="category-side-nav">{sidenav_html}</aside>
  <div class="suppliers-content">
    {sections_html}
  </div>
</div>
</main>
{SUPPLIERS_JS}
</body>
</html>
"""
