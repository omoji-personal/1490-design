# tests/test_sourcing_render_md.py
from datetime import date
from pathlib import Path

from sourcing_loader import load_sourcing, load_schedule
from sourcing_queue import ScheduleLookup
from sourcing_render_md import render_full_tracker, render_decision_queue, render_annika_queue

FIXTURES = Path(__file__).parent / "fixtures"


def test_full_tracker_groups_by_urgency_then_room():
    data = load_sourcing(FIXTURES / "sample_sourcing.yaml")
    md = render_full_tracker(data.items, data.meta)
    # Both fixture items are T0 / kitchen and master_bath
    assert "## T0" in md
    assert "G3-HOOD" in md
    assert "MB-FAUCET" in md
    # MB-FAUCET is canon-locked decided — should show decided_sku
    assert "Delta Trinsic" in md


def test_full_tracker_hides_stub_items():
    data = load_sourcing(FIXTURES / "sample_sourcing.yaml")
    # Mutate one item to stub
    data.items[0].decision_status = "stub"
    md = render_full_tracker(data.items, data.meta)
    assert "G3-HOOD" not in md
    assert "MB-FAUCET" in md  # other item still appears


def test_render_decision_queue_only_includes_queue_items():
    data = load_sourcing(FIXTURES / "sample_sourcing.yaml")
    sched = load_schedule(FIXTURES / "sample_schedule.yaml")
    lookup = ScheduleLookup(schedule=sched, meta_last_updated=data.meta.last_updated, today=date(2026, 6, 5))
    md = render_decision_queue(data.items, data.meta, lookup, manual_trigger_t3=False)
    # G3-HOOD is T0 options_drafted, bath_gut 2026-06-15, today 2026-06-05 → 10 days → IN queue
    assert "G3-HOOD" in md
    # MB-FAUCET is decided → NOT in queue
    assert "MB-FAUCET" not in md


def test_render_decision_queue_empty_state():
    data = load_sourcing(FIXTURES / "sample_sourcing.yaml")
    sched = load_schedule(FIXTURES / "sample_schedule.yaml")
    # Today way before any phase → no T0 in window
    lookup = ScheduleLookup(schedule=sched, meta_last_updated=data.meta.last_updated, today=date(2026, 1, 1))
    md = render_decision_queue(data.items, data.meta, lookup, manual_trigger_t3=False)
    assert "no items" in md.lower() or "nothing" in md.lower()


def test_render_annika_queue_filters_to_annika_loop():
    data = load_sourcing(FIXTURES / "sample_sourcing.yaml")
    md = render_annika_queue(data.items, data.meta)
    # Both fixture items have annika_loop=True
    assert "G3-HOOD" in md
    assert "MB-FAUCET" in md


def test_render_annika_queue_excludes_non_loop_items():
    data = load_sourcing(FIXTURES / "sample_sourcing.yaml")
    data.items[0].annika_loop = False
    md = render_annika_queue(data.items, data.meta)
    assert "G3-HOOD" not in md
    assert "MB-FAUCET" in md
