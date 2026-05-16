# sourcing_render_html.py
"""Render sourcing data to a static HTML page styled to match /budget and /decisions.
Cards carry data-* attributes for client-side filtering (see filter UI in build_sourcing.py)."""
from typing import List, Optional, Dict
from html import escape

from sourcing_schema import Item, Meta
from sourcing_lint import LintFinding
from sourcing_queue import ScheduleLookup, T0_PHASES


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
}
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, "Inter", system-ui, sans-serif;
       background: var(--bg); color: var(--ink); line-height: 1.55; -webkit-font-smoothing: antialiased; }
nav.topnav { position: sticky; top: 0; z-index: 50; background: rgba(250, 248, 244, 0.96);
  border-bottom: 1px solid var(--border); backdrop-filter: blur(8px); }
.topnav-inner { max-width: 1200px; margin: 0 auto; padding: 11px 28px; display: flex;
  gap: 4px; flex-wrap: wrap; align-items: center; font-size: 13px; }
.topnav-inner .home { color: #6b6660; margin-right: 14px; font-weight: 600; text-decoration: none; }
.topnav-inner .home:hover { color: var(--accent); }
.topnav-inner .group-label { color: #6b6660; font-size: 11px; text-transform: uppercase;
  letter-spacing: 0.5px; margin: 0 4px 0 12px; font-weight: 600; }
.topnav-inner a:not(.home) { color: var(--ink); text-decoration: none; padding: 4px 10px;
  border-radius: 999px; border: 1px solid var(--border); }
.topnav-inner a:not(.home):hover { background: var(--card-bg); border-color: var(--accent); }
.topnav-inner a.current { background: var(--warm-tint); border-color: #c9b88a; }
.page-header { max-width: 1200px; margin: 36px auto 20px; padding: 0 28px; }
.page-header h1 { font-size: 30px; margin: 0 0 6px; font-weight: 600; letter-spacing: -0.5px; }
.page-header .subtitle { color: var(--muted); font-size: 15px; max-width: 760px; }
main { max-width: 1200px; margin: 0 auto; padding: 0 28px 80px; }
.lint-alert { background: #fff4d6; border: 1px solid #e9c97f; border-radius: 8px;
  padding: 12px 16px; margin: 16px 0; }
.lint-alert.lint-error { background: #fde8e6; border-color: #d99080; }
.lint-alert h4 { margin: 0 0 6px; font-size: 13px; text-transform: uppercase; letter-spacing: 0.6px; }
.lint-alert ul { margin: 0; padding-left: 18px; font-size: 13px; }
.schedule-not-locked { font-size: 11px; padding: 2px 8px; border-radius: 4px; background: #fef0d6;
  border: 1px solid #e9c97f; color: #6e4f1a; }
.revision-history { margin-top: 12px; padding-top: 8px; border-top: 1px dashed var(--border);
  font-size: 11.5px; color: var(--muted); }
.revision-history strong { color: var(--ink); margin-right: 6px; }
.filter-bar { display: flex; gap: 6px; flex-wrap: wrap; padding: 14px 0; border-bottom: 1px solid var(--border); margin-bottom: 24px; position: sticky; top: 44px; background: var(--bg); z-index: 40; }
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
.vintage-brief { background: #f3eedd; border-radius: 8px; padding: 12px; font-size: 13.5px; }
.vintage-brief strong { display: inline-block; min-width: 80px; }
.notes-line { font-size: 12.5px; color: var(--muted); font-style: italic; margin-top: 8px; }
"""


TOPNAV_HTML = """<nav class="topnav">
  <div class="topnav-inner">
    <a href="/" class="home">← 1490 Lively Ridge</a>
    <a href="/">Home</a><a href="/mood-board">Mood</a><a href="/spectrum">Spectrum</a><a href="/decisions">Decisions</a><a href="/budget">Budget</a><a href="/sourcing" class="current">Sourcing</a><a href="/spec">Spec</a>
    <span class="group-label">Rooms</span>
    <a href="/kitchen">Kitchen</a><a href="/master">Master</a><a href="/baths">Baths</a><a href="/lr">LR</a><a href="/nursery">Nursery</a><a href="/office">Office</a>
    <span class="group-label">Canon</span>
    <a href="/cathie-hong">Cathie Hong</a><a href="/owiu">OWIU</a><a href="/sss">SSS</a><a href="/jenni-kayne">Jenni Kayne</a>
    <a href="/materials">Materials</a><a href="/rejected">Rejected</a>
  </div>
</nav>"""


def _render_option(opt) -> str:
    star = '<span class="star">★</span> ' if opt.recommend else ""
    return f"""<div class="option-card {'recommend' if opt.recommend else ''}">
      <div class="vendor">{escape(opt.vendor)}</div>
      <div class="sku">{star}{escape(opt.sku)}</div>
      <div class="price">${opt.price_usd:,.0f}</div>
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


def _render_item_card(item: Item, schedule_lookup: Optional[ScheduleLookup] = None) -> str:
    badge_class, badge_text = STATUS_BADGE.get(item.decision_status, ("", item.decision_status))
    annika_flag = ' · 👩 Annika' if item.annika_loop else ''
    sample_flag = ' · ⚠️ sample required' if item.sample_required else ''
    sched_locked = _schedule_locked_for_item(item, schedule_lookup)
    sched_badge = '' if sched_locked else '<span class="schedule-not-locked">⚠️ schedule not locked</span>'
    body = ""

    if item.decided_sku:
        body = f'<div class="decided-line">✅ {escape(item.decided_sku)}</div>'
    elif item.vintage_brief:
        v = item.vintage_brief
        body = f'''<div class="vintage-brief">
          <div><strong>Style:</strong> {escape(v.style)}</div>
          <div><strong>Avoid:</strong> {escape(v.not_)}</div>
          <div><strong>Target $:</strong> {escape(v.target_price_usd)}</div>
          <div><strong>Hunt at:</strong> {escape(', '.join(v.hunt_venues))}</div>
        </div>'''
    elif item.options:
        body = '<div class="options-grid">' + "".join(_render_option(o) for o in item.options) + '</div>'

    notes_html = f'<div class="notes-line">{escape(item.notes)}</div>' if item.notes else ""

    history_html = _render_revision_history(item)

    return f"""<article class="item-card" data-id="{escape(item.id)}"
       data-urgency="{escape(item.urgency)}" data-room="{escape(item.room)}"
       data-category="{escape(item.category)}" data-status="{escape(item.decision_status)}"
       data-annika="{str(item.annika_loop).lower()}"
       data-schedule-locked="{str(sched_locked).lower()}">
      <div class="item-card-header">
        <span class="item-id">{escape(item.id)}</span>
        <h3>{escape(item.title)}</h3>
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
      {body}
      {notes_html}
      {history_html}
    </article>"""


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
        parts.append('<div class="lint-alert"><h4>Lint warnings ({})</h4><ul>{}</ul></div>'.format(
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
    return f"""<div class="filter-bar">
      <button data-filter="all" class="active">All</button>
      <button data-filter="decide-now">Decide this week</button>
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
    </div>"""


FILTER_JS = """
<script>
(function() {
  const cards = Array.from(document.querySelectorAll('.item-card'));
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
})();
</script>
"""


def render_site_page(items: List[Item], meta: Meta, lint_findings: List[LintFinding],
                     schedule_lookup: Optional[ScheduleLookup] = None) -> str:
    visible = [it for it in items if it.decision_status != "stub"]
    lint_html = _render_lint_alerts(lint_findings)
    cards_html = "\n".join(_render_item_card(it, schedule_lookup) for it in visible)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Sourcing · 1490 Lively Ridge</title>
<meta name="description" content="Sourcing tracker for every design-decision item — vendor, SKU, lead time, status. {len(visible)} items.">
<style>{SHARED_CSS}</style>
</head>
<body>
{TOPNAV_HTML}
<header class="page-header">
  <h1>Sourcing</h1>
  <p class="subtitle">Every design-decision item the renovation will consume. {len(visible)} items tracked. Updated {escape(meta.last_updated)}.</p>
</header>
<main>
{lint_html}
{_render_filter_bar()}
{cards_html}
</main>
{FILTER_JS}
</body>
</html>
"""
