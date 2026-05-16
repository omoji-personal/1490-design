# tests/test_sourcing_render_md.py
from datetime import date
from pathlib import Path

from sourcing_loader import load_sourcing, load_schedule
from sourcing_queue import ScheduleLookup
from sourcing_render_md import render_full_tracker

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
