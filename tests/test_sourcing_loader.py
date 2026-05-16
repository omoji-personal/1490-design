# tests/test_sourcing_loader.py
from pathlib import Path
import pytest

from sourcing_loader import load_sourcing, load_schedule, SourcingData, Schedule

FIXTURES = Path(__file__).parent / "fixtures"


def test_load_sourcing_returns_meta_and_items():
    data = load_sourcing(FIXTURES / "sample_sourcing.yaml")
    assert isinstance(data, SourcingData)
    assert data.meta.budgets.construction_cap == 342000
    assert len(data.items) == 2
    assert data.items[0].id == "G3-HOOD"
    assert data.items[1].id == "MB-FAUCET"


def test_load_schedule_returns_phase_dates():
    sched = load_schedule(FIXTURES / "sample_schedule.yaml")
    assert isinstance(sched, Schedule)
    assert sched.phases["roof_phase_start"] == "2026-06-01"
    assert sched.phases["move_back_in"] == "2026-09-15"


def test_load_schedule_with_null_dates():
    """When phase dates are null, they come through as None."""
    import yaml
    tmp = FIXTURES.parent / "tmp_null_sched.yaml"
    tmp.write_text("phases:\n  roof_phase_start: null\n  bath_gut_start: null\n  kitchen_gut_start: null\n  electrical_rough_start: null\n  plumbing_rough_start: null\n  finish_phase_start: null\n  move_back_in: null\n")
    try:
        sched = load_schedule(tmp)
        assert sched.phases["roof_phase_start"] is None
        assert sched.phases["move_back_in"] is None
    finally:
        tmp.unlink()
