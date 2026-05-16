# tests/test_sourcing_lint.py
from sourcing_lint import (
    LintFinding,
    check_brass_finish,
    check_wood_tone,
    check_tile_palette,
)
from sourcing_schema import Item, Option


def _i(id_, room="kitchen", category="hardware", tags=None, decided_sku=None, options=None):
    return Item(
        id=id_, title=id_, category=category, room=room,
        urgency="T0", lead_time_weeks=1,
        budget_source="construction_allowance", budget_target_usd=100,
        sourcing_actor="owner_direct",
        decision_status="decided" if decided_sku else "options_drafted",
        annika_loop=False,
        cross_room_consistency=tags or [],
        options=options or [Option(sku="x", vendor="y", price_usd=1, image="", reasoning="")] if not decided_sku else None,
        decided_sku=decided_sku,
    )


# --- Brass finish ---

def test_brass_finish_all_same_family_no_warning():
    items = [
        _i("X1", tags=["lacquered_brass"], decided_sku="Rejuvenation Westmore lacquered brass"),
        _i("X2", tags=["lacquered_brass"], decided_sku="Rejuvenation Pinnock lacquered brass"),
    ]
    findings = check_brass_finish(items, expected_family="Rejuvenation lacquered brass")
    assert findings == []


def test_brass_finish_drift_warns():
    items = [
        _i("X1", tags=["lacquered_brass"], decided_sku="Rejuvenation Westmore lacquered brass"),
        _i("X2", tags=["lacquered_brass"], decided_sku="WE matte brass pull"),
    ]
    findings = check_brass_finish(items, expected_family="Rejuvenation lacquered brass")
    assert len(findings) == 1
    assert findings[0].severity == "warning"
    assert "X2" in findings[0].message


# --- Wood tone ---

def test_wood_tone_all_same_treatment_no_warning():
    items = [
        _i("F1", category="paint_finish", decided_sku="Rubio Monocoat Pure on white oak"),
        _i("C1", category="cabinetry_millwork", decided_sku="white oak Bleach + Rubio Pure"),
    ]
    findings = check_wood_tone(items, expected_treatment="white_oak_bleach_rubio_pure")
    assert findings == []


def test_wood_tone_drift_warns():
    items = [
        _i("F1", category="paint_finish", decided_sku="Rubio Monocoat Pure"),
        _i("C1", category="cabinetry_millwork", decided_sku="Minwax Special Walnut stain"),
    ]
    findings = check_wood_tone(items, expected_treatment="white_oak_bleach_rubio_pure")
    assert len(findings) >= 1
    assert any("C1" in f.message for f in findings)


# --- Tile palette ---

def test_tile_palette_allowed_tiles_no_error():
    items = [
        _i("T1", category="tile_stone", room="kitchen", decided_sku="Carrara slab backsplash"),
        _i("T2", category="tile_stone", room="master_bath", decided_sku="Cle Bejmat master"),
        _i("T3", category="tile_stone", room="hall_bath", decided_sku="Cle Sea Salt zellige"),
    ]
    findings = check_tile_palette(items, allowed=["cle_sea_salt_zellige", "carrara_slab", "cle_bejmat_master_only"])
    assert findings == []


def test_tile_palette_fourth_tile_errors():
    items = [
        _i("T1", category="tile_stone", room="kitchen", decided_sku="Daltile Linden Point"),
    ]
    findings = check_tile_palette(items, allowed=["cle_sea_salt_zellige", "carrara_slab", "cle_bejmat_master_only"])
    assert len(findings) >= 1
    assert any(f.severity == "error" for f in findings)


def test_tile_palette_bejmat_outside_master_bath_errors():
    items = [
        _i("T1", category="tile_stone", room="kitchen", decided_sku="Cle Bejmat in kitchen"),
    ]
    findings = check_tile_palette(items, allowed=["cle_sea_salt_zellige", "carrara_slab", "cle_bejmat_master_only"])
    assert any(f.severity == "error" and "master" in f.message.lower() for f in findings)
