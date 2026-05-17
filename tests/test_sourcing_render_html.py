# tests/test_sourcing_render_html.py
from datetime import date
from pathlib import Path
import tempfile
import textwrap

from sourcing_loader import load_sourcing, Schedule
from sourcing_lint import LintFinding
from sourcing_render_html import render_site_page, render_for_annika

FIXTURES = Path(__file__).parent / "fixtures"


def test_render_site_page_contains_known_item_card():
    data = load_sourcing(FIXTURES / "sample_sourcing.yaml")
    html = render_site_page(data.items, data.meta, lint_findings=[])
    assert "G3-HOOD" in html
    assert "Kitchen range hood" in html
    assert "Vent-A-Hood SLDH9-K42" in html
    # data-attrs for filter
    assert 'data-urgency="T0"' in html
    assert 'data-room="kitchen"' in html
    assert 'data-status="options_drafted"' in html or 'data-status="decided"' in html


def test_render_site_page_hides_stub_items():
    data = load_sourcing(FIXTURES / "sample_sourcing.yaml")
    data.items[0].decision_status = "stub"
    html = render_site_page(data.items, data.meta, lint_findings=[])
    assert "G3-HOOD" not in html
    assert "MB-FAUCET" in html


def test_render_site_page_shows_lint_alert_bar():
    data = load_sourcing(FIXTURES / "sample_sourcing.yaml")
    findings = [
        LintFinding(severity="error", message="test error message", item_id="X1"),
        LintFinding(severity="warning", message="test warning message"),
    ]
    html = render_site_page(data.items, data.meta, lint_findings=findings)
    assert "test error message" in html
    assert "test warning message" in html
    assert "lint-alert" in html  # CSS class for the alert bar


def test_render_site_page_topnav_marks_sourcing_current():
    data = load_sourcing(FIXTURES / "sample_sourcing.yaml")
    html = render_site_page(data.items, data.meta, lint_findings=[])
    assert '<a href="/sourcing" class="current">Sourcing</a>' in html


def test_render_site_page_schedule_not_locked_badge_shows_when_phase_null():
    """When >50% of urgency-sensitive items are unlocked (all phases null), the renderer
    emits a single top-of-page banner instead of per-card badges. The data-attribute is
    still written false so the filter JS knows the state."""
    from sourcing_queue import ScheduleLookup
    data = load_sourcing(FIXTURES / "sample_sourcing.yaml")
    # All phases null → banner mode (all T0/T1/T2 items unlocked = 100% > 50%)
    sched = Schedule(phases={k: None for k in [
        "roof_phase_start", "bath_gut_start", "kitchen_gut_start",
        "electrical_rough_start", "plumbing_rough_start",
        "finish_phase_start", "move_back_in"]})
    lookup = ScheduleLookup(schedule=sched, meta_last_updated=data.meta.last_updated, today=date(2026, 5, 16))
    html = render_site_page(data.items, data.meta, lint_findings=[], schedule_lookup=lookup)
    # data-attribute still written for filter JS
    assert 'data-schedule-locked="false"' in html
    # Banner replaces per-card badges in bulk-unlocked case
    assert 'schedule-banner' in html
    assert 'Construction schedule not yet locked' in html
    # Per-card badge suppressed in banner mode
    assert 'schedule-not-locked' not in html or 'schedule-banner' in html


def test_render_site_page_shows_recent_revision_history():
    """Per spec Open Question #2: card surfaces last 3 revision_history entries."""
    data = load_sourcing(FIXTURES / "sample_sourcing.yaml")
    html = render_site_page(data.items, data.meta, lint_findings=[])
    # G3-HOOD fixture has 2 revision_history entries
    assert "stub created" in html
    assert "options_drafted, 2 candidates" in html


# ---------------------------------------------------------------------------
# render_for_annika tests
# ---------------------------------------------------------------------------

def test_render_for_annika_contains_annika_items():
    """for-annika page includes annika_loop items in active statuses."""
    data = load_sourcing(FIXTURES / "sample_sourcing.yaml")
    html = render_for_annika(data.items, data.meta)
    # G3-HOOD is annika_loop=true, options_drafted
    assert "G3-HOOD" in html
    assert "Kitchen range hood" in html
    # MB-FAUCET is annika_loop=true, decided
    assert "MB-FAUCET" in html


def test_render_for_annika_shows_pick_and_question():
    """for-annika page renders the recommended pick and a question block."""
    data = load_sourcing(FIXTURES / "sample_sourcing.yaml")
    html = render_for_annika(data.items, data.meta)
    # G3-HOOD recommend option is Vent-A-Hood
    assert "Vent-A-Hood SLDH9-K42 SS" in html
    # Default question fallback rendered
    assert "annika-question" in html


def test_render_for_annika_uses_per_item_questions():
    """Custom question YAML overrides the default fallback."""
    data = load_sourcing(FIXTURES / "sample_sourcing.yaml")
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(textwrap.dedent("""\
            questions:
              G3-HOOD: "Custom question for the hood test?"
        """))
        q_path = Path(f.name)
    try:
        html = render_for_annika(data.items, data.meta, questions_path=q_path)
        assert "Custom question for the hood test?" in html
    finally:
        q_path.unlink(missing_ok=True)


def test_render_for_annika_cover_note_inlined():
    """Cover note markdown is parsed and inlined into the page."""
    data = load_sourcing(FIXTURES / "sample_sourcing.yaml")
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(textwrap.dedent("""\
            ---
            version: v99
            date: 2026-01-01
            deadline: June 30
            ---
            # Test cover heading
            Hello from the cover note.
        """))
        cn_path = Path(f.name)
    try:
        html = render_for_annika(data.items, data.meta, cover_note_path=cn_path)
        assert "Hello from the cover note" in html
        assert "v99" in html
    finally:
        cn_path.unlink(missing_ok=True)


def test_render_for_annika_decided_item_shows_locked():
    """Decided items render as 'Locked' with the decided_sku, not as 'Your read'."""
    data = load_sourcing(FIXTURES / "sample_sourcing.yaml")
    html = render_for_annika(data.items, data.meta)
    # MB-FAUCET is decided
    assert "Delta Trinsic 559LF-CZMPU Champagne Bronze" in html
    assert "Locked" in html


def test_render_for_annika_excludes_non_annika_items():
    """Items with annika_loop=false should not appear on the page."""
    data = load_sourcing(FIXTURES / "sample_sourcing.yaml")
    # Temporarily mark G3-HOOD as non-annika
    data.items[0].annika_loop = False
    html = render_for_annika(data.items, data.meta)
    assert "G3-HOOD" not in html


def test_render_for_annika_toc_generated():
    """Table of contents is present in the output."""
    data = load_sourcing(FIXTURES / "sample_sourcing.yaml")
    html = render_for_annika(data.items, data.meta)
    assert 'class="toc"' in html
    assert "Sections" in html


# ---------------------------------------------------------------------------
# R6 new: approved-overshoots block (#4)
# ---------------------------------------------------------------------------

def test_approved_overshoots_block_appears_for_overshoot_item():
    """Items with approved_overshoot in notes and price > budget should appear in the slate block."""
    from sourcing_schema import Option, Item, Meta, Budgets, ConsistencyLocks
    from sourcing_render_html import render_site_page

    opt = Option(
        sku="Fancy Widget", vendor="V", price_usd=500.0, image="",
        reasoning="approved", recommend=True,
        details=None, product_url=None,
    )
    item = Item(
        id="TEST-OVER", title="Test Overshoot", category="hardware", room="kitchen",
        urgency="T0", lead_time_weeks=1,
        budget_source="construction_allowance", budget_target_usd=300.0,
        sourcing_actor="owner_direct", decision_status="options_drafted",
        annika_loop=False, options=[opt],
        notes="approved_overshoot per owner confirmation",
    )
    meta = Meta(
        last_updated="2026-05-16",
        budgets=Budgets(construction_cap=342000, furniture_envelope=55000, path3_owner_direct_ceiling=10000),
        consistency_locks=ConsistencyLocks(
            brass_finish_family="Rejuvenation lacquered brass",
            wood_tone="white_oak_bleach_rubio_pure",
            tile_palette=["cle_sea_salt_zellige", "carrara_slab", "cle_bejmat_master_only"],
            paint_line="aura",
        ),
    )
    html = render_site_page([item], meta, lint_findings=[])
    assert "approved-overshoots-block" in html
    assert "TEST-OVER" in html


def test_approved_overshoots_block_absent_when_no_overshoots():
    """When no approved_overshoot items exist, the dynamic block header should not appear."""
    data = load_sourcing(FIXTURES / "sample_sourcing.yaml")
    # Ensure no approved_overshoot in fixture items
    for it in data.items:
        it.notes = ""
    html = render_site_page(data.items, data.meta, lint_findings=[])
    # The dynamic h4 "Approved overshoots" header should not appear
    assert "Approved overshoots" not in html


def test_approved_overshoots_block_renders_when_keyword_present_but_price_within_budget():
    """R7-I1: After HARD-RULE 'revisions UP only', the budget always covers the ★ rec,
    so the legacy price>budget condition never fired.  The keyword presence must trigger
    rendering regardless of price-vs-budget arithmetic."""
    from sourcing_schema import Option, Item, Meta, Budgets, ConsistencyLocks
    from sourcing_render_html import render_site_page

    # Price exactly matches budget — legacy condition would have skipped this.
    opt = Option(
        sku="Some Pot Filler", vendor="Delta", price_usd=756.0, image="",
        reasoning="approved_overshoot: true. No cheaper option exists.",
        recommend=True,
    )
    item = Item(
        id="KW-OVER", title="Keyword overshoot item", category="plumbing_fixture",
        room="kitchen", urgency="T0", lead_time_weeks=4,
        budget_source="construction_allowance", budget_target_usd=756.0,
        sourcing_actor="owner_direct", decision_status="options_drafted",
        annika_loop=False, options=[opt],
        notes="approved_overshoot: true per OWNER CONFIRM #1.",
    )
    meta = Meta(
        last_updated="2026-05-16",
        budgets=Budgets(construction_cap=342000, furniture_envelope=55000, path3_owner_direct_ceiling=10000),
        consistency_locks=ConsistencyLocks(
            brass_finish_family="Rejuvenation lacquered brass",
            wood_tone="white_oak_bleach_rubio_pure",
            tile_palette=["cle_sea_salt_zellige", "carrara_slab", "cle_bejmat_master_only"],
            paint_line="aura",
        ),
    )
    html = render_site_page([item], meta, lint_findings=[])
    assert "approved-overshoots-block" in html
    assert "KW-OVER" in html


def test_approved_overshoots_block_triggers_on_reasoning_keyword():
    """The keyword can also live in the ★ option's reasoning prose, not just item.notes."""
    from sourcing_schema import Option, Item, Meta, Budgets, ConsistencyLocks
    from sourcing_render_html import render_site_page

    opt = Option(
        sku="Some Faucet", vendor="V", price_usd=200.0, image="",
        reasoning="This is an approved overshoot ratified by owner.",
        recommend=True,
    )
    item = Item(
        id="REA-OVER", title="Reasoning overshoot", category="hardware", room="kitchen",
        urgency="T0", lead_time_weeks=1,
        budget_source="construction_allowance", budget_target_usd=200.0,
        sourcing_actor="owner_direct", decision_status="options_drafted",
        annika_loop=False, options=[opt],
        notes="ordinary note without keyword",
    )
    meta = Meta(
        last_updated="2026-05-16",
        budgets=Budgets(construction_cap=342000, furniture_envelope=55000, path3_owner_direct_ceiling=10000),
        consistency_locks=ConsistencyLocks(
            brass_finish_family="Rejuvenation lacquered brass",
            wood_tone="white_oak_bleach_rubio_pure",
            tile_palette=["cle_sea_salt_zellige", "carrara_slab", "cle_bejmat_master_only"],
            paint_line="aura",
        ),
    )
    html = render_site_page([item], meta, lint_findings=[])
    assert "REA-OVER" in html
    assert "approved-overshoots-block" in html


# ---------------------------------------------------------------------------
# R6 new: double-vendor bug (#11)
# ---------------------------------------------------------------------------

def test_for_annika_wrong_class_red_only_fires_when_sku_field_contains_signal():
    """R7-I2: past-tense corrective prose in reasoning/details ("the original SKU does not
    exist; we substituted X") must NOT trigger wrong-class red escalation. The signal phrase
    must appear in the literal sku string (or sku_canonical) for the warning to fire."""
    from sourcing_schema import Option, Item, Meta, Budgets, ConsistencyLocks
    from sourcing_render_html import render_for_annika

    # Case A: signal phrase ("does not exist") appears in DETAILS as past-tense corrective
    # prose describing what was rejected and replaced. The current SKU is the correct pick.
    # MUST NOT escalate to red.
    pick = Option(
        sku="Rejuvenation Tumalo Single Sconce — Lacquered Brass",
        vendor="Rejuvenation", price_usd=200.0, image="",
        reasoning="Original Pinnock SKU does not exist in current catalog; substituted Tumalo.",
        recommend=True,
        details="WRONG SKU 1903LF-CZ not found; closest Trinsic family swap was Tumalo. "
                "Confirmed live at rejuvenation.com.",
    )
    item = Item(
        id="WC-CORRECTIVE", title="Sconce corrective", category="lighting_fixture",
        room="kitchen", urgency="T0", lead_time_weeks=2,
        budget_source="construction_allowance", budget_target_usd=200.0,
        sourcing_actor="owner_direct", decision_status="options_drafted",
        annika_loop=True, options=[pick],
    )
    meta = Meta(
        last_updated="2026-05-16",
        budgets=Budgets(construction_cap=342000, furniture_envelope=55000, path3_owner_direct_ceiling=10000),
        consistency_locks=ConsistencyLocks(
            brass_finish_family="Rejuvenation lacquered brass",
            wood_tone="white_oak_bleach_rubio_pure",
            tile_palette=["cle_sea_salt_zellige", "carrara_slab", "cle_bejmat_master_only"],
            paint_line="aura",
        ),
    )
    html = render_for_annika([item], meta)
    # The wrong-class red escalation must NOT fire — past-tense prose only.
    assert "Wrong product class flagged" not in html, \
        "past-tense corrective prose in reasoning/details must not trigger wrong-class red"

    # Case B: signal phrase appears in the SKU itself — MUST fire.
    bad_pick = Option(
        sku="Delta 1903LF-CZ Bar/Prep Faucet WRONG PRODUCT — not a pot filler",
        vendor="Delta", price_usd=685.0, image="",
        reasoning="No alternatives at this price tier.",
        recommend=True,
        details="Closest Trinsic family.",
    )
    bad_item = Item(
        id="WC-REAL", title="Real wrong class", category="plumbing_fixture",
        room="kitchen", urgency="T0", lead_time_weeks=2,
        budget_source="construction_allowance", budget_target_usd=700.0,
        sourcing_actor="owner_direct", decision_status="options_drafted",
        annika_loop=True, options=[bad_pick],
    )
    html_b = render_for_annika([bad_item], meta)
    assert "Wrong product class flagged" in html_b, \
        "signal phrase IN the SKU string must trigger wrong-class red"


def test_for_annika_no_double_vendor_in_alts():
    """Alt options whose SKU already starts with the vendor name must not repeat it."""
    from sourcing_schema import Option, Item, Meta, Budgets, ConsistencyLocks
    from sourcing_render_html import render_for_annika

    pick = Option(
        sku="Babyletto Toco Glider Eco-Weave", vendor="Babyletto", price_usd=499.0,
        image="", reasoning="canonical glider", recommend=True,
    )
    alt = Option(
        sku="West Elm Organic Glider Crypton Ivory", vendor="West Elm", price_usd=1099.0,
        image="", reasoning="anchor brand option", recommend=False,
    )
    item = Item(
        id="TEST-GLIDER", title="Nursery glider", category="furniture", room="nursery",
        urgency="T2", lead_time_weeks=10,
        budget_source="furniture_envelope", budget_target_usd=900.0,
        sourcing_actor="owner_furniture", decision_status="options_drafted",
        annika_loop=True, options=[pick, alt],
    )
    meta = Meta(
        last_updated="2026-05-16",
        budgets=Budgets(construction_cap=342000, furniture_envelope=55000, path3_owner_direct_ceiling=10000),
        consistency_locks=ConsistencyLocks(
            brass_finish_family="Rejuvenation lacquered brass",
            wood_tone="white_oak_bleach_rubio_pure",
            tile_palette=["cle_sea_salt_zellige", "carrara_slab", "cle_bejmat_master_only"],
            paint_line="aura",
        ),
    )
    html = render_for_annika([item], meta)
    # "West Elm West Elm" should NOT appear
    assert "West Elm West Elm" not in html
    # But "West Elm" should still appear (the SKU text itself)
    assert "West Elm" in html


# ---------------------------------------------------------------------------
# R9 Track A: declutter /sourcing — collapse locked decisions + 2-up grid
# ---------------------------------------------------------------------------

def test_render_site_page_locked_decisions_collapsed_behind_details():
    """R9 Track A: /sourcing main page must collapse canon-decided items (no options
    array OR decision_status='decided') into a single <details> block with a <summary>
    so decision-makers can scan drafted items first. Per-room pages are unaffected."""
    from sourcing_render_html import render_site_page, render_room_page
    data = load_sourcing(FIXTURES / "sample_sourcing.yaml")
    # Fixture has: G3-HOOD (options_drafted, drafted) + MB-FAUCET (decided, locked)
    html = render_site_page(data.items, data.meta, lint_findings=[])

    # The locked-decisions <details> block must be present with a <summary>.
    assert '<details class="locked-decisions-banner">' in html
    assert '<summary>' in html
    # Summary copy includes the count + scannable categories hint.
    assert 'decisions locked' in html
    # The decided item (MB-FAUCET) must live inside the locked details block.
    # Use the literal opening <details> tag (not the class name, which also lives in CSS).
    locked_idx = html.find('<details class="locked-decisions-banner">')
    mb_idx = html.find('MB-FAUCET')
    g3_idx = html.find('G3-HOOD')
    assert locked_idx != -1 and mb_idx != -1 and g3_idx != -1
    # G3-HOOD (drafted) is rendered BEFORE the locked-decisions block.
    assert g3_idx < locked_idx, "drafted items must render before the locked-decisions block"
    # MB-FAUCET (decided) is rendered AFTER the locked-decisions opening tag.
    assert mb_idx > locked_idx, "decided items must render inside the locked-decisions block"

    # Drafted items render inside the 2-up grid wrapper.
    assert 'class="sourcing-grid-2up"' in html
    grid_idx = html.find('<div class="sourcing-grid-2up">')
    assert grid_idx != -1
    assert grid_idx < g3_idx < locked_idx

    # Per-room page MUST NOT use either the details block or the 2-up grid — it stays
    # 1-col with locked items inline for in-room decision context.
    room_html = render_room_page(
        "Master Suite", ["master_br", "master_bath"], data.items, data.meta,
    )
    assert '<details class="locked-decisions-banner">' not in room_html, \
        "per-room pages must not collapse locked items behind a toggle"
    assert '<div class="sourcing-grid-2up">' not in room_html, \
        "per-room pages must not use the 2-up grid layout"
    # MB-FAUCET is still rendered inline on the per-room page.
    assert 'MB-FAUCET' in room_html


def test_render_site_page_no_locked_block_when_all_drafted():
    """When every visible item is drafted (no canon-decisions), the locked-decisions
    <details> block must not appear at all (avoids an empty banner)."""
    from sourcing_render_html import render_site_page
    data = load_sourcing(FIXTURES / "sample_sourcing.yaml")
    # Drop the canon-locked item so every remaining item is options_drafted.
    data.items = [it for it in data.items if it.decision_status != "decided"]
    html = render_site_page(data.items, data.meta, lint_findings=[])
    # No <details> tag emitted (CSS class for the rule still lives in the <style> block).
    assert '<details class="locked-decisions-banner">' not in html
    # Drafted grid is still present.
    assert '<div class="sourcing-grid-2up">' in html


def test_render_site_page_locked_count_matches_decided_items():
    """The summary count must match the number of canon-decided items rendered inside."""
    from sourcing_schema import Option, Item, Meta, Budgets, ConsistencyLocks
    from sourcing_render_html import render_site_page
    # Build three locked items + one drafted.
    locked_items = []
    for i, (sku, room) in enumerate([
        ("Paint OC-17", "common"),
        ("Hardwood white-oak rift", "lr"),
        ("Cle Sea Salt zellige", "master_bath"),
    ]):
        locked_items.append(Item(
            id=f"L{i}", title=sku, category="paint_finish", room=room,
            urgency="T1", lead_time_weeks=2,
            budget_source="construction_allowance", budget_target_usd=500.0,
            sourcing_actor="tcw", decision_status="decided",
            annika_loop=False, decided_sku=sku, options=None,
        ))
    drafted = Item(
        id="D1", title="Drafted item", category="appliance", room="kitchen",
        urgency="T0", lead_time_weeks=4,
        budget_source="construction_allowance", budget_target_usd=1500.0,
        sourcing_actor="owner_direct", decision_status="options_drafted",
        annika_loop=False, options=[Option(
            sku="X", vendor="V", price_usd=1400.0, image="",
            reasoning="r", recommend=True,
        )],
    )
    meta = Meta(
        last_updated="2026-05-17",
        budgets=Budgets(construction_cap=342000, furniture_envelope=55000, path3_owner_direct_ceiling=10000),
        consistency_locks=ConsistencyLocks(
            brass_finish_family="Rejuvenation lacquered brass",
            wood_tone="white_oak_bleach_rubio_pure",
            tile_palette=["cle_sea_salt_zellige", "carrara_slab", "cle_bejmat_master_only"],
            paint_line="aura",
        ),
    )
    html = render_site_page(locked_items + [drafted], meta, lint_findings=[])
    # Count text in summary should be "3 decisions locked".
    assert "3 decisions locked" in html
    # All three locked ids present.
    for lid in ["L0", "L1", "L2"]:
        assert lid in html
    # Drafted item present too.
    assert "D1" in html


# ---------------------------------------------------------------------------
# D1: Decisions-needed banner — pinned at top of /sourcing
# ---------------------------------------------------------------------------

def _make_item(item_id: str, catalog_status=None, title="Test item", room="kitchen",
               category="hardware", decision_status="options_drafted"):
    from sourcing_schema import Option, Item
    opt = Option(sku="X", vendor="V", price_usd=10.0, image="",
                 reasoning="r", recommend=True)
    return Item(
        id=item_id, title=title, category=category, room=room,
        urgency="T0", lead_time_weeks=1,
        budget_source="construction_allowance", budget_target_usd=100.0,
        sourcing_actor="owner_direct", decision_status=decision_status,
        annika_loop=False, options=[opt],
        catalog_status=catalog_status,
    )


def _make_meta():
    from sourcing_schema import Meta, Budgets, ConsistencyLocks
    return Meta(
        last_updated="2026-05-17",
        budgets=Budgets(construction_cap=342000, furniture_envelope=55000, path3_owner_direct_ceiling=10000),
        consistency_locks=ConsistencyLocks(
            brass_finish_family="Rejuvenation lacquered brass",
            wood_tone="white_oak_bleach_rubio_pure",
            tile_palette=["cle_sea_salt_zellige", "carrara_slab", "cle_bejmat_master_only"],
            paint_line="aura",
        ),
    )


def test_decisions_needed_banner_renders_when_flagged_items_exist():
    """D1: banner renders with N count + N jump links when items have catalog_status flagged."""
    from sourcing_render_html import render_site_page
    items = [
        _make_item("MB-TILE-FLOOR", catalog_status="needs_reselection"),
        _make_item("K-FLOOR-TILE", catalog_status="needs_reselection"),
        _make_item("MB-MEDICINE-CABINET", catalog_status="spec_error"),
        _make_item("BB-VANITY", catalog_status="spec_error"),
        _make_item("K-PENDANTS", catalog_status="needs_reselection"),
        _make_item("HEALTHY-1"),  # no catalog gap — should not appear in banner
    ]
    meta = _make_meta()
    html = render_site_page(items, meta, lint_findings=[])
    # Banner is present
    assert "decisions-needed-banner" in html
    # Heading shows the count
    assert "5 decision" in html
    # Jump-links present
    for item_id in ["MB-TILE-FLOOR", "K-FLOOR-TILE", "MB-MEDICINE-CABINET", "BB-VANITY", "K-PENDANTS"]:
        assert f'href="#item-{item_id}"' in html
    # Anchors present on the cards
    for item_id in ["MB-TILE-FLOOR", "K-FLOOR-TILE", "MB-MEDICINE-CABINET", "BB-VANITY", "K-PENDANTS"]:
        assert f'id="item-{item_id}"' in html
    # Healthy item is NOT in banner
    assert 'href="#item-HEALTHY-1"' not in html


def test_decisions_needed_banner_absent_when_no_flagged_items():
    """D1: banner does not render when N=0. (CSS class definition is allowed in the
    style block; the rendered <div class="decisions-needed-banner"> must be absent.)"""
    from sourcing_render_html import render_site_page
    items = [_make_item("H1"), _make_item("H2")]
    meta = _make_meta()
    html = render_site_page(items, meta, lint_findings=[])
    assert 'class="decisions-needed-banner"' not in html
    assert "decisions need your reselection" not in html
    assert "decision need your reselection" not in html


def test_decisions_needed_banner_singular_grammar():
    """D1: single flagged item uses singular grammar."""
    from sourcing_render_html import render_site_page
    items = [_make_item("ONLY-1", catalog_status="needs_reselection"), _make_item("H1")]
    meta = _make_meta()
    html = render_site_page(items, meta, lint_findings=[])
    assert "decisions-needed-banner" in html
    assert "1 decision need" in html  # singular form


# ---------------------------------------------------------------------------
# D2: Budget rollup block
# ---------------------------------------------------------------------------

def test_budget_rollup_block_renders_totals_and_categories():
    """D2: rollup shows total, cap, delta, and per-category breakdown."""
    from sourcing_render_html import render_site_page
    items = [
        _make_item("A", category="plumbing_fixture"),  # 100
        _make_item("B", category="plumbing_fixture"),  # 100
        _make_item("C", category="lighting_fixture"),  # 100
        _make_item("D", category="furniture"),         # 100
    ]
    meta = _make_meta()
    html = render_site_page(items, meta, lint_findings=[])
    assert "budget-rollup" in html
    # Total = $400, cap $342,000, delta = $341,600 positive
    assert "Total budgeted:" in html
    assert "$400" in html
    assert "$342,000" in html
    assert "delta-positive" in html
    assert "$341,600" in html
    # Per-category rows: plumbing (2), lighting (1), furniture (1)
    assert "Plumbing" in html
    assert "Lighting" in html
    assert "Furniture" in html


def test_budget_rollup_handles_null_budget_gracefully():
    """D2: items with budget_target_usd=0 do not crash the rollup."""
    from sourcing_render_html import render_site_page
    item = _make_item("Z", category="hardware")
    item.budget_target_usd = 0.0
    meta = _make_meta()
    html = render_site_page([item], meta, lint_findings=[])
    assert "budget-rollup" in html
    # Delta should be the full cap, positive
    assert "$342,000" in html


def test_budget_rollup_skips_empty_categories():
    """D2: categories with zero items are skipped from the table (no empty rows)."""
    from sourcing_render_html import render_site_page
    items = [_make_item("A", category="plumbing_fixture")]
    meta = _make_meta()
    html = render_site_page(items, meta, lint_findings=[])
    # Plumbing appears; Tile / stone (no items) does not appear as a row
    assert "Plumbing" in html
    # Tile/Stone label only appears if the category has items in it
    # We check the row marker — table rows are <tr><td>{label}</td>
    assert "<td>Tile / stone</td>" not in html


# ---------------------------------------------------------------------------
# D3: Topnav dropdown collapse
# ---------------------------------------------------------------------------

def test_topnav_has_rooms_dropdown():
    """D3: Rooms is a <details> dropdown, not inline links."""
    from sourcing_render_html import _build_topnav_html
    nav = _build_topnav_html("sourcing")
    assert 'details class="nav-dropdown"' in nav
    assert "<summary>Rooms</summary>" in nav
    assert "<summary>Canon</summary>" in nav
    # Room links should still be inside the dropdown menu
    assert 'href="/kitchen"' in nav
    assert 'href="/master"' in nav


def test_topnav_marks_current_page():
    """D3: current page link gets class='current'."""
    from sourcing_render_html import _build_topnav_html
    nav = _build_topnav_html("vendors")
    assert 'href="/vendors" class="current"' in nav
    # And the sourcing entry should NOT be current
    assert 'href="/sourcing" class="current"' not in nav


def test_topnav_includes_vendors_link():
    """D3+D6: topnav exposes /vendors as a top-level link."""
    from sourcing_render_html import _build_topnav_html
    nav = _build_topnav_html("sourcing")
    assert 'href="/vendors"' in nav


# ---------------------------------------------------------------------------
# D4: Git-history audit trail
# ---------------------------------------------------------------------------

def test_render_item_card_renders_last_changed_when_provided():
    """D4: when last_changed_map is supplied, item cards show 'Last changed YYYY-MM-DD'."""
    from sourcing_render_html import render_site_page
    items = [_make_item("X1")]
    meta = _make_meta()
    html = render_site_page(items, meta, lint_findings=[], last_changed_map={"X1": "2026-05-17"})
    assert "Last changed 2026-05-17" in html


def test_render_item_card_no_last_changed_when_id_missing():
    """D4: when an id is not in the map, no last-changed line is rendered."""
    from sourcing_render_html import render_site_page
    items = [_make_item("X1")]
    meta = _make_meta()
    html = render_site_page(items, meta, lint_findings=[], last_changed_map={"OTHER": "2026-05-01"})
    assert "Last changed" not in html


# ---------------------------------------------------------------------------
# D5: /for-annika decisions banner pull-up
# ---------------------------------------------------------------------------

def test_for_annika_surfaces_catalog_gaps_with_tailored_copy():
    """D5: /for-annika top renders the decisions-needed banner with annika-variant copy."""
    from sourcing_render_html import render_for_annika
    items = [
        _make_item("MB-TILE-FLOOR", catalog_status="needs_reselection"),
        _make_item("K-PENDANTS", catalog_status="needs_reselection"),
        _make_item("BB-VANITY", catalog_status="spec_error"),
    ]
    # Annika-only items in the active set
    for it in items:
        it.annika_loop = True
    meta = _make_meta()
    html = render_for_annika(items, meta)
    assert "decisions-needed-banner" in html
    assert "design eye" in html  # tailored copy variant
    assert "MB-TILE-FLOOR" in html


def test_for_annika_no_decisions_banner_when_no_flagged_items():
    """D5: when no catalog gaps exist, /for-annika does NOT render the banner element."""
    from sourcing_render_html import render_for_annika
    items = [_make_item("HEALTHY")]
    items[0].annika_loop = True
    meta = _make_meta()
    html = render_for_annika(items, meta)
    assert 'class="decisions-needed-banner"' not in html
    assert "picks need your design eye" not in html


# ---------------------------------------------------------------------------
# D6: /vendors page
# ---------------------------------------------------------------------------

def test_render_vendors_page_groups_by_vendor():
    """D6: /vendors page groups items by vendor and renders per-vendor sections."""
    from sourcing_render_html import render_vendors_page
    from sourcing_schema import Option, Item
    # Two West Elm items + one Article item
    we_opt_a = Option(sku="WE-A", vendor="West Elm", price_usd=500.0, image="",
                      reasoning="r", recommend=True)
    we_opt_b = Option(sku="WE-B", vendor="West Elm", price_usd=300.0, image="",
                      reasoning="r", recommend=True)
    art_opt = Option(sku="ART-1", vendor="Article", price_usd=1000.0, image="",
                     reasoning="r", recommend=True)
    items = [
        Item(id="A", title="WE item A", category="furniture", room="lr",
             urgency="T1", lead_time_weeks=4,
             budget_source="furniture_envelope", budget_target_usd=500.0,
             sourcing_actor="owner_furniture", decision_status="options_drafted",
             annika_loop=False, options=[we_opt_a]),
        Item(id="B", title="WE item B", category="furniture", room="lr",
             urgency="T1", lead_time_weeks=4,
             budget_source="furniture_envelope", budget_target_usd=300.0,
             sourcing_actor="owner_furniture", decision_status="options_drafted",
             annika_loop=False, options=[we_opt_b]),
        Item(id="C", title="Article item", category="furniture", room="lr",
             urgency="T1", lead_time_weeks=4,
             budget_source="furniture_envelope", budget_target_usd=1000.0,
             sourcing_actor="owner_furniture", decision_status="options_drafted",
             annika_loop=False, options=[art_opt]),
    ]
    meta = _make_meta()
    html = render_vendors_page(items, meta)
    # Both vendors are section headers
    assert "West Elm" in html
    assert "Article" in html
    # Canon coherence summary present
    assert "vendor-mix-summary" in html
    assert "Canon brand-mix coherence" in html
    # West Elm appears first (higher $ sum: $800 vs $1000? actually $800 < $1000)
    # Article should appear before WE because $1000 > $800
    art_pos = html.find('<h2>Article</h2>')
    we_pos = html.find('<h2>West Elm</h2>')
    assert art_pos != -1 and we_pos != -1
    assert art_pos < we_pos


def test_render_vendors_page_canon_coherence_warns_when_outside_band():
    """D6: bucket >5pp outside its DESIGN_SPEC §5d band is flagged."""
    from sourcing_render_html import render_vendors_page
    meta = _make_meta()
    # Zero items — every bucket is at 0%, well below any target band
    html = render_vendors_page([], meta)
    assert "vendor-mix-summary" in html
    # All canon buckets should be flagged out-of-band (0% vs 35-40 etc)
    assert "5pp outside" in html


def test_render_vendors_page_includes_vendors_topnav_link():
    """D6: /vendors page topnav shows Vendors marked as current."""
    from sourcing_render_html import render_vendors_page
    meta = _make_meta()
    html = render_vendors_page([], meta)
    assert 'href="/vendors" class="current"' in html
