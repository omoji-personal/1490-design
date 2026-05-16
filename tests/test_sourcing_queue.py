# tests/test_sourcing_queue.py
from datetime import date

from sourcing_queue import ScheduleLookup
from sourcing_loader import Schedule


def test_days_until_with_iso_date():
    sched = Schedule(phases={"bath_gut_start": "2026-06-15"})
    lookup = ScheduleLookup(schedule=sched, meta_last_updated="2026-05-16", today=date(2026, 6, 1))
    days, locked = lookup.days_until("bath_gut_start")
    assert days == 14
    assert locked is True


def test_days_until_with_null_date_falls_back():
    """Null phase date → fall back to meta.last_updated + 12 weeks, locked=False."""
    sched = Schedule(phases={"bath_gut_start": None})
    lookup = ScheduleLookup(schedule=sched, meta_last_updated="2026-05-16", today=date(2026, 5, 16))
    days, locked = lookup.days_until("bath_gut_start")
    # 12 weeks = 84 days from 2026-05-16
    assert days == 84
    assert locked is False


def test_days_until_negative_when_phase_passed():
    sched = Schedule(phases={"bath_gut_start": "2026-05-01"})
    lookup = ScheduleLookup(schedule=sched, meta_last_updated="2026-05-16", today=date(2026, 5, 16))
    days, _ = lookup.days_until("bath_gut_start")
    assert days == -15


def test_days_until_unknown_phase_raises():
    import pytest
    sched = Schedule(phases={})
    lookup = ScheduleLookup(schedule=sched, meta_last_updated="2026-05-16", today=date(2026, 5, 16))
    with pytest.raises(KeyError):
        lookup.days_until("nonexistent_phase")


from sourcing_queue import is_in_decision_queue
from sourcing_schema import Item, Option


def _make_item(id_, urgency, status, manual_trigger=False):
    return Item(
        id=id_, title="x", category="appliance", room="kitchen",
        urgency=urgency, lead_time_weeks=1,
        budget_source="construction_allowance", budget_target_usd=100,
        sourcing_actor="owner_direct", decision_status=status,
        annika_loop=False,
        options=[Option(sku="a", vendor="b", price_usd=1, image="", reasoning="")],
    ), manual_trigger


def test_queue_t0_within_window():
    item, _ = _make_item("X1", "T0", "options_drafted")
    sched = Schedule(phases={
        "roof_phase_start": "2026-06-01", "bath_gut_start": "2026-06-01",
        "kitchen_gut_start": "2026-06-01", "electrical_rough_start": "2026-06-01",
        "plumbing_rough_start": "2026-06-01", "finish_phase_start": "2026-08-01",
        "move_back_in": "2026-09-15",
    })
    lookup = ScheduleLookup(schedule=sched, meta_last_updated="2026-05-16", today=date(2026, 5, 20))
    assert is_in_decision_queue(item, lookup, manual_trigger_t3=False) is True


def test_queue_t0_outside_window():
    item, _ = _make_item("X1", "T0", "options_drafted")
    sched = Schedule(phases={
        "roof_phase_start": "2026-07-01", "bath_gut_start": "2026-07-01",
        "kitchen_gut_start": "2026-07-01", "electrical_rough_start": "2026-07-01",
        "plumbing_rough_start": "2026-07-01", "finish_phase_start": "2026-08-01",
        "move_back_in": "2026-09-15",
    })
    lookup = ScheduleLookup(schedule=sched, meta_last_updated="2026-05-16", today=date(2026, 5, 16))
    assert is_in_decision_queue(item, lookup, manual_trigger_t3=False) is False


def test_queue_t1_within_finish_window():
    item, _ = _make_item("X1", "T1", "options_drafted")
    sched = Schedule(phases={
        "roof_phase_start": "2026-06-01", "bath_gut_start": "2026-06-01",
        "kitchen_gut_start": "2026-06-01", "electrical_rough_start": "2026-06-01",
        "plumbing_rough_start": "2026-06-01", "finish_phase_start": "2026-08-01",
        "move_back_in": "2026-09-15",
    })
    lookup = ScheduleLookup(schedule=sched, meta_last_updated="2026-05-16", today=date(2026, 7, 28))
    assert is_in_decision_queue(item, lookup, manual_trigger_t3=False) is True


def test_queue_t2_within_move_back_window():
    item, _ = _make_item("X1", "T2", "options_drafted")
    sched = Schedule(phases={
        "roof_phase_start": "2026-06-01", "bath_gut_start": "2026-06-01",
        "kitchen_gut_start": "2026-06-01", "electrical_rough_start": "2026-06-01",
        "plumbing_rough_start": "2026-06-01", "finish_phase_start": "2026-08-01",
        "move_back_in": "2026-09-15",
    })
    lookup = ScheduleLookup(schedule=sched, meta_last_updated="2026-05-16", today=date(2026, 8, 28))
    assert is_in_decision_queue(item, lookup, manual_trigger_t3=False) is True


def test_queue_t3_only_with_manual_trigger():
    item, _ = _make_item("X1", "T3", "options_drafted")
    sched = Schedule(phases={k: "2026-06-01" for k in [
        "roof_phase_start", "bath_gut_start", "kitchen_gut_start",
        "electrical_rough_start", "plumbing_rough_start",
    ]} | {"finish_phase_start": "2026-08-01", "move_back_in": "2026-09-15"})
    lookup = ScheduleLookup(schedule=sched, meta_last_updated="2026-05-16", today=date(2026, 5, 16))
    assert is_in_decision_queue(item, lookup, manual_trigger_t3=False) is False
    assert is_in_decision_queue(item, lookup, manual_trigger_t3=True) is True


def test_queue_excludes_non_options_drafted():
    """Only options_drafted items can be in the queue."""
    for status in ["stub", "decided", "ordered", "installed"]:
        item, _ = _make_item("X1", "T0", status)
        sched = Schedule(phases={k: "2026-06-01" for k in [
            "roof_phase_start", "bath_gut_start", "kitchen_gut_start",
            "electrical_rough_start", "plumbing_rough_start",
        ]} | {"finish_phase_start": "2026-08-01", "move_back_in": "2026-09-15"})
        lookup = ScheduleLookup(schedule=sched, meta_last_updated="2026-05-16", today=date(2026, 5, 25))
        assert is_in_decision_queue(item, lookup, manual_trigger_t3=False) is False, f"status={status} should not be in queue"
