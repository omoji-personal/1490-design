# sourcing_render_md.py
"""Render sourcing data to 3 markdown outputs:
- SOURCING_TRACKER.md — full tracker grouped by urgency, then room
- needs-decision-now.md — filtered queue view
- annika-queue.md — Annika-loop filtered view
"""
from datetime import date
from typing import List, Optional

from sourcing_schema import Item, Meta
from sourcing_queue import ScheduleLookup, is_in_decision_queue

URGENCY_LABELS = {
    "T0": "T0 critical-path (decide before construction phase)",
    "T1": "T1 mid-reno (decide before finish phase)",
    "T2": "T2 post-reno (decide after move-back-in)",
    "T3": "T3 year-1+ (slow layers)",
}


def _format_item(item: Item) -> str:
    """One item rendered as a markdown subsection."""
    lines = [f"### `{item.id}` — {item.title}"]
    badge_map = {
        "options_drafted": "🟡 options-drafted",
        "awaiting_sample": "🟠 awaiting-sample",
        "sample_in_hand": "🟢 sample-in-hand",
        "decided": "✅ decided",
        "ordered": "📦 ordered",
        "received": "📬 received",
        "installed": "🏁 installed",
        "deferred_p2": "⬇️ deferred-p2",
        "cancelled": "❌ cancelled",
        "watch_list": "👁 watch-list",
        "found_candidate": "🔍 found-candidate",
    }
    lines.append(f"**Status:** {badge_map.get(item.decision_status, item.decision_status)} · "
                 f"**Room:** {item.room} · **Category:** {item.category} · "
                 f"**Urgency:** {item.urgency} · **Lead:** {item.lead_time_weeks} wk")
    lines.append(f"**Budget:** ${item.budget_target_usd:,.0f} from `{item.budget_source}` · "
                 f"**Actor:** `{item.sourcing_actor}`"
                 + (" · ⚠️ sample required" if item.sample_required else "")
                 + (" · 👩 annika-loop" if item.annika_loop else ""))

    if item.decided_sku:
        lines.append(f"\n**✅ Decided:** {item.decided_sku}")
    elif item.vintage_brief:
        lines.append(f"\n**Vintage brief:** {item.vintage_brief.style}")
        if item.vintage_brief.not_:
            lines.append(f"**Avoid:** {item.vintage_brief.not_}")
        lines.append(f"**Target $:** {item.vintage_brief.target_price_usd} · "
                     f"**Hunt venues:** {', '.join(item.vintage_brief.hunt_venues)}")
    elif item.options:
        lines.append("\n**Options:**\n")
        for i, opt in enumerate(item.options, 1):
            star = "★ " if opt.recommend else ""
            lines.append(f"{i}. {star}**{opt.sku}** @ {opt.vendor} — ${opt.price_usd:,.0f}")
            lines.append(f"   {opt.reasoning}")

    if item.notes:
        lines.append(f"\n*Notes:* {item.notes}")

    return "\n".join(lines)


def render_full_tracker(items: List[Item], meta: Meta) -> str:
    """Group by urgency tier, then by room, then by id within room. Stub items hidden."""
    visible = [it for it in items if it.decision_status != "stub"]
    if not visible:
        return f"# Sourcing Tracker\n\n*Last updated: {meta.last_updated}*\n\n_No items yet._\n"

    lines = [f"# Sourcing Tracker", "", f"*Last updated: {meta.last_updated}*", "",
             f"Total visible items: {len(visible)} · "
             f"Construction cap: ${meta.budgets.construction_cap:,} · "
             f"Furniture envelope: ${meta.budgets.furniture_envelope:,}", ""]

    by_urgency: dict = {}
    for it in visible:
        by_urgency.setdefault(it.urgency, []).append(it)

    for tier in ["T0", "T1", "T2", "T3"]:
        bucket = by_urgency.get(tier, [])
        if not bucket:
            continue
        lines.append(f"\n## {URGENCY_LABELS[tier]}")
        by_room: dict = {}
        for it in bucket:
            by_room.setdefault(it.room, []).append(it)
        for room in sorted(by_room.keys()):
            lines.append(f"\n### Room: `{room}`")
            for it in sorted(by_room[room], key=lambda x: x.id):
                lines.append("")
                lines.append(_format_item(it))

    return "\n".join(lines) + "\n"
