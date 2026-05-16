#!/usr/bin/env python3
"""Build sourcing outputs: 3 markdown files in HomeAI + 1 HTML page on the site.

Reads:  ~/Desktop/HomeAI/scope/sourcing.yaml
        ~/Desktop/HomeAI/data/construction_schedule.yaml
Writes: ~/Desktop/HomeAI/scope/SOURCING_TRACKER.md
        ~/Desktop/HomeAI/scope/needs-decision-now.md
        ~/Desktop/HomeAI/scope/annika-queue.md
        ~/Desktop/1490-design-site/sourcing.html
"""
from datetime import date
from pathlib import Path

from sourcing_loader import load_sourcing, load_schedule
from sourcing_queue import ScheduleLookup
from sourcing_lint import run_all_lints
from sourcing_render_md import render_full_tracker, render_decision_queue, render_annika_queue
from sourcing_render_html import render_site_page, render_room_page


HOME = Path.home()
HOMEAI = HOME / "Desktop" / "HomeAI"
SITE = HOME / "Desktop" / "1490-design-site"

SOURCING_YAML = HOMEAI / "scope" / "sourcing.yaml"
SCHEDULE_YAML = HOMEAI / "data" / "construction_schedule.yaml"

OUT_TRACKER = HOMEAI / "scope" / "SOURCING_TRACKER.md"
OUT_QUEUE = HOMEAI / "scope" / "needs-decision-now.md"
OUT_ANNIKA = HOMEAI / "scope" / "annika-queue.md"
OUT_HTML = SITE / "sourcing.html"


def main(manual_trigger_t3: bool = False) -> None:
    data = load_sourcing(SOURCING_YAML)
    schedule = load_schedule(SCHEDULE_YAML)
    lookup = ScheduleLookup(
        schedule=schedule,
        meta_last_updated=data.meta.last_updated,
        today=date.today(),
    )

    findings = run_all_lints(data.items, data.meta)
    errors = [f for f in findings if f.severity == "error"]

    OUT_TRACKER.write_text(render_full_tracker(data.items, data.meta))
    OUT_QUEUE.write_text(render_decision_queue(data.items, data.meta, lookup, manual_trigger_t3))
    OUT_ANNIKA.write_text(render_annika_queue(data.items, data.meta))
    OUT_HTML.write_text(render_site_page(data.items, data.meta, findings, schedule_lookup=lookup))

    print(f"Wrote {OUT_TRACKER.name} ({OUT_TRACKER.stat().st_size:,} bytes)")
    print(f"Wrote {OUT_QUEUE.name} ({OUT_QUEUE.stat().st_size:,} bytes)")
    print(f"Wrote {OUT_ANNIKA.name} ({OUT_ANNIKA.stat().st_size:,} bytes)")
    print(f"Wrote {OUT_HTML.name} ({OUT_HTML.stat().st_size:,} bytes)")
    ROOM_VIEWS = [
        ("Kitchen", ["kitchen"], "sourcing-kitchen.html"),
        ("Master Suite", ["master_br", "master_bath"], "sourcing-master.html"),
        ("Baths (Hall + Basement)", ["hall_bath", "basement_bath"], "sourcing-baths.html"),
        ("Living + Dining", ["lr", "dining"], "sourcing-lr.html"),
        ("Nursery", ["nursery"], "sourcing-nursery.html"),
        ("Office", ["office"], "sourcing-office.html"),
    ]

    for label, rooms, fname in ROOM_VIEWS:
        out = SITE / fname
        out.write_text(render_room_page(label, rooms, data.items, data.meta, schedule_lookup=lookup))
        print(f"Wrote {out.name} ({out.stat().st_size:,} bytes)")

    print(f"\nLint: {len(findings)} findings ({len(errors)} errors)")
    for f in findings:
        marker = {"error": "❌", "warning": "⚠️", "info": "ℹ️"}.get(f.severity, "·")
        print(f"  {marker} [{f.severity}] {f.message}")

    if errors:
        import sys
        sys.exit(1)


if __name__ == "__main__":
    import sys
    manual = "--trigger-t3" in sys.argv
    main(manual_trigger_t3=manual)
