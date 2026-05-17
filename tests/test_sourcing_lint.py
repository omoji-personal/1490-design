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
    """Explicit non-allowed brass treatment (matte brass) should warn."""
    items = [
        _i("X1", tags=["lacquered_brass"], decided_sku="Rejuvenation Westmore lacquered brass"),
        _i("X2", tags=["lacquered_brass"], decided_sku="WE matte brass pull"),
    ]
    findings = check_brass_finish(items, expected_family="Rejuvenation lacquered brass")
    assert len(findings) == 1
    assert findings[0].severity == "warning"
    assert "X2" in findings[0].message


def test_brass_finish_schoolhouse_no_warning():
    """Schoolhouse lacquered brass is an allowed family — should not warn."""
    items = [
        _i("S1", tags=["lacquered_brass"], decided_sku="Schoolhouse Princeton Wall Sconce, lacquered brass, 4-inch milk glass"),
    ]
    findings = check_brass_finish(items, expected_family="Rejuvenation lacquered brass")
    assert findings == []


def test_brass_finish_cedar_moss_no_warning():
    """Cedar & Moss items are always lacquered brass in canon — should not warn."""
    items = [
        _i("C1", tags=["lacquered_brass"], decided_sku="Cedar & Moss Globe Sconce, lacquered brass"),
    ]
    findings = check_brass_finish(items, expected_family="Rejuvenation lacquered brass")
    assert findings == []


def test_brass_finish_polished_brass_warns():
    """Polished brass is a confirmed non-allowed treatment — should warn."""
    items = [
        _i("P1", tags=["lacquered_brass"], decided_sku="Newport Brass polished brass faucet"),
    ]
    findings = check_brass_finish(items, expected_family="Rejuvenation lacquered brass")
    assert any(f.severity == "warning" and "P1" in f.message for f in findings)


def test_brass_finish_no_brand_lacquered_no_warning():
    """Manufacturer-agnostic 'lacquered brass' phrase should pass without brand qualifier."""
    items = [
        _i("N1", tags=["lacquered_brass"], decided_sku="wall sconce, lacquered brass finish"),
    ]
    findings = check_brass_finish(items, expected_family="Rejuvenation lacquered brass")
    assert findings == []


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
    check_no_fictional_sku_urls, check_no_collection_landing_urls,
    check_known_vendor_finishes,
    check_per_item_budget_overshoot,
    check_no_orphan_sku_refs_in_notes,
    check_catalog_status_callouts,
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


def test_paint_line_cabinet_factory_finish_no_warning():
    """Cabinet items categorized as paint_finish with factory-finish SKU (no paint brand) should not warn."""
    items = [_i("CF1", category="paint_finish",
                decided_sku="KraftMaid Vantage light oak Shaker — factory finish included in cabinet line")]
    findings = check_paint_line(items, expected_line="aura")
    assert findings == []


def test_paint_line_bm_non_aura_sku_no_warning():
    """Any BM Aura family variant in SKU text should pass even without the word 'aura'."""
    items = [_i("P2", category="paint_finish", decided_sku="BM Saybrook Sage HC-114, Aura Bath & Spa matte")]
    findings = check_paint_line(items, expected_line="aura")
    assert findings == []


def test_paint_line_behr_warns():
    """Behr is a forbidden brand — should warn regardless of product line."""
    items = [_i("P3", category="paint_finish", decided_sku="Behr Premium Plus Ultra pure white")]
    findings = check_paint_line(items, expected_line="aura")
    assert any(f.severity == "warning" and "P3" in f.message for f in findings)


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
    """6-item room with 5 brass and 1 black → under the ≥2 threshold for black → info finding."""
    items = [
        _i(f"K{i}", room="kitchen", category="hardware", tags=["lacquered_brass"], decided_sku="brass")
        for i in range(5)
    ] + [_i("K10", room="kitchen", category="hardware", tags=["matte_black"], decided_sku="matte black")]
    findings = check_hardware_mix(items)
    assert any(f.severity == "info" and "kitchen" in f.message.lower() for f in findings)


def test_hardware_mix_small_room_skipped():
    """Room with <6 hardware items should never fire even if only one finish."""
    items = [
        _i(f"K{i}", room="bath_tiny", category="hardware", tags=["lacquered_brass"], decided_sku="brass")
        for i in range(3)
    ] + [_i("K10", room="bath_tiny", category="hardware", tags=["matte_black"], decided_sku="matte black")]
    findings = check_hardware_mix(items)
    assert not any("bath_tiny" in (f.item_id or "") or "bath_tiny" in f.message for f in findings)


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


# --- Rule 7: fictional SKU URLs ---

def _meta_simple():
    return _meta()


def _opt(sku="SKU1", price=100.0, recommend=False, product_url=None, details=None):
    from sourcing_schema import Option
    return Option(
        sku=sku, vendor="V", price_usd=price, image="",
        reasoning="r", recommend=recommend,
        product_url=product_url, details=details,
    )


def test_fictional_sku_url_search_q_errors():
    """★ option with /search?q= URL should be flagged as error."""
    items = [_i("F1", options=[
        _opt(sku="Thing", price=50, recommend=True,
             product_url="https://example.com/search?q=chrome+faucet"),
    ])]
    findings = check_no_fictional_sku_urls(items, _meta_simple())
    assert any(f.severity == "error" and "F1" in f.message for f in findings)


def test_fictional_sku_url_google_search_errors():
    """★ option pointing at google.com/search should be flagged."""
    items = [_i("F2", options=[
        _opt(sku="Thing", price=50, recommend=True,
             product_url="https://www.google.com/search?q=best+faucet"),
    ])]
    findings = check_no_fictional_sku_urls(items, _meta_simple())
    assert any(f.severity == "error" and "F2" in f.message for f in findings)


def test_fictional_sku_url_real_url_no_error():
    """★ option with a direct product page URL should NOT be flagged."""
    items = [_i("F3", options=[
        _opt(sku="Thing", price=50, recommend=True,
             product_url="https://www.rejuvenation.com/products/westmore-faucet-abc123"),
    ])]
    findings = check_no_fictional_sku_urls(items, _meta_simple())
    assert findings == []


def test_fictional_sku_url_empty_url_no_error():
    """★ option with empty/None product_url should NOT be flagged (no claim made)."""
    items = [_i("F4", options=[
        _opt(sku="Thing", price=50, recommend=True, product_url=None),
        _opt(sku="Other", price=60, recommend=False,
             product_url="https://example.com/search?q=other"),  # non-★, should be ignored
    ])]
    findings = check_no_fictional_sku_urls(items, _meta_simple())
    assert findings == []


# --- Rule 8: per-item budget overshoot ---

def test_per_item_budget_overshoot_within_5pct_no_error():
    """Price exactly at 5% over budget should NOT fire (boundary: > 1.05, not >=)."""
    items = [_i("B1", options=[_opt(price=105.0, recommend=True)])]
    items[0].budget_target_usd = 100.0
    findings = check_per_item_budget_overshoot(items, _meta_simple())
    assert findings == []


def test_per_item_budget_overshoot_over_5pct_errors():
    """Price >5% over budget should fire as error."""
    items = [_i("B2", options=[_opt(price=200.0, recommend=True)])]
    items[0].budget_target_usd = 100.0
    findings = check_per_item_budget_overshoot(items, _meta_simple())
    assert any(f.severity == "error" and "B2" in f.message for f in findings)


def test_per_item_budget_overshoot_approved_overshoot_keyword_suppresses():
    """'approved_overshoot' in notes should suppress the error."""
    items = [_i("B3", options=[_opt(price=200.0, recommend=True)])]
    items[0].budget_target_usd = 100.0
    items[0].notes = "Price confirmed by owner — approved_overshoot per Annika 2026-05-15"
    findings = check_per_item_budget_overshoot(items, _meta_simple())
    assert findings == []


def test_per_item_budget_overshoot_zero_budget_skipped():
    """Items with budget_target_usd == 0 should be skipped entirely."""
    items = [_i("B4", options=[_opt(price=999.0, recommend=True)])]
    items[0].budget_target_usd = 0
    findings = check_per_item_budget_overshoot(items, _meta_simple())
    assert findings == []


# --- Rule 9: orphan SKU refs in notes ---

def test_orphan_sku_refs_missing_token_warns():
    """A notes token matching the model-number heuristic but absent from options SKUs → warning."""
    items = [_i("N1", options=[_opt(sku="REALSKU123", details="some detail")])]
    items[0].notes = "Previously considered OLDSKU-789 but replaced"
    findings = check_no_orphan_sku_refs_in_notes(items, _meta_simple())
    assert any(f.severity == "warning" and "N1" in f.message and "OLDSKU-789" in f.message
               for f in findings)


def test_orphan_sku_refs_present_token_no_warning():
    """A notes token that actually appears in an option's SKU should NOT be flagged."""
    items = [_i("N2", options=[_opt(sku="REALSKU-789", details=None)])]
    items[0].notes = "Using REALSKU-789 per Annika recommendation"
    findings = check_no_orphan_sku_refs_in_notes(items, _meta_simple())
    assert not any("N2" in f.message for f in findings)


def test_orphan_sku_refs_no_notes_no_warning():
    """Item with empty notes should never fire."""
    items = [_i("N3", options=[_opt(sku="THING-001")])]
    items[0].notes = ""
    findings = check_no_orphan_sku_refs_in_notes(items, _meta_simple())
    assert findings == []


# --- Rule 10: collection / landing-page URLs ---

def test_collection_landing_category_path_warns():
    """★ URL containing /category/ should be flagged as a landing page."""
    items = [_i("BB1", options=[
        _opt(sku="Delta T14259-SS", price=500, recommend=True,
             product_url="https://www.deltafaucet.com/category/trinsic"),
    ])]
    findings = check_no_collection_landing_urls(items, _meta_simple())
    assert any(f.severity == "warning" and "BB1" in f.message for f in findings)


def test_collection_landing_collections_path_warns():
    """★ URL containing /collections/ (Shopify-style) should be flagged."""
    items = [_i("BB2", options=[
        _opt(sku="Some Fixture", price=200, recommend=True,
             product_url="https://example.com/collections/bathroom-fixtures"),
    ])]
    findings = check_no_collection_landing_urls(items, _meta_simple())
    assert any(f.severity == "warning" and "BB2" in f.message for f in findings)


def test_collection_landing_specific_product_no_warning():
    """★ URL pointing at a real product page should NOT be flagged."""
    items = [_i("BB3", options=[
        _opt(sku="Delta T14259-SS", price=500, recommend=True,
             product_url="https://www.deltafaucet.com/bathroom/showers/T14259-SS"),
    ])]
    findings = check_no_collection_landing_urls(items, _meta_simple())
    assert findings == []


def test_collection_landing_shallow_path_warns():
    """★ URL with only one path segment (domain/segment) is too shallow for a product page."""
    items = [_i("BB4", options=[
        _opt(sku="Widget", price=100, recommend=True,
             product_url="https://example.com/trinsic"),
    ])]
    findings = check_no_collection_landing_urls(items, _meta_simple())
    assert any(f.severity == "warning" and "BB4" in f.message for f in findings)


def test_collection_landing_empty_url_skipped():
    """★ option with no product_url should not trigger collection-landing check."""
    items = [_i("BB5", options=[
        _opt(sku="Widget", price=100, recommend=True, product_url=None),
    ])]
    findings = check_no_collection_landing_urls(items, _meta_simple())
    assert findings == []


def test_collection_landing_non_recommend_ignored():
    """Non-★ option with landing URL should be ignored."""
    items = [_i("BB6", options=[
        _opt(sku="Widget", price=100, recommend=False,
             product_url="https://example.com/category/all-fixtures"),
    ])]
    findings = check_no_collection_landing_urls(items, _meta_simple())
    assert findings == []


# --- Rule 11: known vendor finishes ---

def test_known_vendor_finishes_cedar_moss_lacquered_warns():
    """Cedar & Moss 'lacquered brass' is not in their known finish set — should warn."""
    items = [_i("CM1", options=[
        _opt(sku="Cedar & Moss Globe Sconce lacquered brass", price=200,
             recommend=True, details="lacquered brass finish"),
    ])]
    items[0].options[0].vendor = "Cedar & Moss"
    findings = check_known_vendor_finishes(items, _meta_simple())
    assert any(f.severity == "warning" and "CM1" in f.message for f in findings)


def test_known_vendor_finishes_cedar_moss_brass_no_warning():
    """Cedar & Moss 'brass' is a known finish — should not warn."""
    items = [_i("CM2", options=[
        _opt(sku="Cedar & Moss Globe Sconce brass", price=200,
             recommend=True, details="brass finish"),
    ])]
    items[0].options[0].vendor = "Cedar & Moss"
    findings = check_known_vendor_finishes(items, _meta_simple())
    assert not any("CM2" in f.message for f in findings)


def test_known_vendor_finishes_rejuvenation_antique_brass_no_warning():
    """Rejuvenation antique brass is known — should not warn."""
    items = [_i("RJ1", options=[
        _opt(sku="Rejuvenation Westmore antique brass", price=150,
             recommend=True, details="antique brass finish"),
    ])]
    items[0].options[0].vendor = "Rejuvenation"
    findings = check_known_vendor_finishes(items, _meta_simple())
    assert not any("RJ1" in f.message for f in findings)


def test_known_vendor_finishes_unknown_vendor_skipped():
    """Vendor not in KNOWN_VENDOR_FINISHES dict should never fire."""
    items = [_i("UK1", options=[
        _opt(sku="SomeBrand Fixture matte antique lacquered", price=300,
             recommend=True, details="lacquered bronze"),
    ])]
    items[0].options[0].vendor = "Unknown Brand Co"
    findings = check_known_vendor_finishes(items, _meta_simple())
    assert findings == []


def test_known_vendor_finishes_no_finish_words_skipped():
    """If option text has no finish-indicating words at all, skip — avoid false positives."""
    items = [_i("CM3", options=[
        _opt(sku="Cedar & Moss Globe Sconce 4-inch", price=200, recommend=True),
    ])]
    items[0].options[0].vendor = "Cedar & Moss"
    findings = check_known_vendor_finishes(items, _meta_simple())
    assert not any("CM3" in f.message for f in findings)


def test_known_vendor_finishes_substring_modifier_not_flagged():
    """Modifier substrings buried inside non-finish words (e.g. 'raw' inside 'Crawford') must
    NOT trigger a finish-vocabulary warning.  Same for 'true' inside 'true price' in details
    prose. These were R6-I3 / R7-I4 false positives."""
    from sourcing_schema import Option
    # 'raw' is a substring of 'Crawford' — must not fire
    opt_raw = Option(
        sku="Rejuvenation Crawford Single Wall Sconce — Lacquered Brass",
        vendor="Rejuvenation", price_usd=200.0, image="",
        reasoning="r", recommend=True,
        details="Crawford lacquered brass, hardwire, pair",
    )
    items_raw = [_i("RAW1", options=[opt_raw])]
    findings_raw = check_known_vendor_finishes(items_raw, _meta_simple())
    assert not any("RAW1" in f.message for f in findings_raw), \
        f"'raw' inside 'Crawford' must not fire vendor-finish warning; got: {findings_raw}"

    # 'true' inside 'true price' (sentinel-style prose) must not fire either
    opt_true = Option(
        sku="Rejuvenation Massey Single Hook — Natural Brass",
        vendor="Rejuvenation", price_usd=225.0, image="",
        reasoning="r", recommend=True,
        details="true price would be $295. natural brass finish.",
    )
    items_true = [_i("TRUE1", options=[opt_true])]
    findings_true = check_known_vendor_finishes(items_true, _meta_simple())
    assert not any("TRUE1" in f.message for f in findings_true), \
        f"bare 'true' word in details prose must not fire vendor-finish warning; got: {findings_true}"


# --- Rule 8 extended: decided items with budget but no priced option ---

def test_per_item_budget_decided_no_options_info():
    """Decided item with budget but no options array should emit info (price unverifiable)."""
    items = [_i("HB1", decided_sku="Waterworks Henry Tub Filler HB-12345")]
    items[0].budget_target_usd = 500.0
    items[0].decision_status = "decided"
    findings = check_per_item_budget_overshoot(items, _meta_simple())
    assert any(f.severity == "info" and "HB1" in f.message for f in findings)


def test_per_item_budget_decided_no_options_approved_suppressed():
    """approved_overshoot keyword in notes should suppress the info finding for decided items."""
    items = [_i("HB2", decided_sku="Waterworks Henry Tub Filler HB-12345")]
    items[0].budget_target_usd = 500.0
    items[0].decision_status = "decided"
    items[0].notes = "Confirmed by owner — approved_overshoot per Annika"
    findings = check_per_item_budget_overshoot(items, _meta_simple())
    assert not any("HB2" in f.message for f in findings)


def test_per_item_budget_decided_zero_budget_skipped():
    """Decided item with budget_target_usd == 0 should be skipped entirely."""
    items = [_i("HB3", decided_sku="Some Faucet SKU-999")]
    items[0].budget_target_usd = 0.0
    items[0].decision_status = "decided"
    findings = check_per_item_budget_overshoot(items, _meta_simple())
    assert not any("HB3" in f.message for f in findings)


# --- R6: sentinel words in orphan-SKU check ---

def test_orphan_sku_sentinel_words_not_flagged():
    """CONFIRM, OWNER, DEFER etc. must NOT be flagged as orphan SKU references."""
    items = [_i("SN1", options=[_opt(sku="REALSKU-123")])]
    items[0].notes = "CONFIRM with OWNER before ordering. DEFER to VERIFY pricing. APPROVED by Annika. GREENGUARD required."
    findings = check_no_orphan_sku_refs_in_notes(items, _meta_simple())
    # None of the sentinel tokens should appear in findings for SN1
    assert not any("SN1" in f.message for f in findings)


def test_orphan_sku_item_id_cross_ref_not_flagged():
    """Notes referencing another item's ID (e.g. K-SINK) should not be flagged as orphan."""
    item_a = _i("K-SINK", options=[_opt(sku="RUVATI-7300")])
    item_b = _i("K-RO-FAUCET", options=[_opt(sku="AQ-SFRO2-BN")])
    item_b.notes = "Depends on K-SINK installation. Coordinate with K-SINK plumber."
    findings = check_no_orphan_sku_refs_in_notes([item_a, item_b], _meta_simple())
    # K-SINK cross-reference in notes should NOT fire as orphan
    assert not any("K-SINK" in f.message for f in findings)


def test_orphan_sku_real_orphan_still_flagged():
    """A genuine orphan (old SKU removed from options but still in notes) should still flag."""
    items = [_i("OR1", options=[_opt(sku="NEWSKU-999")])]
    items[0].notes = "Previously was OLDSKU-789 but swapped out in R4."
    findings = check_no_orphan_sku_refs_in_notes(items, _meta_simple())
    assert any("OR1" in f.message and "OLDSKU-789" in f.message for f in findings)


# --- Catalog status callouts ---

def test_catalog_status_callouts_none_returns_no_findings():
    items = [_i("X1", decided_sku="A")]
    assert check_catalog_status_callouts(items, _meta()) == []


def test_catalog_status_needs_reselection_warns():
    item = _i("X1", decided_sku="A")
    item.catalog_status = "needs_reselection"
    item.catalog_status_note = "vendor discontinued"
    findings = check_catalog_status_callouts([item], _meta())
    assert len(findings) == 1
    assert findings[0].severity == "warning"
    assert "CATALOG GAP" in findings[0].message
    assert "vendor discontinued" in findings[0].message


def test_catalog_status_spec_error_warns():
    item = _i("X2", decided_sku="A")
    item.catalog_status = "spec_error"
    findings = check_catalog_status_callouts([item], _meta())
    assert len(findings) == 1
    assert findings[0].severity == "warning"
    assert "SPEC ERROR" in findings[0].message


def test_catalog_status_verified_is_info_severity():
    item = _i("X3", decided_sku="A")
    item.catalog_status = "verified"
    findings = check_catalog_status_callouts([item], _meta())
    assert len(findings) == 1
    assert findings[0].severity == "info"
    assert "VERIFIED" in findings[0].message


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
    # Directory-level findings (item_id=None) come from supplier_directory.yaml
    # which lives outside this test's control — they may exist on the developer's
    # machine. We assert only item-level findings (item_id != None) are empty.
    item_level = [f for f in findings if f.item_id is not None]
    assert item_level == []
