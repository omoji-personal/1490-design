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
