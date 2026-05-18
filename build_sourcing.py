#!/usr/bin/env python3
"""Build sourcing outputs: 3 markdown files in HomeAI + HTML pages on the site.

Reads:  ~/Desktop/HomeAI/scope/sourcing.yaml
        ~/Desktop/HomeAI/scope/supplier_directory.yaml          (for /suppliers)
        ~/Desktop/HomeAI/data/construction_schedule.yaml
        ~/Desktop/HomeAI/correspondence/annika-cover-note.md   (optional)
        ~/Desktop/HomeAI/scope/annika-questions.yaml           (optional)
Writes: ~/Desktop/HomeAI/scope/SOURCING_TRACKER.md
        ~/Desktop/HomeAI/scope/needs-decision-now.md
        ~/Desktop/HomeAI/scope/annika-queue.md
        ~/Desktop/1490-design-site/sourcing.html
        ~/Desktop/1490-design-site/for-annika.html             (auto-generated)
        ~/Desktop/1490-design-site/vendors.html
        ~/Desktop/1490-design-site/suppliers.html
        ~/Desktop/1490-design-site/sourcing-<room>.html         (6 room views)

Flags: --allow-missing-suppliers   bypass the fail-loud check when
                                    supplier_directory.yaml is absent;
                                    /suppliers.html still gets rendered as
                                    an empty-state placeholder via the
                                    loader's directory-not-found path.
       --trigger-t3                manual T3 trigger for decision queue
"""
import argparse
from datetime import date
from pathlib import Path

from sourcing_loader import load_sourcing, load_schedule
from sourcing_queue import ScheduleLookup
from sourcing_lint import run_all_lints
from sourcing_render_md import render_full_tracker, render_decision_queue, render_annika_queue
from sourcing_render_html import (
    render_site_page, render_room_page, render_for_annika, render_vendors_page,
    render_suppliers_page,
)
from sourcing_git_history import build_last_changed_map


HOME = Path.home()
HOMEAI = HOME / "Desktop" / "HomeAI"
SITE = HOME / "Desktop" / "1490-design-site"

SOURCING_YAML = HOMEAI / "scope" / "sourcing.yaml"
SUPPLIER_DIRECTORY_YAML = HOMEAI / "scope" / "supplier_directory.yaml"
SCHEDULE_YAML = HOMEAI / "data" / "construction_schedule.yaml"
COVER_NOTE = HOMEAI / "correspondence" / "annika-cover-note.md"
ANNIKA_QUESTIONS = HOMEAI / "scope" / "annika-questions.yaml"

OUT_TRACKER = HOMEAI / "scope" / "SOURCING_TRACKER.md"
OUT_QUEUE = HOMEAI / "scope" / "needs-decision-now.md"
OUT_ANNIKA_MD = HOMEAI / "scope" / "annika-queue.md"
OUT_HTML = SITE / "sourcing.html"
OUT_ANNIKA_HTML = SITE / "for-annika.html"
OUT_VENDORS_HTML = SITE / "vendors.html"
OUT_SUPPLIERS_HTML = SITE / "suppliers.html"


def main(manual_trigger_t3: bool = False, allow_missing_suppliers: bool = False) -> None:
    # R2 Fix C9 — fail loud if supplier_directory.yaml is missing instead of
    # silently writing a placeholder suppliers.html. Operator can override with
    # --allow-missing-suppliers when bootstrapping a fresh repo.
    if not SUPPLIER_DIRECTORY_YAML.exists() and not allow_missing_suppliers:
        import sys
        sys.stderr.write(
            f"ERROR: supplier_directory.yaml not found at {SUPPLIER_DIRECTORY_YAML}\n"
            f"       /suppliers.html cannot be rendered without it.\n"
            f"       Pass --allow-missing-suppliers to skip this check.\n"
        )
        sys.exit(1)

    data = load_sourcing(SOURCING_YAML)
    schedule = load_schedule(SCHEDULE_YAML)
    lookup = ScheduleLookup(
        schedule=schedule,
        meta_last_updated=data.meta.last_updated,
        today=date.today(),
    )

    findings = run_all_lints(data.items, data.meta)
    errors = [f for f in findings if f.severity == "error"]

    # D4: git-blame-derived last-changed date per item (best-effort; {} if git unavailable).
    last_changed = build_last_changed_map(SOURCING_YAML)

    OUT_TRACKER.write_text(render_full_tracker(data.items, data.meta))
    OUT_QUEUE.write_text(render_decision_queue(data.items, data.meta, lookup, manual_trigger_t3))
    OUT_ANNIKA_MD.write_text(render_annika_queue(data.items, data.meta))
    OUT_HTML.write_text(render_site_page(
        data.items, data.meta, findings,
        schedule_lookup=lookup,
        last_changed_map=last_changed,
    ))
    OUT_ANNIKA_HTML.write_text(render_for_annika(
        data.items, data.meta,
        cover_note_path=COVER_NOTE,
        questions_path=ANNIKA_QUESTIONS,
    ))
    OUT_VENDORS_HTML.write_text(render_vendors_page(
        data.items, data.meta, last_changed_map=last_changed,
    ))
    OUT_SUPPLIERS_HTML.write_text(render_suppliers_page())

    print(f"Wrote {OUT_TRACKER.name} ({OUT_TRACKER.stat().st_size:,} bytes)")
    print(f"Wrote {OUT_QUEUE.name} ({OUT_QUEUE.stat().st_size:,} bytes)")
    print(f"Wrote {OUT_ANNIKA_MD.name} ({OUT_ANNIKA_MD.stat().st_size:,} bytes)")
    print(f"Wrote {OUT_HTML.name} ({OUT_HTML.stat().st_size:,} bytes)")
    print(f"Wrote {OUT_ANNIKA_HTML.name} ({OUT_ANNIKA_HTML.stat().st_size:,} bytes)")
    print(f"Wrote {OUT_VENDORS_HTML.name} ({OUT_VENDORS_HTML.stat().st_size:,} bytes)")
    print(f"Wrote {OUT_SUPPLIERS_HTML.name} ({OUT_SUPPLIERS_HTML.stat().st_size:,} bytes)")
    ROOM_VIEWS = [
        ("Kitchen", ["kitchen"], "sourcing-kitchen.html", "/kitchen"),
        ("Master Suite", ["master_br", "master_bath"], "sourcing-master.html", "/master"),
        ("Baths (Hall + Basement)", ["hall_bath", "basement_bath"], "sourcing-baths.html", "/baths"),
        ("Living + Dining", ["lr", "dining"], "sourcing-lr.html", "/lr"),
        ("Nursery", ["nursery"], "sourcing-nursery.html", "/nursery"),
        ("Office", ["office"], "sourcing-office.html", "/office"),
    ]

    for label, rooms, fname, hub_url in ROOM_VIEWS:
        out = SITE / fname
        out.write_text(render_room_page(label, rooms, data.items, data.meta,
                                        schedule_lookup=lookup, design_hub_url=hub_url,
                                        last_changed_map=last_changed))
        print(f"Wrote {out.name} ({out.stat().st_size:,} bytes)")

    print(f"\nLint: {len(findings)} findings ({len(errors)} errors)")
    for f in findings:
        marker = {"error": "❌", "warning": "⚠️", "info": "ℹ️"}.get(f.severity, "·")
        print(f"  {marker} [{f.severity}] {f.message}")

    if errors:
        import sys
        sys.exit(1)


def _parse_args(argv=None):
    """R5 Min1 — argparse replaces the ad-hoc `in sys.argv` string scan so
    typos like `--trigger_t3` fail loud and `--help` prints accurate text
    (the previous help comment described `--allow-missing-suppliers` as
    'skip /suppliers render', which didn't match the loader's actual
    empty-state placeholder behavior)."""
    p = argparse.ArgumentParser(
        prog="build_sourcing.py",
        description=(
            "Build /sourcing, /vendors, /suppliers, /for-annika + 6 room views "
            "from HomeAI yaml scope."
        ),
    )
    p.add_argument(
        "--allow-missing-suppliers",
        action="store_true",
        help=(
            "Bypass the fail-loud check when supplier_directory.yaml is "
            "absent. The loader still renders an empty-state /suppliers "
            "placeholder; this flag only suppresses the build-time error."
        ),
    )
    p.add_argument(
        "--trigger-t3",
        action="store_true",
        help="Manual T3 trigger for the decision-queue tier rules.",
    )
    return p.parse_args(argv)


if __name__ == "__main__":
    args = _parse_args()
    main(
        manual_trigger_t3=args.trigger_t3,
        allow_missing_suppliers=args.allow_missing_suppliers,
    )
