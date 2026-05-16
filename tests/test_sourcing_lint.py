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
    # Use a non-substrate decorative tile that isn't in the allowed palette
    items = [
        _i("T1", category="tile_stone", room="kitchen", decided_sku="Cle Glaze Mist penny round"),
    ]
    findings = check_tile_palette(items, allowed=["cle_sea_salt_zellige", "carrara_slab", "cle_bejmat_master_only"])
    assert len(findings) >= 1
    assert any(f.severity == "error" for f in findings)


def test_tile_palette_substrate_tile_skipped():
    """Daltile porcelain / Caesarstone / other substrate tiles must NOT trigger palette errors."""
    items = [
        _i("T1", category="tile_stone", room="bath_1", decided_sku="Daltile Linden Point porcelain"),
        _i("T2", category="tile_stone", room="kitchen", decided_sku="Caesarstone Statuario counter"),
        _i("T3", category="tile_stone", room="bath_2", decided_sku="MSI porcelain floor"),
    ]
    findings = check_tile_palette(items, allowed=["cle_sea_salt_zellige", "carrara_slab", "cle_bejmat_master_only"])
    assert findings == []


def test_tile_palette_bejmat_outside_master_bath_errors():
    items = [
        _i("T1", category="tile_stone", room="kitchen", decided_sku="Cle Bejmat in kitchen"),
    ]
    findings = check_tile_palette(items, allowed=["cle_sea_salt_zellige", "carrara_slab", "cle_bejmat_master_only"])
    assert any(f.severity == "error" and "master" in f.message.lower() for f in findings)


from sourcing_lint import (
    check_paint_line, check_hardware_mix, check_budget_rollup,
)
from sourcing_schema import Meta, Budgets, ConsistencyLocks


# --- Paint line ---

def test_paint_line_aura_no_warning():
    items = [_i("P1", category="paint_finish", decided_sku="BM Aura White Dove OC-17")]
    findings = check_paint_line(items, expected_line="aura")
    assert findings == []


def test_paint_line_non_aura_warns():
    items = [_i("P1", category="paint_finish", decided_sku="SW Cashmere Eider White")]
    findings = check_paint_line(items, expected_line="aura")
    assert any(f.severity == "warning" and "P1" in f.message for f in findings)


# --- Hardware mix ---

def test_hardware_mix_balanced_room_no_warning():
    items = [
        _i(f"K{i}", room="kitchen", category="hardware", tags=["lacquered_brass"], decided_sku="brass pull")
        for i in range(3)
    ] + [
        _i(f"K{i+10}", room="kitchen", category="hardware", tags=["matte_black"], decided_sku="matte black knob")
        for i in range(3)
    ]
    findings = check_hardware_mix(items)
    assert all(f.severity != "warning" for f in findings)


def test_hardware_mix_unbalanced_room_info():
    items = [
        _i(f"K{i}", room="kitchen", category="hardware", tags=["lacquered_brass"], decided_sku="brass")
        for i in range(3)
    ] + [_i("K10", room="kitchen", category="hardware", tags=["matte_black"], decided_sku="matte black")]
    findings = check_hardware_mix(items)
    assert any(f.severity == "info" and "kitchen" in f.message.lower() for f in findings)


# --- Budget rollup ---

def _meta(cap=342000, furn=30000, p3=10000):
    return Meta(
        last_updated="2026-05-16",
        budgets=Budgets(construction_cap=cap, furniture_envelope=furn, path3_owner_direct_ceiling=p3),
        consistency_locks=ConsistencyLocks(
            brass_finish_family="Rejuvenation lacquered brass",
            wood_tone="white_oak_bleach_rubio_pure",
            tile_palette=["cle_sea_salt_zellige", "carrara_slab", "cle_bejmat_master_only"],
            paint_line="aura",
        ),
    )


def test_budget_rollup_under_no_error():
    items = [_i("X1", category="furniture")]
    items[0].budget_source = "furniture_envelope"
    items[0].budget_target_usd = 25000
    findings = check_budget_rollup(items, _meta())
    assert findings == []


def test_budget_rollup_furniture_overshoot_warns():
    """furniture_envelope is a soft target — overshoot is warning, not error."""
    items = [_i("X1", category="furniture")]
    items[0].budget_source = "furniture_envelope"
    items[0].budget_target_usd = 35000  # over $30K
    findings = check_budget_rollup(items, _meta())
    assert any(f.severity == "warning" and "furniture_envelope" in f.message for f in findings)


# --- Lint aggregator ---

from sourcing_lint import run_all_lints


def test_run_all_lints_returns_aggregated_findings():
    items = [
        _i("BR1", category="hardware", tags=["lacquered_brass"], decided_sku="WE matte brass"),  # warning
        _i("T1", category="tile_stone", room="kitchen", decided_sku="Cle Glaze Mist penny round"),  # error (non-substrate 4th tile)
    ]
    items[0].budget_source = "furniture_envelope"
    items[0].budget_target_usd = 35000  # over $30K → warning (soft target)
    findings = run_all_lints(items, _meta())
    severities = [f.severity for f in findings]
    assert "error" in severities  # tile palette violation
    assert "warning" in severities  # brass + furniture envelope


def test_run_all_lints_empty_items_no_findings():
    findings = run_all_lints([], _meta())
    assert findings == []
