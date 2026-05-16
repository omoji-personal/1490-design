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

@media (max-width: 720px) {
  .page-header h1 { font-size: 24px; }
  .topnav-inner { padding: 8px 14px; font-size: 12px; gap: 3px; }
  .topnav-inner .home { margin-right: 8px; }
  .topnav-inner a:not(.home) { padding: 3px 8px; font-size: 12px; }
  .topnav-inner .group-label { font-size: 10px; margin: 0 2px 0 8px; }
  .filter-bar { top: auto; position: static; flex-wrap: wrap; padding: 10px 0; }
  .filter-bar button, .filter-bar select { font-size: 12px; padding: 4px 10px; }
  .options-grid { grid-template-columns: 1fr; }
  .option-img-main { max-width: 100%; height: auto; max-height: 220px; }
  .item-card { padding: 12px; }
  main { padding: 0 14px 60px; }
  .page-header { padding: 0 14px; }
}
"""


TOPNAV_HTML = """<nav class="topnav">
  <div class="topnav-inner">
    <a href="/" class="home">← 1490 Lively Ridge</a>
    <a href="/">Home</a><a href="/mood-board">Mood</a><a href="/spectrum">Spectrum</a><a href="/decisions">Decisions</a><a href="/budget">Budget</a><a href="/sourcing" class="current">Sourcing</a><a href="/for-annika">Annika</a><a href="/spec">Spec</a>
    <span class="group-label">Rooms</span>
    <a href="/kitchen">Kitchen</a><a href="/master">Master</a><a href="/baths">Baths</a><a href="/lr">LR</a><a href="/nursery">Nursery</a><a href="/office">Office</a>
    <span class="group-label">Canon</span>
    <a href="/cathie-hong">Cathie Hong</a><a href="/owiu">OWIU</a><a href="/sss">SSS</a><a href="/jenni-kayne">Jenni Kayne</a>
    <a href="/materials">Materials</a><a href="/rejected">Rejected</a>
  </div>
</nav>"""


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
                      suppress_sched_badge: bool = False) -> str:
    badge_class, badge_text = STATUS_BADGE.get(item.decision_status, ("", item.decision_status))
    annika_flag = ' · 👩 Annika' if item.annika_loop else ''
    sample_flag = ' · ⚠️ sample required' if item.sample_required else ''
    sched_locked = _schedule_locked_for_item(item, schedule_lookup)
    # Per-card badge only shown when banner mode is off (< 50% unlocked)
    sched_badge = '' if (sched_locked or suppress_sched_badge) else '<span class="schedule-not-locked">⚠️ schedule not locked</span>'
    body = ""

    if item.decided_sku:
        body = f'<div class="decided-line">✅ {escape(item.decided_sku)}</div>'
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
        # Placeholder if watch_list item has no option images
        if not item.options:
            body += f'<div class="img-placeholder">{escape(item.title)}<br><small>vintage hunt · no image yet</small></div>'
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


def _approved_overshoots_block(items: List[Item]) -> str:
    """Show items with approved_overshoot=true in a distinct slate block so they remain visible."""
    overshoots = []
    for item in items:
        if "approved_overshoot" not in (item.notes or "").lower():
            continue
        if not item.options:
            continue
        rec = next((o for o in item.options if o.recommend), None)
        if rec and rec.price_usd > item.budget_target_usd:
            pct = (rec.price_usd / item.budget_target_usd - 1) * 100
            overshoots.append((item.id, rec.price_usd, item.budget_target_usd, pct))
    if not overshoots:
        return ""
    rows = "".join(
        f"<li>{escape(i)} &mdash; ${p:,.0f} vs target ${b:,.0f} (+{pct:.0f}%)</li>"
        for i, p, b, pct in overshoots
    )
    return (
        f'<div class="approved-overshoots-block">'
        f'<h4>Approved overshoots ({len(overshoots)})</h4>'
        f'<ul>{rows}</ul>'
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
    return f"""<div class="filter-bar">
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


def render_site_page(items: List[Item], meta: Meta, lint_findings: List[LintFinding],
                     schedule_lookup: Optional[ScheduleLookup] = None) -> str:
    visible = [it for it in items if it.decision_status != "stub"]
    lint_html = _render_lint_alerts(lint_findings)
    overshoot_html = _approved_overshoots_block(visible)
    banner_mode = _schedule_banner_mode(visible, schedule_lookup)
    schedule_banner_html = (
        '<div class="schedule-banner">⚠️ Construction schedule not yet locked — urgency badges deferred until dates are confirmed.</div>'
        if banner_mode else ""
    )
    cards_html = "\n".join(_render_item_card(it, schedule_lookup, suppress_sched_badge=banner_mode) for it in visible)
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
{ROOM_LINKS_HTML}
<main>
{overshoot_html}
{lint_html}
{schedule_banner_html}
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
                     design_hub_url: Optional[str] = None) -> str:
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
    cards_html = "\n".join(_render_item_card(it, schedule_lookup, suppress_sched_badge=banner_mode) for it in visible)

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
@media (max-width: 720px) {
  .annika-item-body { grid-template-columns: 1fr; }
  .cover { margin-top: 30px; padding: 0 16px; }
  .cover h1 { font-size: 26px; }
  .cta-block { padding: 0 16px; }
  main.annika-main { padding: 0 16px 80px; }
  .section-divider { padding: 0 16px; padding-top: 24px; }
  .section-note { padding: 0 16px; }
}
"""

# ANNIKA topnav is identical to main but marks /for-annika as current
ANNIKA_TOPNAV_HTML = """<nav class="topnav">
  <div class="topnav-inner">
    <a href="/" class="home">&larr; 1490 Lively Ridge</a>
    <a href="/">Home</a><a href="/mood-board">Mood</a><a href="/spectrum">Spectrum</a><a href="/decisions">Decisions</a><a href="/budget">Budget</a><a href="/sourcing">Sourcing</a><a href="/for-annika" class="current">&#9829; Annika</a><a href="/spec">Spec</a>
    <span class="group-label">Rooms</span>
    <a href="/kitchen">Kitchen</a><a href="/master">Master</a><a href="/baths">Baths</a><a href="/lr">LR</a><a href="/nursery">Nursery</a><a href="/office">Office</a>
    <span class="group-label">Canon</span>
    <a href="/cathie-hong">Cathie Hong</a><a href="/owiu">OWIU</a><a href="/sss">SSS</a><a href="/jenni-kayne">Jenni Kayne</a>
    <a href="/materials">Materials</a><a href="/rejected">Rejected</a>
  </div>
</nav>"""

ANNIKA_GLOSSARY_HTML = """<details class="annika-glossary" style="max-width:760px;margin:0 auto 32px;border:1px solid #e8e2d6;border-radius:10px;overflow:hidden;">
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
        # Detect wrong-product-class language in reasoning or details → escalate to error severity
        _wrong_class_signals = ["not a pot filler", "wrong product", "not a ", "doesn't exist",
                                 "does not exist", "not found", "bar/prep faucet", "wrong product class"]
        _opt_text_lower = ((pick_opt.details or "") + " " + (pick_opt.reasoning or "")).lower()
        _has_wrong_class = any(sig in _opt_text_lower for sig in _wrong_class_signals)
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
{toc_html}
{ANNIKA_GLOSSARY_HTML}
{sections_html}
{summary_cta_html}
</body>
</html>
"""
