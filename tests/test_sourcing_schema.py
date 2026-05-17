from pathlib import Path
import pytest
import yaml

from sourcing_schema import Item, Option, Meta, parse_item, parse_meta, ValidationError

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_standard_item():
    """A valid standard item with options array parses cleanly."""
    raw = {
        "id": "G3-HOOD",
        "title": "Kitchen range hood",
        "category": "appliance",
        "room": "kitchen",
        "urgency": "T0",
        "lead_time_weeks": 4,
        "budget_source": "construction_allowance",
        "budget_target_usd": 1500,
        "sourcing_actor": "owner_direct",
        "decision_status": "options_drafted",
        "annika_loop": True,
        "cross_room_consistency": [],
        "dependencies": [],
        "sample_required": False,
        "options": [
            {
                "sku": "Vent-A-Hood SLDH9-K42 SS",
                "vendor": "CDGA",
                "price_usd": 1480,
                "image": "images/sourcing/g3-hood-1.jpg",
                "reasoning": "Magic Lung; 900 CFM.",
                "recommend": True,
            }
        ],
        "decided_sku": None,
        "ordered_date": None,
        "received_date": None,
        "installed_date": None,
        "notes": "",
        "revision_history": [],
    }
    item = parse_item(raw)
    assert item.id == "G3-HOOD"
    assert item.urgency == "T0"
    assert len(item.options) == 1
    assert item.options[0].recommend is True
    assert item.vintage_brief is None


def test_parse_canon_locked_item():
    """status=decided + decided_sku set, no options or vintage_brief."""
    raw = {
        "id": "MB-FAUCET",
        "title": "Master bath faucet",
        "category": "plumbing_fixture",
        "room": "master_bath",
        "urgency": "T0",
        "lead_time_weeks": 2,
        "budget_source": "construction_allowance",
        "budget_target_usd": 450,
        "sourcing_actor": "owner_direct",
        "decision_status": "decided",
        "annika_loop": True,
        "decided_sku": "Delta Trinsic 559LF-CZMPU",
    }
    item = parse_item(raw)
    assert item.decided_sku == "Delta Trinsic 559LF-CZMPU"
    assert item.options is None
    assert item.vintage_brief is None


def test_parse_vintage_item():
    raw = {
        "id": "LR-COFFEE-VINTAGE",
        "title": "LR coffee table (vintage)",
        "category": "furniture",
        "room": "lr",
        "urgency": "T3",
        "lead_time_weeks": 0,
        "budget_source": "furniture_envelope",
        "budget_target_usd": 1200,
        "sourcing_actor": "vintage_hunt",
        "decision_status": "watch_list",
        "annika_loop": False,
        "vintage_brief": {
            "style": "Mid-century walnut oval, 36-44 inch",
            "not": "no glass, no chrome",
            "target_price_usd": "800-1500",
            "hunt_venues": ["Westside Modern", "City Issue"],
            "aspirational_refs": ["cathiehong_12"],
        },
    }
    item = parse_item(raw)
    assert item.vintage_brief is not None
    assert item.vintage_brief.style.startswith("Mid-century")
    assert item.options is None


def test_invalid_category_rejected():
    raw = {
        "id": "X-1",
        "title": "x",
        "category": "not_a_category",
        "room": "kitchen",
        "urgency": "T0",
        "lead_time_weeks": 1,
        "budget_source": "construction_allowance",
        "budget_target_usd": 100,
        "sourcing_actor": "owner_direct",
        "decision_status": "stub",
        "annika_loop": False,
        "options": [{"sku": "a", "vendor": "b", "price_usd": 1, "image": "", "reasoning": ""}],
    }
    with pytest.raises(ValidationError, match="invalid category"):
        parse_item(raw)


def test_catalog_status_field_optional_and_validated():
    """catalog_status is None by default and accepts only the three documented values."""
    base = {
        "id": "MB-FAUCET",
        "title": "x",
        "category": "plumbing_fixture",
        "room": "master_bath",
        "urgency": "T0",
        "lead_time_weeks": 2,
        "budget_source": "construction_allowance",
        "budget_target_usd": 450,
        "sourcing_actor": "owner_direct",
        "decision_status": "decided",
        "annika_loop": False,
        "decided_sku": "Delta Trinsic",
    }
    # Default = None
    item = parse_item(dict(base))
    assert item.catalog_status is None
    assert item.catalog_status_note is None
    # All three valid statuses parse and round-trip
    for s in ("verified", "needs_reselection", "spec_error"):
        raw = dict(base, catalog_status=s, catalog_status_note=f"note for {s}")
        item = parse_item(raw)
        assert item.catalog_status == s
        assert item.catalog_status_note == f"note for {s}"
    # Invalid value rejected
    raw = dict(base, catalog_status="bogus")
    with pytest.raises(ValidationError, match="invalid catalog_status"):
        parse_item(raw)


def test_options_and_vintage_both_rejected():
    raw = {
        "id": "X-2",
        "title": "x",
        "category": "furniture",
        "room": "lr",
        "urgency": "T2",
        "lead_time_weeks": 0,
        "budget_source": "furniture_envelope",
        "budget_target_usd": 500,
        "sourcing_actor": "owner_furniture",
        "decision_status": "stub",
        "annika_loop": False,
        "options": [{"sku": "a", "vendor": "b", "price_usd": 1, "image": "", "reasoning": ""}],
        "vintage_brief": {"style": "x", "hunt_venues": [], "aspirational_refs": []},
    }
    with pytest.raises(ValidationError, match="cannot have both"):
        parse_item(raw)


def test_item_vendor_field_optional_and_roundtrips():
    """The new top-level `vendor` field is None by default and round-trips
    a non-empty value through parse_item."""
    base = {
        "id": "MB-FAUCET",
        "title": "Master bath faucet",
        "category": "plumbing_fixture",
        "room": "master_bath",
        "urgency": "T0",
        "lead_time_weeks": 2,
        "budget_source": "construction_allowance",
        "budget_target_usd": 450,
        "sourcing_actor": "owner_direct",
        "decision_status": "decided",
        "annika_loop": True,
        "decided_sku": "Delta Trinsic 559LF-CZMPU Champagne Bronze",
    }
    # Missing → None
    item = parse_item(base)
    assert item.vendor is None
    # Set → round-trips through
    raw_with_vendor = dict(base, vendor="Delta")
    item2 = parse_item(raw_with_vendor)
    assert item2.vendor == "Delta"
