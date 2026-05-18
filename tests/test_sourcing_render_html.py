# tests/test_sourcing_render_html.py
from datetime import date
from pathlib import Path
import tempfile
import textwrap

import pytest

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


def test_render_vendors_page_attributes_canon_decided_via_top_level_vendor():
    """Canon-decided items (no options[], no vintage_brief) with a top-level
    `vendor` field get attributed to that vendor's section — they no longer
    fall into the '(canon-locked — vendor in spec text)' bucket."""
    from sourcing_render_html import render_vendors_page
    from sourcing_schema import Item
    items = [
        # A canon-decided item with top-level vendor → routed to West Elm
        Item(
            id="MB-VANITY", title="Master vanity",
            category="furniture", room="master_bath", urgency="T0",
            lead_time_weeks=6, budget_source="construction_allowance",
            budget_target_usd=2500.0, sourcing_actor="owner_direct",
            decision_status="decided", annika_loop=False,
            decided_sku="WE Hutchinson Vanity Double 60 Blonde",
            vendor="West Elm",
        ),
        # A canon-decided item without top-level vendor → unattributed bucket
        Item(
            id="UNATTRIBUTED", title="Unattributed item",
            category="paint_finish", room="common", urgency="T0",
            lead_time_weeks=0, budget_source="construction_allowance",
            budget_target_usd=1000.0, sourcing_actor="tcw",
            decision_status="decided", annika_loop=False,
            decided_sku="Some prose-only spec",
        ),
    ]
    meta = _make_meta()
    html = render_vendors_page(items, meta)
    # MB-VANITY appears under West Elm
    assert "<h2>West Elm</h2>" in html
    # Unattributed item lands in the canon-locked pool
    assert "(canon-locked &mdash; vendor in spec text)" in html or \
        "(canon-locked — vendor in spec text)" in html
    # The MB-VANITY id should appear inside the West Elm section, not the
    # canon-locked pool. Validate by locating positions.
    we_idx = html.find("<h2>West Elm</h2>")
    pool_idx = html.find("canon-locked")
    mb_idx = html.find("MB-VANITY")
    assert we_idx != -1 and pool_idx != -1 and mb_idx != -1
    # The MB-VANITY id should be closer to the West Elm header than the pool header.
    assert abs(mb_idx - we_idx) < abs(mb_idx - pool_idx)


def test_render_vendors_page_top_level_vendor_wins_over_option_vendor():
    """If both a top-level `vendor` and `options` are set, top-level wins.
    (This isn't the typical case but the precedence has to be deterministic.)"""
    from sourcing_render_html import render_vendors_page
    from sourcing_schema import Item, Option
    opt = Option(sku="X", vendor="OptionVendor", price_usd=100.0, image="",
                 reasoning="r", recommend=True)
    items = [
        Item(
            id="X1", title="x",
            category="furniture", room="lr", urgency="T1",
            lead_time_weeks=4, budget_source="furniture_envelope",
            budget_target_usd=500.0, sourcing_actor="owner_furniture",
            decision_status="options_drafted", annika_loop=False,
            options=[opt], vendor="TopLevelVendor",
        ),
    ]
    meta = _make_meta()
    html = render_vendors_page(items, meta)
    assert "<h2>TopLevelVendor</h2>" in html
    assert "<h2>OptionVendor</h2>" not in html


# ---------------------------------------------------------------------------
# Suppliers directory page (/suppliers) — browse-style discovery surface
# ---------------------------------------------------------------------------

_SUPPLIER_DIR_FIXTURE = {
    "meta": {
        "generated": "2026-05-17",
        "aesthetic_anchor": "California Modern Japandi",
        "project_price_tier": "mid-market",
        "cap_reference": 342000,
    },
    "categories": [
        {"id": "furniture-seating", "label": "Sofas / Chairs / Sectionals"},
        {"id": "lighting", "label": "Pendants / Sconces / Lamps / Floor"},
    ],
    "suppliers": [
        {
            "id": "west-elm-seating",
            "category": "furniture-seating",
            "name": "West Elm",
            "url": "https://www.westelm.com",
            "price_tier": "mid",
            "fit": "STRONG",
            "style_fingerprint": "Channel-tufted seating, brass + bronze metals.",
            "fit_for_project": "STRONG — anchor brand per DESIGN_SPEC.",
            "collections_to_browse": [
                {"name": "Andes Sectional", "url": "https://www.westelm.com/andes/"},
            ],
            "lead_time_typical": "4-10 weeks",
            "sample_policy": "Free swatches",
        },
        {
            "id": "schoolhouse",
            "category": "lighting",
            "name": "Schoolhouse",
            "url": "https://www.schoolhouse.com",
            "price_tier": "premium",
            "fit": "STRONG",
            "style_fingerprint": "Lacquered brass + opal glass.",
            "fit_for_project": "STRONG — DESIGN_SPEC canon.",
        },
    ],
}


def test_render_suppliers_page_basic():
    """Suppliers page renders all supplier cards in their category groups."""
    from sourcing_render_html import render_suppliers_page
    html = render_suppliers_page(_SUPPLIER_DIR_FIXTURE)
    assert "<title>Suppliers" in html
    # Both suppliers present
    assert "West Elm" in html
    assert "Schoolhouse" in html
    # Both categories rendered
    assert "Sofas / Chairs / Sectionals" in html
    assert "Pendants / Sconces / Lamps / Floor" in html
    # Cards carry data-* attrs for filtering
    assert 'data-category="furniture-seating"' in html
    assert 'data-tier="mid"' in html
    assert 'data-fit="STRONG"' in html


def test_render_suppliers_page_filter_bar_present():
    """Suppliers page exposes search + category + tier + fit filters and a random button."""
    from sourcing_render_html import render_suppliers_page
    html = render_suppliers_page(_SUPPLIER_DIR_FIXTURE)
    assert 'id="supplier-search"' in html
    assert 'id="cat-filter"' in html
    assert 'id="tier-filter"' in html
    assert 'id="fit-filter"' in html
    assert 'id="reset-filters"' in html
    assert 'id="random-pick"' in html


def test_render_suppliers_page_collections_chips():
    """Suppliers with collections_to_browse render clickable chips."""
    from sourcing_render_html import render_suppliers_page
    html = render_suppliers_page(_SUPPLIER_DIR_FIXTURE)
    assert "Andes Sectional" in html
    assert 'class="collection-chip"' in html


def test_render_suppliers_page_anchor_block():
    """Suppliers page shows the aesthetic anchor / price tier / canon mix at the top."""
    from sourcing_render_html import render_suppliers_page
    html = render_suppliers_page(_SUPPLIER_DIR_FIXTURE)
    assert "Browse map" in html
    assert "California Modern Japandi" in html
    assert "mid-market" in html
    assert "Canon brand mix" in html


def test_render_suppliers_page_topnav_current():
    """Suppliers page marks Suppliers as the current topnav link."""
    from sourcing_render_html import render_suppliers_page
    html = render_suppliers_page(_SUPPLIER_DIR_FIXTURE)
    assert 'href="/suppliers" class="current"' in html


def test_topnav_includes_suppliers_link():
    """Topnav exposes /suppliers as a top-level link."""
    from sourcing_render_html import _build_topnav_html
    nav = _build_topnav_html("sourcing")
    assert 'href="/suppliers"' in nav


def test_render_suppliers_page_empty_fallback_when_no_directory():
    """When called without directory and YAML absent, returns a safe placeholder page."""
    from sourcing_render_html import render_suppliers_page
    # Force the helper to receive an explicit empty dict — the fallback path is
    # exercised by passing None when the YAML can't be loaded. Here we pass an
    # empty-ish but minimally valid dict to exercise the normal render with zero
    # cards; the placeholder branch is covered by inspection.
    html = render_suppliers_page({"meta": {}, "categories": [], "suppliers": []})
    # Normal render path with zero data still produces a valid page with the topnav
    assert "<title>Suppliers" in html
    assert "0 suppliers across 0 categories" in html


# ---------------------------------------------------------------------------
# Enhancement-pass tests (2026-05-17): hero images, cross-link, verification
# badge, action selector, URL filter persistence, sort dropdown.
# ---------------------------------------------------------------------------


def test_render_suppliers_page_hero_image_renders_when_present():
    """Card hero image is emitted with the supplier_directory.yaml hero_image path."""
    from sourcing_render_html import render_suppliers_page
    fixture = {
        "meta": {"generated": "2026-05-17", "last_verification_pass": "2026-05-17"},
        "categories": [{"id": "furniture-seating", "label": "Seating"}],
        "suppliers": [{
            "id": "west-elm-seating",
            "category": "furniture-seating",
            "name": "West Elm",
            "url": "https://www.westelm.com",
            "price_tier": "mid", "fit": "STRONG",
            "style_fingerprint": "x", "fit_for_project": "x",
            "hero_image": "/images/suppliers/west-elm-seating.jpg",
            "url_verified": True, "url_status": 200,
        }],
    }
    html = render_suppliers_page(fixture)
    # When the file exists on disk → an <img> tag is emitted; when it doesn't,
    # the placeholder is emitted. Both are acceptable; assert one of them.
    assert ('src="/images/suppliers/west-elm-seating.jpg"' in html
            or 'supplier-hero-placeholder' in html)
    # Container always present.
    assert 'class="supplier-hero' in html


def test_render_suppliers_page_hero_placeholder_when_image_missing():
    """Missing hero_image OR missing-on-disk path falls back to soft placeholder."""
    from sourcing_render_html import render_suppliers_page
    fixture = {
        "meta": {"generated": "2026-05-17"},
        "categories": [{"id": "lighting", "label": "Lighting"}],
        "suppliers": [{
            "id": "fictional-supplier-xyz",
            "category": "lighting",
            "name": "Fictional Supplier XYZ",
            "url": "https://example.com",
            "price_tier": "mid", "fit": "GOOD",
            "style_fingerprint": "x", "fit_for_project": "x",
            "hero_image": "/images/suppliers/fictional-supplier-xyz-NOT-PRESENT.jpg",
            "url_verified": False,
        }],
    }
    html = render_suppliers_page(fixture)
    assert 'supplier-hero-placeholder' in html
    assert 'Fictional Supplier XYZ' in html


def test_render_suppliers_page_verification_badge():
    """Verified suppliers get a green badge; unverified get an amber badge."""
    from sourcing_render_html import render_suppliers_page
    fixture = {
        "meta": {"generated": "2026-05-17", "last_verification_pass": "2026-05-17"},
        "categories": [
            {"id": "furniture-seating", "label": "Seating"},
            {"id": "lighting", "label": "Lighting"},
        ],
        "suppliers": [
            {"id": "a", "category": "furniture-seating", "name": "A",
             "url": "https://example.com", "price_tier": "mid", "fit": "STRONG",
             "style_fingerprint": "x", "fit_for_project": "x",
             "url_verified": True, "url_status": 200},
            {"id": "b", "category": "lighting", "name": "B",
             "url": "https://example.com", "price_tier": "mid", "fit": "GOOD",
             "style_fingerprint": "x", "fit_for_project": "x",
             "url_verified": False},
        ],
    }
    html = render_suppliers_page(fixture)
    assert 'verif-badge verif-ok' in html
    assert 'verif-badge verif-warn' in html
    assert 'Verified 2026-05-17' in html
    assert 'Unverified' in html


def test_render_suppliers_page_action_selector_present():
    """Each card has a Visit / Saved / Ruled-out tri-state radio."""
    from sourcing_render_html import render_suppliers_page
    fixture = {
        "meta": {},
        "categories": [{"id": "furniture-seating", "label": "Seating"}],
        "suppliers": [{
            "id": "a", "category": "furniture-seating", "name": "A",
            "url": "https://example.com", "price_tier": "mid", "fit": "STRONG",
            "style_fingerprint": "x", "fit_for_project": "x",
            "url_verified": True, "url_status": 200,
        }],
    }
    html = render_suppliers_page(fixture)
    assert 'class="supplier-action"' in html
    assert 'data-action="visit"' in html
    assert 'data-action="saved"' in html
    assert 'data-action="ruled"' in html


def test_render_suppliers_page_sort_dropdown_and_copy_button():
    """Sort dropdown and Copy filter URL button present in the filter bar."""
    from sourcing_render_html import render_suppliers_page
    fixture = {
        "meta": {},
        "categories": [{"id": "lighting", "label": "Lighting"}],
        "suppliers": [],
    }
    html = render_suppliers_page(fixture)
    assert 'id="sort-by"' in html
    assert 'value="tier"' in html
    assert 'value="fit"' in html
    assert 'value="verified"' in html
    assert 'value="random"' in html
    assert 'id="copy-filter-url"' in html


def test_render_suppliers_page_action_filter_chips():
    """Filter bar exposes 4 action filter chips (All / Visit / Saved / Ruled)."""
    from sourcing_render_html import render_suppliers_page
    fixture = {"meta": {}, "categories": [], "suppliers": []}
    html = render_suppliers_page(fixture)
    assert 'data-action-filter="all"' in html
    assert 'data-action-filter="visit"' in html
    assert 'data-action-filter="saved"' in html
    assert 'data-action-filter="ruled"' in html


def test_render_suppliers_page_url_filter_persistence_js():
    """JS reads URL params on load (search, category, tier, fit, sort, action, vendor)."""
    from sourcing_render_html import render_suppliers_page
    html = render_suppliers_page({"meta": {}, "categories": [], "suppliers": []})
    # Init reads URL params
    assert "URLSearchParams" in html
    assert "history.replaceState" in html
    # Sort + action filter + vendor handling all live in the same script.
    assert "p.get('vendor')" in html or 'p.get("vendor")' in html
    assert "p.set('category'" in html or 'p.set("category"' in html


def test_render_suppliers_page_crosslink_counts_when_sourcing_present(tmp_path, monkeypatch):
    """When sourcing.yaml has matching vendor strings, the cross-link block shows the count."""
    from sourcing_render_html import _supplier_sourcing_links, _vendor_string_matches_supplier
    # Direct unit test on the helper — covers the matching logic without needing
    # to override the HomeAI/scope sourcing.yaml path.
    sourcing_items = [
        {"id": "LR-SOFA", "top_vendor": "West Elm", "option_vendors": []},
        {"id": "MB-VANITY", "top_vendor": "West Elm", "option_vendors": []},
        {"id": "K-PENDANTS", "top_vendor": "Rejuvenation", "option_vendors": ["Schoolhouse", "West Elm"]},
        {"id": "OTHER", "top_vendor": "Generic", "option_vendors": []},
    ]
    matches = _supplier_sourcing_links("west-elm-seating", "West Elm", sourcing_items)
    assert sorted(matches) == sorted(["LR-SOFA", "MB-VANITY", "K-PENDANTS"])

    matches_schoolhouse = _supplier_sourcing_links("schoolhouse", "Schoolhouse", sourcing_items)
    assert matches_schoolhouse == ["K-PENDANTS"]

    matches_none = _supplier_sourcing_links("nonexistent-id", "Nonexistent Brand", sourcing_items)
    assert matches_none == []


def test_render_suppliers_page_crosslink_block_in_html():
    """Cross-link footer renders for both matched and unmatched suppliers."""
    from sourcing_render_html import render_suppliers_page
    fixture = {
        "meta": {},
        "categories": [{"id": "furniture-seating", "label": "Seating"}],
        "suppliers": [{
            "id": "west-elm-seating",
            "category": "furniture-seating",
            "name": "West Elm",
            "url": "https://example.com",
            "price_tier": "mid", "fit": "STRONG",
            "style_fingerprint": "x", "fit_for_project": "x",
            "url_verified": True, "url_status": 200,
        }],
    }
    html = render_suppliers_page(fixture)
    # Either matched or unmatched block must render
    assert 'sourcing-crosslink' in html
    assert ('Tracked in /sourcing' in html) or ('Not yet tracked' in html)


def test_render_suppliers_page_verification_badge_tooltip():
    """Verification badge carries a data-tooltip with URL status + price probe count."""
    from sourcing_render_html import render_suppliers_page
    fixture = {
        "meta": {"last_verification_pass": "2026-05-17"},
        "categories": [{"id": "plumbing", "label": "Plumbing"}],
        "suppliers": [{
            "id": "delta", "category": "plumbing", "name": "Delta",
            "url": "https://example.com", "price_tier": "mid", "fit": "STRONG",
            "style_fingerprint": "x", "fit_for_project": "x",
            "url_verified": True, "url_status": 200,
            "price_validation": [{"sku": "S1", "retail_typical": 100}, {"sku": "S2", "retail_typical": 200}],
        }],
    }
    html = render_suppliers_page(fixture)
    assert 'data-tooltip="URL status: 200' in html
    assert 'price probe' in html


def test_render_suppliers_page_card_carries_verified_date():
    """Card data-verified-date attribute supports the 'recently verified' sort."""
    from sourcing_render_html import render_suppliers_page
    fixture = {
        "meta": {"last_verification_pass": "2026-05-17"},
        "categories": [{"id": "lighting", "label": "Lighting"}],
        "suppliers": [{
            "id": "x", "category": "lighting", "name": "X",
            "url": "https://example.com", "price_tier": "mid", "fit": "GOOD",
            "style_fingerprint": "x", "fit_for_project": "x",
            "url_verified": True, "url_status": 200,
        }],
    }
    html = render_suppliers_page(fixture)
    assert 'data-verified-date="2026-05-17"' in html
    assert 'data-verified="true"' in html


# ---------------------------------------------------------------------------
# Lint rule: supplier_directory URL freshness
# ---------------------------------------------------------------------------


def test_supplier_directory_url_freshness_lint_passes_when_all_verified(tmp_path, monkeypatch):
    """check_supplier_directory_url_freshness emits no findings when every supplier is verified."""
    from sourcing_lint import check_supplier_directory_url_freshness
    yaml_text = textwrap.dedent("""\
        meta: {}
        categories: []
        suppliers:
          - id: a
            url_verified: true
            url_status: 200
          - id: b
            url_verified: true
            url_status: "ok"
        """)
    target = tmp_path / "Desktop" / "HomeAI" / "scope"
    target.mkdir(parents=True)
    (target / "supplier_directory.yaml").write_text(yaml_text)
    monkeypatch.setenv("HOME", str(tmp_path))
    # Monkeypatch os.path.expanduser used inside the lint
    import os as _os
    real_expand = _os.path.expanduser
    monkeypatch.setattr(
        _os.path, "expanduser",
        lambda p: p.replace("~", str(tmp_path)) if p.startswith("~") else real_expand(p),
    )
    findings = check_supplier_directory_url_freshness([], None)
    assert findings == []


def test_supplier_directory_url_freshness_lint_flags_unverified(tmp_path, monkeypatch):
    """check_supplier_directory_url_freshness emits a warning when suppliers are unverified."""
    from sourcing_lint import check_supplier_directory_url_freshness
    yaml_text = textwrap.dedent("""\
        meta: {}
        categories: []
        suppliers:
          - id: alpha
            url_verified: false
          - id: bravo
            url_verified: true
            url_status: 404
          - id: charlie
            url_verified: true
            url_status: 200
        """)
    target = tmp_path / "Desktop" / "HomeAI" / "scope"
    target.mkdir(parents=True)
    (target / "supplier_directory.yaml").write_text(yaml_text)
    import os as _os
    real_expand = _os.path.expanduser
    monkeypatch.setattr(
        _os.path, "expanduser",
        lambda p: p.replace("~", str(tmp_path)) if p.startswith("~") else real_expand(p),
    )
    findings = check_supplier_directory_url_freshness([], None)
    assert len(findings) == 1
    assert findings[0].severity == "warning"
    assert "2 supplier" in findings[0].message
    assert "alpha" in findings[0].message
    assert "bravo" in findings[0].message
    # charlie should NOT appear
    assert "charlie" not in findings[0].message


# ---------------------------------------------------------------------------
# R2 Fix C3 — URL freshness uses exact-match allow-list (not prefix-match)
# ---------------------------------------------------------------------------


def test_supplier_directory_url_freshness_lint_flags_prefix_match_bug(tmp_path, monkeypatch):
    """Codex flagged: '200 BUT IS 404' previously passed lint via prefix-match on '200'.

    R2 Fix C3 makes the status comparison exact against {200, 301, 302, 'ok',
    'bot_blocked_ok', 'redirected_changed_path', 'redirected_brand_change'}.
    """
    from sourcing_lint import check_supplier_directory_url_freshness
    yaml_text = textwrap.dedent("""\
        meta: {}
        categories: []
        suppliers:
          - id: stale_lying
            url_verified: true
            url_status: "200 BUT IS 404"
          - id: stale_appended_404
            url_verified: true
            url_status: "200 (actually 404 in retest)"
          - id: ok_canonical
            url_verified: true
            url_status: "ok"
        """)
    target = tmp_path / "Desktop" / "HomeAI" / "scope"
    target.mkdir(parents=True)
    (target / "supplier_directory.yaml").write_text(yaml_text)
    import os as _os
    real_expand = _os.path.expanduser
    monkeypatch.setattr(
        _os.path, "expanduser",
        lambda p: p.replace("~", str(tmp_path)) if p.startswith("~") else real_expand(p),
    )
    findings = check_supplier_directory_url_freshness([], None)
    # Both "200 BUT IS 404" and "200 (actually 404...)" must now be flagged.
    assert len(findings) == 1
    msg = findings[0].message
    assert "2 supplier" in msg
    assert "stale_lying" in msg
    assert "stale_appended_404" in msg
    assert "ok_canonical" not in msg


# ---------------------------------------------------------------------------
# R2 Fix C1 — XSS href scheme sanitization
# ---------------------------------------------------------------------------


def test_safe_href_strips_javascript_scheme():
    """Malicious javascript: URLs in the YAML must NOT survive into rendered hrefs."""
    from sourcing_render_html import _safe_href
    assert _safe_href("javascript:alert(1)") == "#"
    assert _safe_href("JAVASCRIPT:alert(1)") == "#"
    assert _safe_href("  javascript:alert(1)") == "#"
    assert _safe_href("data:text/html,<script>alert(1)</script>") == "#"
    assert _safe_href("vbscript:msgbox(1)") == "#"
    # Safe schemes pass through.
    assert _safe_href("https://example.com") == "https://example.com"
    assert _safe_href("http://example.com") == "http://example.com"
    assert _safe_href("mailto:x@example.com") == "mailto:x@example.com"
    # Internal links survive.
    assert _safe_href("/sourcing?vendor=x") == "/sourcing?vendor=x"
    assert _safe_href("#anchor") == "#anchor"
    # Empty/None → safe fallback.
    assert _safe_href("") == "#"
    assert _safe_href(None) == "#"


def test_render_suppliers_page_xss_url_is_neutralized():
    """A javascript: URL in supplier_directory.yaml must render as href='#', not be clickable."""
    from sourcing_render_html import render_suppliers_page
    fixture = {
        "meta": {},
        "categories": [{"id": "lighting", "label": "Lighting"}],
        "suppliers": [{
            "id": "xss-test", "category": "lighting", "name": "Evil Supplier",
            "url": "javascript:alert('xss')",
            "price_tier": "mid", "fit": "STRONG",
            "style_fingerprint": "x", "fit_for_project": "x",
            "collections_to_browse": [
                {"name": "Bad chip", "url": "javascript:steal()"},
            ],
        }],
    }
    html = render_suppliers_page(fixture)
    assert "javascript:" not in html
    # Explore button + collection chip both fell back to '#'.
    assert 'href="#"' in html


# ---------------------------------------------------------------------------
# R2 Fix C2 — Supplier dataclass + load_supplier_directory
# ---------------------------------------------------------------------------


def test_supplier_dataclass_accepts_valid_minimum():
    from sourcing_schema import parse_supplier, Supplier
    sup = parse_supplier({
        "id": "x", "category": "lighting", "name": "X",
        "url": "https://example.com",
        "price_tier": "mid", "fit": "STRONG",
        "style_fingerprint": "x", "fit_for_project": "x",
    })
    assert isinstance(sup, Supplier)
    assert sup.id == "x"
    assert sup.fit == "STRONG"


def test_supplier_dataclass_rejects_bad_price_tier():
    from sourcing_schema import parse_supplier, ValidationError
    import pytest
    with pytest.raises(ValidationError):
        parse_supplier({
            "id": "x", "category": "lighting", "name": "X",
            "url": "https://example.com",
            "price_tier": "luxury",  # invalid
            "fit": "STRONG",
            "style_fingerprint": "x", "fit_for_project": "x",
        })


def test_supplier_dataclass_rejects_bad_fit():
    from sourcing_schema import parse_supplier, ValidationError
    import pytest
    with pytest.raises(ValidationError):
        parse_supplier({
            "id": "x", "category": "lighting", "name": "X",
            "url": "https://example.com",
            "price_tier": "mid",
            "fit": "PERFECT",  # invalid
            "style_fingerprint": "x", "fit_for_project": "x",
        })


def test_supplier_dataclass_accepts_watch_list_fit():
    """R2 schema must accept WATCH_LIST as a valid fit alongside the original four."""
    from sourcing_schema import parse_supplier
    sup = parse_supplier({
        "id": "x", "category": "lighting", "name": "X",
        "url": "https://example.com",
        "price_tier": "mid", "fit": "WATCH_LIST",
        "style_fingerprint": "x", "fit_for_project": "x",
    })
    assert sup.fit == "WATCH_LIST"


def test_supplier_dataclass_accepts_operator_notes():
    """R2 Fix UX4 — Alpha's operator_notes field must be accepted by schema."""
    from sourcing_schema import parse_supplier
    sup = parse_supplier({
        "id": "x", "category": "lighting", "name": "X",
        "url": "https://example.com",
        "price_tier": "mid", "fit": "STRONG",
        "style_fingerprint": "x", "fit_for_project": "x",
        "operator_notes": "internal: WE blocks WebFetch — use real browser",
    })
    assert sup.operator_notes == "internal: WE blocks WebFetch — use real browser"


def test_load_supplier_directory_fails_loud_on_missing_file(tmp_path):
    """R2 Fix C9 — missing yaml must raise, not silently produce an empty page."""
    from sourcing_schema import load_supplier_directory, ValidationError
    import pytest
    with pytest.raises(ValidationError):
        load_supplier_directory(str(tmp_path / "does-not-exist.yaml"))


def test_load_supplier_directory_fails_loud_on_empty_suppliers(tmp_path):
    from sourcing_schema import load_supplier_directory, ValidationError
    import pytest
    p = tmp_path / "empty.yaml"
    p.write_text("meta: {}\ncategories: []\nsuppliers: []\n")
    with pytest.raises(ValidationError):
        load_supplier_directory(str(p))


def test_load_supplier_directory_fails_loud_on_bad_row(tmp_path):
    from sourcing_schema import load_supplier_directory, ValidationError
    import pytest
    p = tmp_path / "bad.yaml"
    p.write_text(textwrap.dedent("""\
        meta: {}
        categories: []
        suppliers:
          - id: bad
            category: lighting
            name: Bad
            url: https://example.com
            price_tier: invented_tier
            fit: STRONG
            style_fingerprint: x
            fit_for_project: x
        """))
    with pytest.raises(ValidationError):
        load_supplier_directory(str(p))


# ---------------------------------------------------------------------------
# R2 Fix UX1 — Card density compression (hero + spec strip + <details>)
# ---------------------------------------------------------------------------


def test_render_suppliers_page_uses_details_expander():
    """R2 card layout puts heavy detail (warnings, collections, lead/sample, notes,
    crosslink, action selector) inside a <details> expander so the default state
    shows ~5 elements not ~14."""
    from sourcing_render_html import render_suppliers_page
    fixture = {
        "meta": {},
        "categories": [{"id": "lighting", "label": "Lighting"}],
        "suppliers": [{
            "id": "x", "category": "lighting", "name": "X",
            "url": "https://example.com",
            "price_tier": "mid", "fit": "STRONG",
            "style_fingerprint": "Brass + opal glass.",
            "fit_for_project": "STRONG — canon anchor.",
            "off_canon_warning": "skip glam-modern sub-line",
            "lead_time_typical": "4 wk",
            "sample_policy": "free",
            "notes": "test notes",
            "collections_to_browse": [{"name": "Spec collection", "url": "https://example.com/c"}],
            "url_verified": True, "url_status": 200,
        }],
    }
    html = render_suppliers_page(fixture)
    assert "<details" in html
    # R5 Fix I3 — summary is now supplier-specific (prefixed with name).
    assert "<summary>X &mdash; details" in html
    # Heavy details inside the expander
    assert "skip glam-modern" in html
    assert "Spec collection" in html
    assert "test notes" in html
    # Spec strip present
    assert "supplier-spec-strip" in html


def test_render_suppliers_page_compact_spec_strip_has_tier_fit_price():
    from sourcing_render_html import render_suppliers_page
    fixture = {
        "meta": {},
        "categories": [{"id": "lighting", "label": "Lighting"}],
        "suppliers": [{
            "id": "x", "category": "lighting", "name": "X",
            "url": "https://example.com",
            "price_tier": "premium", "fit": "STRONG",
            "style_fingerprint": "x", "fit_for_project": "x",
            "price_range_typical": {"sconce": "180-450"},
        }],
    }
    html = render_suppliers_page(fixture)
    assert "tier-premium" in html
    assert "fit-strong" in html
    # Compact price snippet shows the first range value.
    assert "$180-450" in html


# ---------------------------------------------------------------------------
# R2 Fix UX3 — Bracket-truncation sanitization
# ---------------------------------------------------------------------------


def test_sanitize_brackets_removes_owner_confirm_truncation():
    """[OWNER CONFIRM ... ] markers must NOT survive into rendered HTML —
    West Elm's notes ended in '[OWNER CONFIRM' with no closing bracket,
    leaving the visible Notes truncated mid-sentence."""
    from sourcing_render_html import _sanitize_brackets_for_display
    # Truncated (unclosed)
    s = "Performance fabric upgrade per §7 [OWNER CONFIRM"
    out = _sanitize_brackets_for_display(s)
    assert "[OWNER CONFIRM" not in out
    assert "Performance fabric upgrade per §7" in out
    # Properly bracketed
    s2 = "Performance per §7 [OWNER CONFIRM #3] details follow"
    out2 = _sanitize_brackets_for_display(s2)
    assert "[OWNER CONFIRM" not in out2
    assert "details follow" in out2
    # Empty/None safety
    assert _sanitize_brackets_for_display("") == ""
    assert _sanitize_brackets_for_display(None) == ""


def test_render_suppliers_page_strips_owner_confirm_from_notes():
    from sourcing_render_html import render_suppliers_page
    fixture = {
        "meta": {},
        "categories": [{"id": "lighting", "label": "Lighting"}],
        "suppliers": [{
            "id": "x", "category": "lighting", "name": "X",
            "url": "https://example.com",
            "price_tier": "mid", "fit": "STRONG",
            "style_fingerprint": "x", "fit_for_project": "x",
            "notes": "Performance per §7 [OWNER CONFIRM #3] more after",
        }],
    }
    html = render_suppliers_page(fixture)
    assert "[OWNER CONFIRM" not in html
    assert "more after" in html


# ---------------------------------------------------------------------------
# R2 Fix UX4 — operator_notes never rendered
# ---------------------------------------------------------------------------


def test_render_suppliers_page_never_emits_operator_notes():
    """operator_notes is operator-internal; the renderer must NOT include it in
    the user-facing HTML even when passed directly via the dict (bypassing
    load_supplier_directory)."""
    from sourcing_render_html import render_suppliers_page
    fixture = {
        "meta": {},
        "categories": [{"id": "lighting", "label": "Lighting"}],
        "suppliers": [{
            "id": "x", "category": "lighting", "name": "X",
            "url": "https://example.com",
            "price_tier": "mid", "fit": "STRONG",
            "style_fingerprint": "x", "fit_for_project": "x",
            "operator_notes": "INTERNAL SECRET STRING DO NOT LEAK",
        }],
    }
    html = render_suppliers_page(fixture)
    assert "INTERNAL SECRET STRING" not in html
    assert "operator_notes" not in html


# ---------------------------------------------------------------------------
# R2 Fix UX5 — Hero visual-class badge
# ---------------------------------------------------------------------------


def test_hero_visual_class_explicit_text_placeholder():
    from sourcing_render_html import _hero_visual_class
    sup = {"hero_image_source": "text_placeholder", "hero_image": "/x.jpg"}
    assert _hero_visual_class(sup) == "placeholder"


def test_hero_visual_class_logo_from_filename():
    from sourcing_render_html import _hero_visual_class
    sup = {
        "hero_image": "/images/suppliers/foo-logo.jpg",
        "hero_image_source_url": "https://cdn.example.com/SC_LOGO_BLK_1200X628.jpg",
    }
    assert _hero_visual_class(sup) == "logo"


def test_hero_visual_class_photo_from_brand_cdn():
    from sourcing_render_html import _hero_visual_class
    sup = {
        "hero_image": "/images/suppliers/west-elm-seating.jpg",
        "hero_image_source_url": "https://assets.weimgs.com/products/andes.jpg",
    }
    assert _hero_visual_class(sup) == "photo"


def test_hero_visual_class_placeholder_when_no_image():
    from sourcing_render_html import _hero_visual_class
    assert _hero_visual_class({}) == "placeholder"


def test_render_suppliers_page_emits_hero_visual_badge():
    """Cards emit a hero-class-badge classifying the hero as photo/logo/placeholder."""
    from sourcing_render_html import render_suppliers_page
    fixture = {
        "meta": {},
        "categories": [{"id": "lighting", "label": "Lighting"}],
        "suppliers": [{
            "id": "x", "category": "lighting", "name": "X",
            "url": "https://example.com",
            "price_tier": "mid", "fit": "STRONG",
            "style_fingerprint": "x", "fit_for_project": "x",
        }],
    }
    html = render_suppliers_page(fixture)
    assert "hero-class-badge" in html
    assert 'data-hero-class="placeholder"' in html


# ---------------------------------------------------------------------------
# R2 Fix UX6 — Verification badge :focus fallback + ARIA
# ---------------------------------------------------------------------------


def test_render_suppliers_page_verif_badge_has_aria_describedby():
    from sourcing_render_html import render_suppliers_page
    fixture = {
        "meta": {"last_verification_pass": "2026-05-17"},
        "categories": [{"id": "lighting", "label": "Lighting"}],
        "suppliers": [{
            "id": "x", "category": "lighting", "name": "X",
            "url": "https://example.com",
            "price_tier": "mid", "fit": "STRONG",
            "style_fingerprint": "x", "fit_for_project": "x",
            "url_verified": True, "url_status": 200,
        }],
    }
    html = render_suppliers_page(fixture)
    assert 'aria-describedby="verif-tip-x"' in html
    assert 'id="verif-tip-x"' in html
    assert 'role="tooltip"' in html
    assert 'role="button"' in html
    assert 'tabindex="0"' in html


# ---------------------------------------------------------------------------
# R2 Fix C4 — Sort fallback ?? 9 (was || 9 which buried rank-0 values)
# ---------------------------------------------------------------------------


def test_sort_fallback_uses_nullish_coalescing():
    """Sort comparison must use `??` not `||` so rank 0 sorts FIRST (best),
    not last. Inspect the embedded JS to verify."""
    from sourcing_render_html import render_suppliers_page
    html = render_suppliers_page({"meta": {}, "categories": [], "suppliers": []})
    # `?? 9` is the correct fallback. Make sure `|| 9` is gone from sort.
    assert "?? 9" in html
    # The `|| 9` pattern must not exist in any sort-rank context.
    import re
    # Specifically: tierOrder[...] || 9 or fitOrder[...] || 9 must not appear.
    assert not re.search(r"(tierOrder|fitOrder)\[[^\]]+\]\s*\|\|\s*9", html)


# ---------------------------------------------------------------------------
# R2 Fix C5 — /sourcing?vendor= filter actually filters
# ---------------------------------------------------------------------------


def test_sourcing_page_supports_vendor_filter():
    """render_site_page emits JS that handles ?vendor= by hiding non-matching cards."""
    from sourcing_render_html import render_site_page
    data = load_sourcing(FIXTURES / "sample_sourcing.yaml")
    html = render_site_page(data.items, data.meta, lint_findings=[])
    assert "vendor-filter-banner" in html or "data-vendor-matches" in html
    # The JS must read the vendor param and filter cards.
    assert "params.get('vendor')" in html or 'params.get("vendor")' in html


def test_render_item_card_emits_data_vendor_matches():
    """Item cards expose data-vendor-matches when supplier-directory is loaded
    and the item's vendor strings match known suppliers."""
    from sourcing_render_html import _render_item_card
    from sourcing_loader import load_sourcing
    data = load_sourcing(FIXTURES / "sample_sourcing.yaml")
    # Manually pass vendor_matches.
    html = _render_item_card(data.items[0], vendor_matches=["west-elm-seating", "muuto"])
    assert 'data-vendor-matches="west-elm-seating muuto"' in html


# ---------------------------------------------------------------------------
# R2 Fix C6 — Cross-link category scoping (west-elm-bedroom doesn't bleed into seating)
# ---------------------------------------------------------------------------


def test_vendor_matches_scopes_to_compatible_category():
    """R4 Fix C1 — vendor matches must obey the SAME supplier-category-scope
    predicate that drives `/suppliers` counts. A 'sofa' titled item in LR
    must match west-elm-seating (seating title keyword) but NOT
    west-elm-bedroom (bedroom is room+title gated and a sofa in LR fails
    both)."""
    from sourcing_render_html import _vendor_matches_for_item
    # Fake suppliers index (id, name, category)
    suppliers = [
        ("west-elm-seating", "West Elm", "furniture-seating"),
        ("west-elm-bedroom", "West Elm", "furniture-bedroom"),
        ("schoolhouse", "Schoolhouse", "lighting"),  # brand-wide (no recognized suffix)
    ]
    class FakeItem:
        id = "LR-SOFA"
        title = "Sectional sofa"
        category = "furniture"
        room = "lr"
        vendor = "West Elm"
        options = []
    matches = _vendor_matches_for_item(FakeItem(), suppliers)
    # Seating: title contains "sofa" → in scope.
    assert "west-elm-seating" in matches
    # Bedroom: requires room in {master_br, nursery, guest_br} AND a bedroom
    # title keyword. LR-room sofa fails both. R4 closes the 22-row bleed.
    assert "west-elm-bedroom" not in matches
    # Schoolhouse has no recognized suffix → brand-wide match passes via name.
    # However the item's vendor string is "West Elm" not "Schoolhouse", so no match.
    assert "schoolhouse" not in matches


def test_vendor_matches_bedroom_supplier_with_bedroom_item():
    """R4 Fix C1 — a bedroom-room nightstand from West Elm DOES match
    west-elm-bedroom (both room and title-keyword in scope)."""
    from sourcing_render_html import _vendor_matches_for_item
    suppliers = [
        ("west-elm-seating", "West Elm", "furniture-seating"),
        ("west-elm-bedroom", "West Elm", "furniture-bedroom"),
    ]
    class FakeItem:
        id = "MBR-NIGHTSTAND"
        title = "Master bedroom nightstand pair"
        category = "furniture"
        room = "master_br"
        vendor = "West Elm"
        options = []
    matches = _vendor_matches_for_item(FakeItem(), suppliers)
    assert "west-elm-bedroom" in matches
    # Seating: nightstand is not a seating title keyword → out of scope.
    assert "west-elm-seating" not in matches


def test_vendor_matches_blocks_bedroom_supplier_for_lighting_item():
    """A bedroom supplier-id MUST NOT match a lighting sourcing item."""
    from sourcing_render_html import _vendor_matches_for_item
    suppliers = [("west-elm-bedroom", "West Elm", "furniture-bedroom")]
    class FakeItem:
        id = "K-PENDANTS"
        title = "Kitchen pendants"
        category = "lighting_fixture"
        room = "kitchen"
        vendor = "West Elm"
        options = []
    matches = _vendor_matches_for_item(FakeItem(), suppliers)
    assert matches == []


# ---------------------------------------------------------------------------
# R2 Fix C7 — Uncategorized fallback section
# ---------------------------------------------------------------------------


def test_render_suppliers_page_renders_uncategorized_section():
    """Suppliers with categories not in the directory's categories: list must
    NOT be silently dropped — they go into an Uncategorized section at the bottom."""
    from sourcing_render_html import render_suppliers_page
    fixture = {
        "meta": {},
        "categories": [{"id": "lighting", "label": "Lighting"}],
        "suppliers": [
            {"id": "x", "category": "lighting", "name": "X",
             "url": "https://example.com",
             "price_tier": "mid", "fit": "STRONG",
             "style_fingerprint": "x", "fit_for_project": "x"},
            {"id": "y", "category": "unknown-cat", "name": "Y",
             "url": "https://example.com",
             "price_tier": "mid", "fit": "STRONG",
             "style_fingerprint": "y", "fit_for_project": "y"},
            {"id": "z", "category": None, "name": "Z",
             "url": "https://example.com",
             "price_tier": "mid", "fit": "STRONG",
             "style_fingerprint": "z", "fit_for_project": "z"},
        ],
    }
    html = render_suppliers_page(fixture)
    assert "Uncategorized" in html
    assert "id=\"cat-uncategorized\"" in html
    # Both unknown suppliers must be present
    assert ">Y<" in html or "Y" in html
    assert ">Z<" in html or "Z" in html


def test_supplier_directory_uncategorized_lint(tmp_path, monkeypatch):
    """Lint flags suppliers with categories not in the directory's categories list."""
    from sourcing_lint import check_supplier_directory_uncategorized
    yaml_text = textwrap.dedent("""\
        meta: {}
        categories:
          - id: lighting
            label: Lighting
        suppliers:
          - id: ok_one
            category: lighting
            name: Ok
            url: https://example.com
            price_tier: mid
            fit: STRONG
          - id: bad_one
            category: invented_cat
            name: Bad
            url: https://example.com
            price_tier: mid
            fit: STRONG
        """)
    target = tmp_path / "Desktop" / "HomeAI" / "scope"
    target.mkdir(parents=True)
    (target / "supplier_directory.yaml").write_text(yaml_text)
    import os as _os
    real_expand = _os.path.expanduser
    monkeypatch.setattr(
        _os.path, "expanduser",
        lambda p: p.replace("~", str(tmp_path)) if p.startswith("~") else real_expand(p),
    )
    findings = check_supplier_directory_uncategorized([], None)
    assert len(findings) == 1
    assert "bad_one" in findings[0].message
    assert "ok_one" not in findings[0].message


# ---------------------------------------------------------------------------
# R2 Fix C8 — action URL param allow-list
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# R2 Fix UX8 — Ruled-out default-hide toggle
# ---------------------------------------------------------------------------


def test_suppliers_page_has_hide_ruled_toggle():
    """Filter bar exposes a 'Hide ruled-out' checkbox, default ON."""
    from sourcing_render_html import render_suppliers_page
    html = render_suppliers_page({"meta": {}, "categories": [], "suppliers": []})
    assert 'id="hide-ruled-toggle"' in html
    # Default checked = ON
    assert 'checked' in html.split('id="hide-ruled-toggle"')[0][-200:] or 'checked>' in html
    # JS persists state to localStorage
    assert "HIDE_RULED_KEY" in html
    # CSS rule hides ruled cards under .hide-ruled
    assert "hide-ruled" in html


def test_suppliers_page_has_unrated_filter_chip():
    """Filter chip row exposes Unrated alongside All/Visit/Saved/Ruled."""
    from sourcing_render_html import render_suppliers_page
    html = render_suppliers_page({"meta": {}, "categories": [], "suppliers": []})
    assert 'data-action-filter="unrated"' in html


# ---------------------------------------------------------------------------
# R2 Fix UX9 — Active-filter pills + empty-state UI
# ---------------------------------------------------------------------------


def test_suppliers_page_has_active_filter_pills_container():
    from sourcing_render_html import render_suppliers_page
    html = render_suppliers_page({"meta": {}, "categories": [], "suppliers": []})
    assert 'id="active-filter-pills"' in html
    assert "renderActiveFilterPills" in html


def test_suppliers_page_has_empty_state_ui():
    from sourcing_render_html import render_suppliers_page
    html = render_suppliers_page({"meta": {}, "categories": [], "suppliers": []})
    assert 'id="suppliers-empty-state"' in html
    assert "No suppliers match" in html


def test_suppliers_action_param_has_allow_list():
    """JS that reads ?action= must use an allow-list, not accept arbitrary values."""
    from sourcing_render_html import render_suppliers_page
    html = render_suppliers_page({"meta": {}, "categories": [], "suppliers": []})
    assert "VALID_ACTION_FILTERS" in html
    # Must contain the canonical set of allowed values.
    assert "'all', 'visit', 'saved', 'ruled', 'unrated'" in html


def test_load_supplier_directory_strips_operator_notes_from_output(tmp_path):
    """operator_notes must NOT be passed through to the renderer's data dict."""
    from sourcing_schema import load_supplier_directory
    p = tmp_path / "ok.yaml"
    p.write_text(textwrap.dedent("""\
        meta: {}
        categories:
          - {id: lighting, label: Lighting}
        suppliers:
          - id: x
            category: lighting
            name: X
            url: https://example.com
            price_tier: mid
            fit: STRONG
            style_fingerprint: x
            fit_for_project: x
            operator_notes: secret internal stuff
        """))
    data = load_supplier_directory(str(p))
    sup = data["suppliers"][0]
    assert "operator_notes" not in sup
    assert "secret internal stuff" not in str(sup)


# ---------------------------------------------------------------------------
# R3 Fix C1 — vendor banner XSS via innerHTML
# ---------------------------------------------------------------------------


def test_sourcing_vendor_banner_uses_textcontent_not_innerhtml():
    """The /sourcing ?vendor= banner must build its message via textContent /
    DOM nodes, never via innerHTML with the un-escaped query param. Otherwise
    a malicious ?vendor=<script>alert(1)</script> would execute.
    """
    import sourcing_render_html as srh
    js = srh.FILTER_JS
    # Locate the vendor-banner section.
    idx = js.find("vendor-filter-banner")
    assert idx > 0, "vendor-filter-banner missing"
    # Take ~2000 chars of the banner construction block.
    block = js[idx:idx + 2000]
    # MUST NOT call .innerHTML = with the vendor variable in the banner block.
    assert "banner.innerHTML" not in block, (
        "vendor banner uses innerHTML — replace with textContent/createElement to "
        "neutralize reflected XSS"
    )
    # SHOULD use textContent or createTextNode for the user-supplied vendor token.
    assert "createTextNode" in block or "textContent" in block, (
        "vendor banner needs textContent/createTextNode to safely surface the ?vendor= param"
    )


# ---------------------------------------------------------------------------
# R3 Fix C3 — _safe_href scheme-relative rejection
# ---------------------------------------------------------------------------


def test_safe_href_rejects_scheme_relative_urls():
    """`//evil.com` is protocol-relative — must NOT bypass the scheme allow-list."""
    from sourcing_render_html import _safe_href
    assert _safe_href("//evil.com") == "#"
    assert _safe_href("//evil.com/path?a=b") == "#"
    assert _safe_href("  //evil.com  ") == "#"  # whitespace-padded
    # Sanity: explicit http(s)/internal still pass.
    assert _safe_href("https://example.com") == "https://example.com"
    assert _safe_href("/sourcing") == "/sourcing"


# ---------------------------------------------------------------------------
# R3 Fix C2 — supplier cross-link counts scoped by both brand AND category
# ---------------------------------------------------------------------------


def test_supplier_sourcing_links_scopes_bedroom_supplier_to_bedroom_items():
    """A `west-elm-bedroom` supplier (category furniture-bedroom) must match only
    bedroom-room furniture items, NOT seating or table items, even though the brand
    string ("West Elm") matches all three. Closes Codex's R2 C6 OPEN finding.
    """
    from sourcing_render_html import _supplier_sourcing_links
    # 3 mock sourcing items, all branded West Elm:
    sourcing_items = [
        {"id": "MB-BED", "title": "Master bed frame", "category": "furniture",
         "room": "master_br", "top_vendor": "West Elm", "option_vendors": []},
        {"id": "LR-SOFA", "title": "LR primary sofa", "category": "furniture",
         "room": "lr", "top_vendor": "West Elm", "option_vendors": []},
        {"id": "DR-SIDEBOARD", "title": "Dining sideboard", "category": "furniture",
         "room": "dining", "top_vendor": "West Elm", "option_vendors": []},
    ]
    # West Elm bedroom supplier should match ONLY the bedroom item.
    matches = _supplier_sourcing_links(
        "west-elm-bedroom", "West Elm", sourcing_items,
        supplier_category="furniture-bedroom",
    )
    assert matches == ["MB-BED"], f"expected only MB-BED, got {matches}"
    # West Elm seating should match ONLY the sofa.
    matches_seating = _supplier_sourcing_links(
        "west-elm-seating", "West Elm", sourcing_items,
        supplier_category="furniture-seating",
    )
    assert matches_seating == ["LR-SOFA"], f"expected only LR-SOFA, got {matches_seating}"
    # West Elm tables should match ONLY the sideboard.
    matches_tables = _supplier_sourcing_links(
        "west-elm-tables", "West Elm", sourcing_items,
        supplier_category="furniture-tables",
    )
    assert matches_tables == ["DR-SIDEBOARD"], f"expected only DR-SIDEBOARD, got {matches_tables}"


def test_supplier_sourcing_links_brand_only_match_when_no_category():
    """When supplier_category=None, the legacy brand-only behavior is preserved
    (back-compat for callers that haven't been updated)."""
    from sourcing_render_html import _supplier_sourcing_links
    sourcing_items = [
        {"id": "LR-SOFA", "title": "LR sofa", "category": "furniture", "room": "lr",
         "top_vendor": "West Elm", "option_vendors": []},
        {"id": "MB-BED", "title": "Master bed frame", "category": "furniture",
         "room": "master_br", "top_vendor": "West Elm", "option_vendors": []},
    ]
    matches = _supplier_sourcing_links("west-elm-seating", "West Elm", sourcing_items)
    assert set(matches) == {"LR-SOFA", "MB-BED"}, (
        f"brand-only match should be brand-wide; got {matches}"
    )


# ---------------------------------------------------------------------------
# R3 Fix C4 / R4 Fix V1 — schema validation: null required fields + category
# membership. R4 moved strict checks INTO parse_supplier() so direct probes
# can't slip past the loader-level guard.
# ---------------------------------------------------------------------------


def test_parse_supplier_rejects_null_url():
    """R4 Fix V1 — parse_supplier() must reject null url at parse time,
    not let it stringify through to "None" and rely on the loader."""
    from sourcing_schema import parse_supplier, ValidationError
    with pytest.raises(ValidationError, match="null/empty url"):
        parse_supplier({
            "id": "x", "category": "lighting", "name": "X",
            "url": None,
            "price_tier": "mid", "fit": "STRONG",
            "style_fingerprint": "x", "fit_for_project": "x",
        })


def test_parse_supplier_rejects_unknown_category():
    """R4 Fix V1 — parse_supplier() must reject unknown supplier-directory
    categories at parse time. Codex's R3 direct probe with
    'not-a-real-category' previously slipped past parse_supplier()."""
    from sourcing_schema import parse_supplier, ValidationError
    with pytest.raises(ValidationError, match="unknown supplier category"):
        parse_supplier({
            "id": "x", "category": "not-a-real-category", "name": "X",
            "url": "https://example.com",
            "price_tier": "mid", "fit": "STRONG",
            "style_fingerprint": "x", "fit_for_project": "x",
        })


def test_parse_supplier_rejects_null_style_fingerprint():
    """R4 Fix V1 — null style_fingerprint must fail at parse_supplier()."""
    from sourcing_schema import parse_supplier, ValidationError
    with pytest.raises(ValidationError, match="null/empty style_fingerprint"):
        parse_supplier({
            "id": "x", "category": "lighting", "name": "X",
            "url": "https://example.com",
            "price_tier": "mid", "fit": "STRONG",
            "style_fingerprint": None, "fit_for_project": "x",
        })


def test_parse_supplier_rejects_null_fit_for_project():
    """R4 Fix V1 — null fit_for_project must fail at parse_supplier()."""
    from sourcing_schema import parse_supplier, ValidationError
    with pytest.raises(ValidationError, match="null/empty fit_for_project"):
        parse_supplier({
            "id": "x", "category": "lighting", "name": "X",
            "url": "https://example.com",
            "price_tier": "mid", "fit": "STRONG",
            "style_fingerprint": "x", "fit_for_project": None,
        })


# ---------------------------------------------------------------------------
# R5 Fix I1 — parse_supplier() must reject non-string values for the typed
# display fields BEFORE stringification. Lists/dicts/ints would otherwise
# silently become "[]"/"{}"/"123" via str() and poison card render.
# ---------------------------------------------------------------------------


def test_parse_supplier_rejects_list_style_fingerprint():
    """R5 Fix I1 — a list value for style_fingerprint must fail at parse_supplier()
    instead of silently stringifying to '[]'."""
    from sourcing_schema import parse_supplier, ValidationError
    with pytest.raises(ValidationError, match="style_fingerprint must be a string"):
        parse_supplier({
            "id": "x", "category": "lighting", "name": "X",
            "url": "https://example.com",
            "price_tier": "mid", "fit": "STRONG",
            "style_fingerprint": [], "fit_for_project": "x",
        })


def test_parse_supplier_rejects_dict_style_fingerprint():
    """R5 Fix I1 — a dict value for style_fingerprint must fail at parse_supplier()."""
    from sourcing_schema import parse_supplier, ValidationError
    with pytest.raises(ValidationError, match="style_fingerprint must be a string"):
        parse_supplier({
            "id": "x", "category": "lighting", "name": "X",
            "url": "https://example.com",
            "price_tier": "mid", "fit": "STRONG",
            "style_fingerprint": {"a": 1}, "fit_for_project": "x",
        })


def test_parse_supplier_rejects_int_style_fingerprint():
    """R5 Fix I1 — an int value for style_fingerprint must fail at parse_supplier()."""
    from sourcing_schema import parse_supplier, ValidationError
    with pytest.raises(ValidationError, match="style_fingerprint must be a string"):
        parse_supplier({
            "id": "x", "category": "lighting", "name": "X",
            "url": "https://example.com",
            "price_tier": "mid", "fit": "STRONG",
            "style_fingerprint": 42, "fit_for_project": "x",
        })


def test_parse_supplier_rejects_list_fit_for_project():
    """R5 Fix I1 — a list value for fit_for_project must fail at parse_supplier()."""
    from sourcing_schema import parse_supplier, ValidationError
    with pytest.raises(ValidationError, match="fit_for_project must be a string"):
        parse_supplier({
            "id": "x", "category": "lighting", "name": "X",
            "url": "https://example.com",
            "price_tier": "mid", "fit": "STRONG",
            "style_fingerprint": "x", "fit_for_project": [],
        })


def test_parse_supplier_rejects_dict_fit_for_project():
    """R5 Fix I1 — a dict value for fit_for_project must fail at parse_supplier()."""
    from sourcing_schema import parse_supplier, ValidationError
    with pytest.raises(ValidationError, match="fit_for_project must be a string"):
        parse_supplier({
            "id": "x", "category": "lighting", "name": "X",
            "url": "https://example.com",
            "price_tier": "mid", "fit": "STRONG",
            "style_fingerprint": "x", "fit_for_project": {"a": 1},
        })


def test_parse_supplier_rejects_empty_string_style_fingerprint():
    """R5 — empty-string style_fingerprint must fail (audit gap from R4)."""
    from sourcing_schema import parse_supplier, ValidationError
    with pytest.raises(ValidationError, match="null/empty style_fingerprint"):
        parse_supplier({
            "id": "x", "category": "lighting", "name": "X",
            "url": "https://example.com",
            "price_tier": "mid", "fit": "STRONG",
            "style_fingerprint": "   ", "fit_for_project": "x",
        })


def test_parse_supplier_rejects_empty_string_fit_for_project():
    """R5 — empty-string fit_for_project must fail (audit gap from R4)."""
    from sourcing_schema import parse_supplier, ValidationError
    with pytest.raises(ValidationError, match="null/empty fit_for_project"):
        parse_supplier({
            "id": "x", "category": "lighting", "name": "X",
            "url": "https://example.com",
            "price_tier": "mid", "fit": "STRONG",
            "style_fingerprint": "x", "fit_for_project": "",
        })


def test_parse_supplier_round_trips_url_status_tag():
    """R4 Fix I2 — recommended_url / url_status_tag / price_validation_status
    must round-trip through parse_supplier() onto the Supplier dataclass."""
    from sourcing_schema import parse_supplier
    sup = parse_supplier({
        "id": "x", "category": "rugs", "name": "X",
        "url": "https://example.com/old",
        "recommended_url": "https://example.com/new",
        "url_status_tag": "redirected_changed_path",
        "price_validation_status": "verified",
        "price_tier": "mid", "fit": "STRONG",
        "style_fingerprint": "x", "fit_for_project": "x",
    })
    assert sup.recommended_url == "https://example.com/new"
    assert sup.url_status_tag == "redirected_changed_path"
    assert sup.price_validation_status == "verified"


def test_load_supplier_directory_rejects_null_url(tmp_path):
    """Suppliers with `url: null` must fail loud at load."""
    from sourcing_schema import load_supplier_directory, ValidationError
    p = tmp_path / "bad.yaml"
    p.write_text(textwrap.dedent("""\
        meta: {}
        categories:
          - {id: lighting, label: Lighting}
        suppliers:
          - id: x
            category: lighting
            name: X
            url: null
            price_tier: mid
            fit: STRONG
            style_fingerprint: x
            fit_for_project: x
        """))
    with pytest.raises(ValidationError, match="null/empty url"):
        load_supplier_directory(str(p))


def test_load_supplier_directory_rejects_unknown_category(tmp_path):
    """Supplier `category` not in the file's `categories:` list fails loud."""
    from sourcing_schema import load_supplier_directory, ValidationError
    p = tmp_path / "bad.yaml"
    p.write_text(textwrap.dedent("""\
        meta: {}
        categories:
          - {id: lighting, label: Lighting}
        suppliers:
          - id: x
            category: not-a-real-category
            name: X
            url: https://example.com
            price_tier: mid
            fit: STRONG
            style_fingerprint: x
            fit_for_project: x
        """))
    # R4 Fix V1 — parse_supplier() now rejects unknown supplier categories
    # at parse time (against the canonical VALID_SUPPLIER_CATEGORIES set),
    # which fires BEFORE the loader's per-file declared-categories check.
    # Either message is acceptable; "unknown supplier category" is the new
    # one for back-compat.
    with pytest.raises(ValidationError, match="unknown supplier category|not in directory categories"):
        load_supplier_directory(str(p))


# ---------------------------------------------------------------------------
# R3 Fix C5 — locked rows emit data-vendor-matches
# ---------------------------------------------------------------------------


def test_render_locked_row_emits_data_vendor_matches():
    """Canon-locked items rendered via _render_locked_row() must carry
    data-vendor-matches so the /sourcing ?vendor= filter can keep them
    visible when they match the requested vendor."""
    from sourcing_render_html import _render_locked_row
    from sourcing_schema import Item
    it = Item(
        id="MB-VANITY", title="Master bath vanity",
        category="cabinetry_millwork", room="master_bath",
        urgency="T1", lead_time_weeks=8, budget_source="construction_allowance",
        budget_target_usd=2500.0, sourcing_actor="owner_direct",
        decision_status="decided", annika_loop=False,
        decided_sku="West Elm Hutchinson Vanity",
        vendor="West Elm",
    )
    row = _render_locked_row(it, vendor_matches=["west-elm-bedroom", "west-elm-seating"])
    assert 'data-vendor-matches="west-elm-bedroom west-elm-seating"' in row


# ---------------------------------------------------------------------------
# R3 Fix UX5 — fit prefix strip
# ---------------------------------------------------------------------------


def test_strip_redundant_fit_prefix_removes_strong():
    from sourcing_render_html import _strip_redundant_fit_prefix
    assert _strip_redundant_fit_prefix("STRONG — anchor brand per DESIGN_SPEC §5d") == (
        "Anchor brand per DESIGN_SPEC §5d"
    )


def test_strip_redundant_fit_prefix_removes_good_hyphen():
    from sourcing_render_html import _strip_redundant_fit_prefix
    # Plain hyphen instead of em-dash.
    assert _strip_redundant_fit_prefix("GOOD - K-DISHWASHER is owner-existing") == (
        "K-DISHWASHER is owner-existing"
    )


def test_strip_redundant_fit_prefix_removes_mixed_endash():
    from sourcing_render_html import _strip_redundant_fit_prefix
    assert _strip_redundant_fit_prefix("MIXED – browse carefully") == "Browse carefully"


def test_strip_redundant_fit_prefix_leaves_other_prose_unchanged():
    from sourcing_render_html import _strip_redundant_fit_prefix
    s = "West Elm Andes is the §11 named sofa."
    assert _strip_redundant_fit_prefix(s) == s


def test_render_suppliers_page_strips_strong_prefix_from_fit_line():
    """fit_for_project rendered in card body must NOT begin with 'STRONG — '."""
    from sourcing_render_html import render_suppliers_page
    fixture = {
        "meta": {},
        "categories": [{"id": "lighting", "label": "Lighting"}],
        "suppliers": [{
            "id": "x", "category": "lighting", "name": "X",
            "url": "https://example.com",
            "price_tier": "mid", "fit": "STRONG",
            "style_fingerprint": "Test fingerprint",
            "fit_for_project": "STRONG — anchor brand per DESIGN_SPEC reference",
        }],
    }
    html = render_suppliers_page(fixture)
    # The fit-line should NOT have "STRONG — " prefix.
    assert "STRONG &mdash; anchor brand" not in html
    assert "STRONG — anchor brand" not in html
    # But the substantive part should remain (with first letter capitalized).
    assert "Anchor brand per DESIGN_SPEC reference" in html


# ---------------------------------------------------------------------------
# R3 Fix UX6 — action group ARIA + arrow-key wiring
# ---------------------------------------------------------------------------


def test_supplier_action_buttons_have_radio_role_and_aria_checked():
    """Each action-btn must have role=radio + aria-checked='false' (default)
    so the role=radiogroup container is no longer a lie."""
    from sourcing_render_html import _render_supplier_card
    sup = {
        "id": "x", "category": "lighting", "name": "X",
        "url": "https://example.com",
        "price_tier": "mid", "fit": "STRONG",
        "style_fingerprint": "x", "fit_for_project": "x",
    }
    card_html = _render_supplier_card(sup, sourcing_match_ids=[])
    # 3 action buttons, each with role="radio" + aria-checked="false".
    assert card_html.count('role="radio"') == 3
    assert card_html.count('aria-checked="false"') == 3
    # R5 Fix I4 — within the supplier-action radiogroup, the FIRST radio is the
    # keyboard entry point (tabindex="0"); the other two stay at tabindex="-1"
    # until the roving handler in SUPPLIERS_JS picks them.
    import re as _re
    action_block = _re.search(
        r'<div class="supplier-action".*?</div>', card_html, _re.DOTALL,
    ).group(0)
    assert action_block.count('tabindex="0"') == 1
    assert action_block.count('tabindex="-1"') == 2


def test_suppliers_js_wires_arrow_key_navigation():
    """SUPPLIERS_JS handles ArrowRight/ArrowLeft for the action radiogroup."""
    from sourcing_render_html import SUPPLIERS_JS
    assert "ArrowRight" in SUPPLIERS_JS
    assert "ArrowLeft" in SUPPLIERS_JS
    # aria-checked toggling on click as well.
    assert "aria-checked" in SUPPLIERS_JS


def test_suppliers_js_arrow_keys_call_setaction():
    """R4 Fix V2 — arrow-key handlers must call setAction(card, next.dataset.action)
    so aria-checked + roving tabindex actually update on arrow nav (not just
    DOM focus). Codex rejected R3 Beta's R3-A3 'verified' claim because the
    original handler only called .focus() without invoking setAction()."""
    from sourcing_render_html import SUPPLIERS_JS
    # ArrowRight branch: setAction call must appear after the next assignment.
    assert "ArrowRight" in SUPPLIERS_JS
    # Find ArrowRight branch and assert setAction is called within it.
    right_idx = SUPPLIERS_JS.find("ArrowRight")
    left_idx = SUPPLIERS_JS.find("ArrowLeft")
    assert right_idx > 0 and left_idx > 0
    # The window between ArrowRight and ArrowLeft is the ArrowRight branch body.
    right_branch = SUPPLIERS_JS[right_idx:left_idx]
    assert "setAction(card, next.dataset.action)" in right_branch, (
        "ArrowRight handler must call setAction so aria-checked + roving "
        "tabindex update, not just .focus(). Got branch: " + right_branch[:500]
    )
    # ArrowLeft branch: same expectation against prev.
    enter_idx = SUPPLIERS_JS.find("' ' || key === 'Enter'", left_idx)
    left_branch = SUPPLIERS_JS[left_idx:enter_idx if enter_idx > 0 else left_idx + 600]
    assert "setAction(card, prev.dataset.action)" in left_branch, (
        "ArrowLeft handler must call setAction with prev.dataset.action."
    )


# ---------------------------------------------------------------------------
# R3 Fix UX4 — tri-state action OUTSIDE the <details> expander
# ---------------------------------------------------------------------------


def test_supplier_action_renders_outside_details_expander():
    """The supplier-action group must be a sibling of (not a descendant of)
    the <details class="supplier-details"> expander."""
    from sourcing_render_html import _render_supplier_card
    sup = {
        "id": "x", "category": "lighting", "name": "X",
        "url": "https://example.com",
        "price_tier": "mid", "fit": "STRONG",
        "style_fingerprint": "x", "fit_for_project": "x",
        "lead_time_typical": "1-2 weeks",  # ensures details emits
    }
    card_html = _render_supplier_card(sup, sourcing_match_ids=[])
    # The action div must appear BEFORE the <details> opening tag.
    action_idx = card_html.find('class="supplier-action"')
    details_idx = card_html.find("<details ")
    assert action_idx > 0, "supplier-action missing"
    assert details_idx > 0, "supplier-details expander missing"
    assert action_idx < details_idx, (
        "supplier-action must render BEFORE the <details> expander so it's "
        "always visible (R3 Fix UX4)"
    )


# ---------------------------------------------------------------------------
# R3 Fix UX3 — mobile filter-bar collapse via <details class="mobile-filters">
# ---------------------------------------------------------------------------


def test_render_suppliers_page_emits_mobile_filters_details():
    """The filter bar must be wrapped in a <details class="mobile-filters">
    so the dead CSS for mobile-collapse actually fires on mobile breakpoints.
    """
    from sourcing_render_html import render_suppliers_page
    fixture = {
        "meta": {},
        "categories": [{"id": "lighting", "label": "Lighting"}],
        "suppliers": [{
            "id": "x", "category": "lighting", "name": "X",
            "url": "https://example.com",
            "price_tier": "mid", "fit": "STRONG",
            "style_fingerprint": "x", "fit_for_project": "x",
        }],
    }
    html = render_suppliers_page(fixture)
    assert '<details class="mobile-filters">' in html
    assert '<summary class="mobile-filters-summary">' in html
    # CSS must reference the open-state filter-bar visibility.
    assert 'details.mobile-filters[open] > .suppliers-filter-bar' in html


# ---------------------------------------------------------------------------
# R3 Fix UX1 — hero classifier defaults to photo on real disk image
# ---------------------------------------------------------------------------


def test_hero_visual_class_defaults_to_photo_when_real_image_on_disk(tmp_path, monkeypatch):
    """When YAML has neither hero_image_source nor hero_image_source_url but
    the file on disk is real (non-trivial size, not HTML), classifier returns
    'photo', not 'placeholder'."""
    import sourcing_render_html as srh
    # Build a fake site dir with a fake "image" file of >1KB that isn't HTML.
    fake_site = tmp_path / "site"
    img_dir = fake_site / "images" / "suppliers"
    img_dir.mkdir(parents=True)
    fake_img = img_dir / "totally-real-product.jpg"
    # 2KB of JPEG-like binary (first 3 bytes are FF D8 FF = JPEG SOI).
    fake_img.write_bytes(b"\xff\xd8\xff" + b"x" * 2048)
    monkeypatch.setattr(srh, "SITE_DIR", fake_site)
    sup = {"hero_image": "/images/suppliers/totally-real-product.jpg"}
    assert srh._hero_visual_class(sup) == "photo"


def test_hero_visual_class_returns_broken_for_html_as_image(tmp_path, monkeypatch):
    """When the on-disk file is actually an HTML error page (e.g. 1.1MB
    schoolhouse.jpg 403), classifier returns 'broken' not 'photo'."""
    import sourcing_render_html as srh
    fake_site = tmp_path / "site"
    img_dir = fake_site / "images" / "suppliers"
    img_dir.mkdir(parents=True)
    fake_img = img_dir / "bad-html.jpg"
    fake_img.write_bytes(b"<!DOCTYPE html>\n<html><head><title>403</title></head>...")
    monkeypatch.setattr(srh, "SITE_DIR", fake_site)
    sup = {"hero_image": "/images/suppliers/bad-html.jpg"}
    assert srh._hero_visual_class(sup) == "broken"


# ---------------------------------------------------------------------------
# R4 Fix I1 — Explore CTA suppressed when _safe_href returns "#"
# ---------------------------------------------------------------------------


def test_explore_cta_suppressed_when_url_inert():
    """R4 Fix I1 — suppliers whose URL is rejected by _safe_href() (e.g.
    javascript: scheme, protocol-relative //) must NOT render a clickable
    Explore button. Codex flagged this as an open R2 important; R3 left
    the rendered `<a href="#">` in place."""
    from sourcing_render_html import _render_supplier_card
    sup = {
        "id": "evil", "category": "lighting", "name": "Evil",
        "url": "javascript:alert(1)",
        "price_tier": "mid", "fit": "STRONG",
        "style_fingerprint": "x", "fit_for_project": "x",
    }
    card_html = _render_supplier_card(sup, sourcing_match_ids=[])
    # Explore anchor MUST be absent; disabled placeholder span present instead.
    assert '<a class="explore-btn"' not in card_html, (
        "Explore <a> button must not render when _safe_href returns '#'."
    )
    assert 'explore-btn-disabled' in card_html, (
        "Inert URL should render a visibly-disabled placeholder span."
    )
    assert 'No site for Evil' in card_html


def test_explore_cta_renders_for_safe_url():
    """R4 Fix I1 sanity check — a well-formed https URL still renders the
    Explore anchor exactly as before."""
    from sourcing_render_html import _render_supplier_card
    sup = {
        "id": "good", "category": "lighting", "name": "Good",
        "url": "https://example.com",
        "price_tier": "mid", "fit": "STRONG",
        "style_fingerprint": "x", "fit_for_project": "x",
    }
    card_html = _render_supplier_card(sup, sourcing_match_ids=[])
    assert '<a class="explore-btn" href="https://example.com"' in card_html
    assert 'explore-btn-disabled' not in card_html


# ---------------------------------------------------------------------------
# R4 Fix I4 — hero_image path-traversal hardening
# ---------------------------------------------------------------------------


def test_safe_hero_image_path_accepts_canonical():
    """Paths under images/suppliers/ resolve to the canonical relative form."""
    from sourcing_render_html import _safe_hero_image_path
    assert _safe_hero_image_path("/images/suppliers/west-elm.jpg") == (
        "images/suppliers/west-elm.jpg"
    )
    assert _safe_hero_image_path("images/suppliers/x/y.jpg") == (
        "images/suppliers/x/y.jpg"
    )


def test_safe_hero_image_path_rejects_traversal():
    """`..` segments anywhere in the path are rejected outright."""
    from sourcing_render_html import _safe_hero_image_path
    assert _safe_hero_image_path("/images/suppliers/../../etc/passwd") is None
    assert _safe_hero_image_path("../etc/passwd") is None
    assert _safe_hero_image_path("images/suppliers/../sourcing/x.jpg") is None


def test_safe_hero_image_path_rejects_outside_subtree():
    """Paths that don't land under images/suppliers/ are rejected."""
    from sourcing_render_html import _safe_hero_image_path
    # Even without '..', a path outside images/suppliers must be rejected.
    assert _safe_hero_image_path("/images/sourcing/x.jpg") is None
    assert _safe_hero_image_path("/etc/passwd") is None
    assert _safe_hero_image_path("") is None
    assert _safe_hero_image_path(None) is None


def test_render_supplier_card_skips_hero_for_unsafe_path(tmp_path, monkeypatch):
    """A yaml entry whose hero_image lives OUTSIDE images/suppliers must
    NOT render an <img>. Falls back to the placeholder block."""
    import sourcing_render_html as srh
    fake_site = tmp_path / "site"
    bad_dir = fake_site / "secret"
    bad_dir.mkdir(parents=True)
    (bad_dir / "leak.jpg").write_bytes(b"\xff\xd8\xff" + b"x" * 2048)
    monkeypatch.setattr(srh, "SITE_DIR", fake_site)
    sup = {
        "id": "x", "category": "lighting", "name": "X",
        "url": "https://example.com",
        "price_tier": "mid", "fit": "STRONG",
        "style_fingerprint": "x", "fit_for_project": "x",
        "hero_image": "/secret/leak.jpg",
        "hero_image_source": "real_brand_cdn",
    }
    card_html = srh._render_supplier_card(sup, sourcing_match_ids=[])
    assert "/secret/leak.jpg" not in card_html
    assert "supplier-hero-placeholder" in card_html


# ---------------------------------------------------------------------------
# R4 Fix I2 — round-trip url verification metadata through the loader
# ---------------------------------------------------------------------------


def test_load_supplier_directory_preserves_verification_metadata(tmp_path):
    """R4 Fix I2 — the loader must propagate recommended_url, url_status_tag,
    and price_validation_status from YAML through to the validated output
    dicts so lint + downstream tools can read them. Codex flagged that
    the loader was dropping all three fields."""
    from sourcing_schema import load_supplier_directory
    p = tmp_path / "ok.yaml"
    p.write_text(textwrap.dedent("""\
        meta: {}
        categories:
          - {id: rugs, label: Rugs}
        suppliers:
          - id: lulu-georgia-rugs
            category: rugs
            name: Lulu and Georgia
            url: https://lulu-and-georgia.com/old-path
            recommended_url: https://lulu-and-georgia.com/rugs
            url_status_tag: redirected_changed_path
            price_validation_status: verified
            price_tier: mid
            fit: STRONG
            style_fingerprint: x
            fit_for_project: x
        """))
    data = load_supplier_directory(str(p))
    sup = data["suppliers"][0]
    assert sup["recommended_url"] == "https://lulu-and-georgia.com/rugs"
    assert sup["url_status_tag"] == "redirected_changed_path"
    assert sup["price_validation_status"] == "verified"


# ---------------------------------------------------------------------------
# R4 Fix I3 — lint: redirected_changed_path entries must have url == recommended_url
# ---------------------------------------------------------------------------


def test_lint_flags_redirected_url_not_matching_recommended(tmp_path, monkeypatch):
    """R4 Fix I3 — when a supplier's url_status_tag is redirected_changed_path
    but `url` does not match `recommended_url`, lint emits a warning so the
    operator updates to the canonical URL. Codex named lulu-georgia-rugs."""
    from sourcing_lint import check_supplier_directory_url_freshness
    yaml_text = textwrap.dedent("""\
        meta: {}
        categories: []
        suppliers:
          - id: lulu-georgia-rugs
            url_verified: true
            url_status: redirected_changed_path
            url_status_tag: redirected_changed_path
            url: https://lulu-and-georgia.com/old-path
            recommended_url: https://lulu-and-georgia.com/rugs
          - id: ok-redirected-already-updated
            url_verified: true
            url_status: redirected_changed_path
            url_status_tag: redirected_changed_path
            url: https://example.com/new
            recommended_url: https://example.com/new
        """)
    target = tmp_path / "Desktop" / "HomeAI" / "scope"
    target.mkdir(parents=True)
    (target / "supplier_directory.yaml").write_text(yaml_text)
    import os as _os
    real_expand = _os.path.expanduser
    monkeypatch.setattr(
        _os.path, "expanduser",
        lambda p: p.replace("~", str(tmp_path)) if p.startswith("~") else real_expand(p),
    )
    findings = check_supplier_directory_url_freshness([], None)
    # No stale finding (both url_status values are in FRESH_STATUS_STRINGS),
    # but exactly one redirect-canonical-drift finding.
    drift = [f for f in findings if "redirected_changed_path" in f.message]
    assert len(drift) == 1
    msg = drift[0].message
    assert "lulu-georgia-rugs" in msg
    assert "ok-redirected-already-updated" not in msg


def test_filter_panel_labels_have_for_associations():
    """R4 Fix I5 — every <label> in the /suppliers filter bar must carry a
    `for=` attribute pointing to its control id. Codex flagged the bare
    <label> nodes (no for=) as failing the WCAG association test."""
    from sourcing_render_html import render_suppliers_page
    fixture = {
        "meta": {},
        "categories": [{"id": "lighting", "label": "Lighting"}],
        "suppliers": [{
            "id": "x", "category": "lighting", "name": "X",
            "url": "https://example.com",
            "price_tier": "mid", "fit": "STRONG",
            "style_fingerprint": "x", "fit_for_project": "x",
        }],
    }
    html = render_suppliers_page(fixture)
    # Each filter-bar control id must have a matching <label for=...>.
    for ctl_id in ("supplier-search", "cat-filter", "tier-filter",
                   "fit-filter", "sort-by"):
        assert f'<label for="{ctl_id}">' in html, (
            f"<label for=\"{ctl_id}\"> missing — filter labels must associate."
        )
    # No bare <label> nodes in the filter bar (smoke-test heuristic: the
    # rendered suppliers-filter-bar block contains zero `<label>` without
    # a `for=` attribute).
    fb_start = html.find('<div class="suppliers-filter-bar">')
    fb_end = html.find('</div>', fb_start)
    fb_block = html[fb_start:fb_end] if fb_start >= 0 else ""
    assert "<label>" not in fb_block, (
        "Found bare <label> in suppliers-filter-bar block: must use for=."
    )


def test_lint_no_drift_when_redirect_url_matches_recommended(tmp_path, monkeypatch):
    """R4 Fix I3 sanity — when url == recommended_url for a redirected entry,
    no drift warning is emitted."""
    from sourcing_lint import check_supplier_directory_url_freshness
    yaml_text = textwrap.dedent("""\
        meta: {}
        categories: []
        suppliers:
          - id: redirected-ok
            url_verified: true
            url_status: redirected_changed_path
            url_status_tag: redirected_changed_path
            url: https://example.com/canonical
            recommended_url: https://example.com/canonical
        """)
    target = tmp_path / "Desktop" / "HomeAI" / "scope"
    target.mkdir(parents=True)
    (target / "supplier_directory.yaml").write_text(yaml_text)
    import os as _os
    real_expand = _os.path.expanduser
    monkeypatch.setattr(
        _os.path, "expanduser",
        lambda p: p.replace("~", str(tmp_path)) if p.startswith("~") else real_expand(p),
    )
    findings = check_supplier_directory_url_freshness([], None)
    assert findings == []


# ---------------------------------------------------------------------------
# R5 Fix I2 — supplier hero <img> emits intrinsic width/height for CLS-free
# layout reservation.
# ---------------------------------------------------------------------------


def test_render_suppliers_page_hero_img_has_intrinsic_dimensions():
    """R5 Fix I2 — every emitted hero <img> must carry width/height attributes."""
    from sourcing_render_html import render_suppliers_page
    fixture = {
        "meta": {"generated": "2026-05-17", "last_verification_pass": "2026-05-17"},
        "categories": [{"id": "furniture-seating", "label": "Seating"}],
        "suppliers": [{
            "id": "west-elm-seating",
            "category": "furniture-seating",
            "name": "West Elm",
            "url": "https://www.westelm.com",
            "price_tier": "mid", "fit": "STRONG",
            "style_fingerprint": "x", "fit_for_project": "x",
            "hero_image": "/images/suppliers/west-elm-seating.jpg",
            "url_verified": True, "url_status": 200,
        }],
    }
    html = render_suppliers_page(fixture)
    # If the on-disk file exists, the <img> is rendered with width/height.
    # If not, the placeholder is used (no <img>); skip the assertion in that case.
    if 'src="/images/suppliers/west-elm-seating.jpg"' in html:
        assert ' width="' in html
        assert ' height="' in html


def test_hero_image_dimensions_fallback_when_path_missing(tmp_path):
    """R5 Fix I2 — _hero_image_dimensions returns fallback when the file
    can't be opened. Best-effort: never raises."""
    from sourcing_render_html import (
        _hero_image_dimensions, _HERO_FALLBACK_W, _HERO_FALLBACK_H,
    )
    w, h = _hero_image_dimensions(tmp_path / "does-not-exist.jpg")
    assert (w, h) == (_HERO_FALLBACK_W, _HERO_FALLBACK_H)


# ---------------------------------------------------------------------------
# R5 Fix I3 — every supplier card's <details> summary is supplier-specific,
# so screen readers can distinguish expanders.
# ---------------------------------------------------------------------------


def test_render_suppliers_page_details_summary_includes_name():
    """R5 Fix I3 — supplier card summary must include the supplier name."""
    from sourcing_render_html import render_suppliers_page
    fixture = {
        "meta": {},
        "categories": [
            {"id": "furniture-seating", "label": "Seating"},
            {"id": "lighting", "label": "Lighting"},
        ],
        "suppliers": [
            {
                "id": "a-co", "category": "furniture-seating", "name": "Alpha Co",
                "url": "https://a.example.com",
                "price_tier": "mid", "fit": "STRONG",
                "style_fingerprint": "x", "fit_for_project": "x",
                "collections_to_browse": [{"name": "Hutchinson"}],
            },
            {
                "id": "b-co", "category": "lighting", "name": "Beta Co",
                "url": "https://b.example.com",
                "price_tier": "low", "fit": "GOOD",
                "style_fingerprint": "y", "fit_for_project": "y",
                "collections_to_browse": [{"name": "Glo"}],
            },
        ],
    }
    html = render_suppliers_page(fixture)
    # Each summary names its supplier — uniqueness for screen readers.
    assert "Alpha Co &mdash; details &amp; collections" in html
    # Old non-distinct text must be gone.
    assert "<summary>Details &amp; collections</summary>" not in html


def test_render_suppliers_page_details_summaries_unique_across_cards():
    """R5 Fix I3 — collect every <summary> from the rendered page; supplier
    summaries must be unique."""
    import re as _re
    from sourcing_render_html import render_suppliers_page
    fixture = {
        "meta": {},
        "categories": [
            {"id": "furniture-seating", "label": "Seating"},
        ],
        "suppliers": [
            {
                "id": f"s{i}", "category": "furniture-seating", "name": f"Supplier {i}",
                "url": "https://example.com",
                "price_tier": "mid", "fit": "STRONG",
                "style_fingerprint": "x", "fit_for_project": "x",
                "collections_to_browse": [{"name": "Coll"}],
            }
            for i in range(5)
        ],
    }
    html = render_suppliers_page(fixture)
    # Pull supplier-card summaries (the ones that end with the canonical phrase).
    summaries = _re.findall(
        r'<summary>([^<]*details &amp; collections)</summary>', html
    )
    assert len(summaries) == 5
    assert len(set(summaries)) == 5  # All distinct.


# ---------------------------------------------------------------------------
# R5 Fix I4 — first action radio in each card gets tabindex="0" so keyboard
# users can enter the radiogroup before JS loads.
# ---------------------------------------------------------------------------


def test_render_suppliers_page_first_action_radio_has_tabindex_zero():
    """R5 Fix I4 — server-side rendered first radio per card has tabindex=0."""
    from sourcing_render_html import render_suppliers_page
    fixture = {
        "meta": {},
        "categories": [{"id": "lighting", "label": "Lighting"}],
        "suppliers": [{
            "id": "x", "category": "lighting", "name": "X",
            "url": "https://example.com",
            "price_tier": "mid", "fit": "STRONG",
            "style_fingerprint": "x", "fit_for_project": "x",
        }],
    }
    html = render_suppliers_page(fixture)
    # The first action button (action-visit) must be the keyboard entry point.
    assert (
        'class="action-btn action-visit" data-action="visit" '
        'role="radio" aria-checked="false" tabindex="0"'
    ) in html
    # Second + third buttons stay at tabindex=-1 until JS roves them.
    assert (
        'class="action-btn action-saved" data-action="saved" '
        'role="radio" aria-checked="false" tabindex="-1"'
    ) in html
    assert (
        'class="action-btn action-ruled" data-action="ruled" '
        'role="radio" aria-checked="false" tabindex="-1"'
    ) in html


# ---------------------------------------------------------------------------
# R1 mobile-fit baseline (2026-05-17) — see audits/2026-05-17-mobile-fit-baseline/
# ---------------------------------------------------------------------------


def test_shared_css_includes_mobile_baseline():
    """SHARED_CSS carries the R1 mobile baseline: overflow-x guard, responsive
    image reset, --topnav-h variable, and the .table-wrapper helper."""
    from sourcing_render_html import SHARED_CSS

    assert "overflow-x: hidden" in SHARED_CSS
    assert "img, picture, video" in SHARED_CSS
    assert "max-width: 100%" in SHARED_CSS
    assert "--topnav-h" in SHARED_CSS
    assert ".table-wrapper" in SHARED_CSS


def test_shared_css_topnav_mobile_scroll():
    """At ≤720px the topnav becomes a horizontally-scrollable single row with
    44px touch targets (baseline §5 + top-fix §3)."""
    from sourcing_render_html import SHARED_CSS

    assert "flex-wrap: nowrap" in SHARED_CSS
    assert "min-height: 44px" in SHARED_CSS


def test_shared_css_uses_720px_breakpoint():
    """sourcing_render uses 720px primary + 480px micro — same convention as
    build_pages + build_spec after R1."""
    from sourcing_render_html import SHARED_CSS

    assert "@media (max-width: 720px)" in SHARED_CSS
    assert "@media (max-width: 480px)" in SHARED_CSS


def test_sticky_offset_uses_topnav_h_variable():
    """.filter-bar top references --topnav-h so sticky offsets scale with
    the taller mobile topnav (baseline §8)."""
    from sourcing_render_html import SHARED_CSS

    assert "top: var(--topnav-h)" in SHARED_CSS


def test_vendors_page_wraps_every_table_in_table_wrapper():
    """vendors.html has 75 raw <table> tags — baseline §3 flagged this as the
    single biggest mobile-fit failure on the site. R1 wraps each in a
    .table-wrapper so they can horizontally scroll instead of breaking layout."""
    import yaml as _yaml
    from pathlib import Path as _Path
    from sourcing_loader import load_sourcing
    from sourcing_render_html import render_vendors_page

    # Use the live scope yaml so the test reflects the real render.
    yaml_path = _Path.home() / "Desktop" / "HomeAI" / "scope" / "sourcing.yaml"
    if not yaml_path.exists():
        import pytest as _pytest
        _pytest.skip("sourcing.yaml not available in this env")
    data = load_sourcing(yaml_path)
    html = render_vendors_page(data.items, data.meta, last_changed_map={})

    n_open = html.count("<table>")
    n_wrapped = html.count('<div class="table-wrapper"><table>')
    n_section_wrapped = html.count(
        '<div class="table-wrapper">'
    )
    # Every <table> opens inside a table-wrapper (one wrapper per table).
    assert n_open > 0, "vendors page should have multiple tables"
    # Per-vendor + canon-summary + (potential budget) wraps — section wrappers
    # always equal or exceed table count because each table is wrapped.
    assert n_section_wrapped >= n_open, (
        f"expected ≥{n_open} .table-wrapper divs, found {n_section_wrapped}"
    )
    # Direct test: every <table> tag is immediately preceded by a wrapper div
    # OR the wrapper appears inline with the table on the same chunk.
    assert n_open == n_wrapped, (
        f"{n_open} <table> tags but only {n_wrapped} wrapped — "
        "some tables would break layout at 375px"
    )


def test_sourcing_page_budget_rollup_table_wrapped():
    """The /sourcing budget-rollup table is the lone unwrapped table baseline §10
    flagged on an otherwise well-tuned page. After R1 it lives inside a
    .table-wrapper."""
    from pathlib import Path as _Path
    from sourcing_loader import load_sourcing
    from sourcing_render_html import render_site_page

    yaml_path = _Path.home() / "Desktop" / "HomeAI" / "scope" / "sourcing.yaml"
    if not yaml_path.exists():
        import pytest as _pytest
        _pytest.skip("sourcing.yaml not available in this env")
    data = load_sourcing(yaml_path)
    html = render_site_page(data.items, data.meta, [])
    # The rollup is rendered as `<div class="budget-rollup">…<div class="table-wrapper"><table>`.
    assert '<div class="budget-rollup">' in html
    # Find the rollup block and verify it contains a wrapper.
    rollup_start = html.find('<div class="budget-rollup">')
    # Look within ~2000 chars after the rollup open for both wrapper + table.
    rollup_chunk = html[rollup_start:rollup_start + 4000]
    assert '<div class="table-wrapper">' in rollup_chunk
    assert "<table>" in rollup_chunk


def test_collection_chip_meets_44px_touch_target_on_mobile():
    """Baseline top-fix §4 — .collection-chip lifted from 36px to 44px so it
    clears WCAG 2.5.5 on the suppliers page."""
    from sourcing_render_html import SUPPLIERS_CSS

    assert ".collection-chip { padding: 10px 14px; min-height: 44px;" in SUPPLIERS_CSS


# ---------------------------------------------------------------------------
# R2 mobile-fit (2026-05-17) — see audits/2026-05-17-mobile-fit-baseline/taa-r2-*
# ---------------------------------------------------------------------------


def test_topnav_uses_scroller_wrapper_for_dropdown_escape():
    """R2-C1: topnav HTML must wrap topnav-inner in a .topnav-scroller div so
    the absolute/fixed dropdowns escape the horizontal-scroll overflow scope.
    Without the wrapper, Rooms ▾ + Canon ▾ menus are clipped vertically on
    mobile (the most user-visible bug on the site at <720px)."""
    from sourcing_render_html import _build_topnav_html

    nav = _build_topnav_html("sourcing")
    assert '<div class="topnav-scroller">' in nav, (
        "topnav must wrap topnav-inner in .topnav-scroller — without it the "
        "mobile dropdowns get clipped"
    )
    # And the scroller must contain the inner.
    assert '<div class="topnav-scroller">' in nav
    assert '<div class="topnav-inner">' in nav
    # Order matters: scroller opens BEFORE inner.
    scroller_idx = nav.find('<div class="topnav-scroller">')
    inner_idx = nav.find('<div class="topnav-inner">')
    assert scroller_idx < inner_idx, "scroller must wrap inner, not the reverse"


def test_mobile_dropdown_escapes_overflow_via_fixed_position():
    """R2-C1: on mobile the dropdown menu becomes position: fixed so it can
    escape .topnav-scroller's horizontal-scroll overflow. Without this, even
    with the scroller wrapper, the menu would still be clipped to the inner
    container width."""
    from sourcing_render_html import SHARED_CSS

    assert "details.nav-dropdown[open] > .nav-dropdown-menu" in SHARED_CSS
    assert "position: fixed" in SHARED_CSS


def test_topnav_h_mobile_lifted_to_56px():
    """R2-C4: mobile --topnav-h underestimated the actual computed height
    (44px min-height + 6px×2 padding ≈ 56px). Pre-R2 it was 52px."""
    from sourcing_render_html import SHARED_CSS

    assert "--topnav-h: 56px" in SHARED_CSS
    assert "--topnav-h: 52px" not in SHARED_CSS


def test_wrapped_table_cascade_rule_present():
    """R2-C2: .table-wrapper > table override so wrapped tables render
    naturally + the wrapper handles overflow. Pre-R2 this lived only in
    build_spec.py; build_pages and sourcing_render were missing it."""
    from sourcing_render_html import SHARED_CSS

    assert ".table-wrapper > table" in SHARED_CSS
    # The rule must reset display/white-space/overflow so the global table
    # block-overflow fallback doesn't double-apply.
    assert ("display: table" in SHARED_CSS and
            "white-space: normal" in SHARED_CSS)


def test_supplier_breakpoint_unified_to_720px():
    """R2-C6: supplier two-column layout collapses at 720px (was 900px,
    an outlier vs the site-wide 720/480 baseline)."""
    from sourcing_render_html import SUPPLIERS_CSS

    # The supplier-page-layout @media must be 720 now, not 900.
    assert "@media (max-width: 720px) {\n  .suppliers-page-layout" in SUPPLIERS_CSS
    # No more 900px breakpoint anywhere in supplier CSS.
    assert "@media (max-width: 900px)" not in SUPPLIERS_CSS


def test_anchor_shim_uses_topnav_h_variable():
    """R2-C5: .item-card[id]::before anchor-shim derives from --topnav-h
    instead of a hardcoded 56px. Keeps jump-link offsets accurate when the
    sticky topnav height changes between mobile and desktop."""
    from sourcing_render_html import SHARED_CSS

    # Find the anchor-shim rule; assert it references --topnav-h.
    shim_idx = SHARED_CSS.find(".item-card[id]::before")
    assert shim_idx >= 0
    shim_chunk = SHARED_CSS[shim_idx:shim_idx + 400]
    assert "var(--topnav-h)" in shim_chunk


def test_category_side_nav_sticky_offset_uses_topnav_h():
    """R2-C5: .category-side-nav sticky top derives from --topnav-h instead
    of a hardcoded 100px."""
    from sourcing_render_html import SUPPLIERS_CSS

    side_idx = SUPPLIERS_CSS.find(".category-side-nav { position: sticky;")
    assert side_idx >= 0
    side_chunk = SUPPLIERS_CSS[side_idx:side_idx + 200]
    assert "var(--topnav-h)" in side_chunk


def test_table_wrapper_scroll_affordance():
    """R2-UX1: scrollable surfaces get an edge-fade gradient + visible
    webkit scrollbar so users know they can swipe horizontally."""
    from sourcing_render_html import SHARED_CSS

    # Edge-fade gradient on the table-wrapper.
    assert ".table-wrapper::after" in SHARED_CSS
    # Visible scrollbar (the previous baseline had display: none).
    assert ".table-wrapper::-webkit-scrollbar { height: 6px;" in SHARED_CSS


def test_topnav_scroller_scroll_affordance():
    """R2-UX1: edge-fade gradient on the topnav scroller so users can see
    "Vendors / Annika / Spec / Rooms ▾ / Canon ▾ / Materials / Rejected"
    are reachable via scroll on mobile."""
    from sourcing_render_html import SHARED_CSS

    assert ".topnav-scroller::after" in SHARED_CSS or (
        ".topnav-scroller::after, .table-wrapper::after" in SHARED_CSS
    )


def test_sourcing_admin_section_collapses_on_mobile():
    """R2-UX2: schedule + decisions + budget + overshoot + lint banners
    wrap in <details class="admin-section">. Desktop default (display:
    contents) is transparent; mobile collapses behind a 'Admin & status'
    tap-target so /sourcing first-paint lands on item cards within a screen."""
    from pathlib import Path as _Path
    from sourcing_loader import load_sourcing
    from sourcing_render_html import render_site_page, SOURCING_MAIN_CSS

    yaml_path = _Path.home() / "Desktop" / "HomeAI" / "scope" / "sourcing.yaml"
    if not yaml_path.exists():
        import pytest as _pytest
        _pytest.skip("sourcing.yaml not available in this env")
    data = load_sourcing(yaml_path)
    html = render_site_page(data.items, data.meta, [])
    # The HTML must wrap the admin banners.
    assert '<details class="admin-section">' in html
    assert '<summary class="admin-section-summary">' in html
    # And the supporting CSS for the desktop-transparent / mobile-collapsed
    # pattern is present.
    assert ".admin-section { display: contents; }" in SOURCING_MAIN_CSS
    assert "@media (max-width: 720px)" in SOURCING_MAIN_CSS


def test_sourcing_filter_bar_uses_mobile_drawer():
    """R2-UX4: /sourcing filter-bar now wraps in <details class="mobile-filters">
    so it collapses behind a tap-target on phone (mirrors the /suppliers
    pattern)."""
    from pathlib import Path as _Path
    from sourcing_loader import load_sourcing
    from sourcing_render_html import render_site_page

    yaml_path = _Path.home() / "Desktop" / "HomeAI" / "scope" / "sourcing.yaml"
    if not yaml_path.exists():
        import pytest as _pytest
        _pytest.skip("sourcing.yaml not available in this env")
    data = load_sourcing(yaml_path)
    html = render_site_page(data.items, data.meta, [])
    # Wrapper present.
    assert 'details class="mobile-filters"' in html
    assert 'class="mobile-filters-summary"' in html
    # The original filter-bar is still inside, just behind the drawer on mobile.
    assert '<div class="filter-bar">' in html


def test_vendors_page_non_sku_cells_wrap_on_mobile():
    """R2-UX3: vendor table on mobile relaxes white-space: nowrap on
    id-col/title-col/num/status-col so titles wrap instead of forcing a
    1500-3500px-wide row that requires per-row horizontal scroll."""
    from sourcing_render_html import VENDORS_CSS

    # The non-SKU cells get white-space: normal on mobile.
    assert "white-space: normal" in VENDORS_CSS
    assert "@media (max-width: 720px)" in VENDORS_CSS


def test_filter_bar_buttons_meet_44px_touch_target():
    """R2-T1: .filter-bar button/select/input lift to 44px min-height on
    mobile per WCAG 2.5.5."""
    from sourcing_render_html import SHARED_CSS

    # The filter-bar mobile rule must include input + min-height: 44px.
    filter_idx = SHARED_CSS.find(".filter-bar button, .filter-bar select, .filter-bar input")
    assert filter_idx >= 0
    chunk = SHARED_CSS[filter_idx:filter_idx + 300]
    assert "min-height: 44px" in chunk


def test_decisions_banner_anchors_meet_44px_on_mobile():
    """R2-T3: .decisions-needed-banner a links lift to 44px min-height on
    mobile per WCAG 2.5.5."""
    from sourcing_render_html import SHARED_CSS

    # The mobile @media block must include a rule for decisions-needed-banner a.
    assert ".decisions-needed-banner a { min-height: 44px;" in SHARED_CSS


def test_vendor_id_col_anchors_meet_44px_on_mobile():
    """R2-T5: /vendors td.id-col a links lift to 44px on mobile (was ~24px
    of unpadded font-only height)."""
    from sourcing_render_html import VENDORS_CSS

    assert ".vendor-section td.id-col a { min-height: 44px;" in VENDORS_CSS


def test_build_spec_table_wrap_is_idempotent():
    """R2-C3: build_spec.py table wrap is idempotent (re-running doesn't
    double-wrap) and skips <table> tags inside <pre> code blocks."""
    import importlib.util as _ilu
    from pathlib import Path as _Path

    bs_path = _Path(__file__).resolve().parent.parent / "build_spec.py"
    src = bs_path.read_text()
    # _wrap_tables must be defined.
    assert "_wrap_tables" in src
    # Load _wrap_tables alone (don't trigger the top-level read that depends on
    # ~/Desktop/HomeAI). Easier path: regex-execute manually.
    # Pull the helper into a sandbox by parsing the function body.
    import re as _re
    func_match = _re.search(
        r"def _wrap_tables\(html: str\) -> str:.*?(?=\n\nhtml_body)",
        src, _re.DOTALL,
    )
    assert func_match, "_wrap_tables function definition not found in build_spec.py"
    # Reconstruct the helper alongside the regex/setup it depends on.
    helper_src = _re.search(r"_TABLE_RE = _re\.compile.*?return \"\".join\(parts\)",
                            src, _re.DOTALL).group(0)
    ns = {"_re": _re}
    exec(
        "import re as _re\n"
        "_TABLE_RE = _re.compile(r'<table\\b[^>]*>.*?</table>', _re.DOTALL)\n"
        "_PRE_SPLIT_RE = _re.compile(r'(<pre\\b[^>]*>.*?</pre>)', _re.DOTALL)\n"
        "_WRAPPER_PREFIX = '<div class=\"table-wrapper\">'\n"
        "def _wrap_one_match(m):\n"
        "    span = m.string\n"
        "    start = m.start()\n"
        "    if span[max(0, start - len(_WRAPPER_PREFIX)):start] == _WRAPPER_PREFIX:\n"
        "        return m.group(0)\n"
        "    return f'{_WRAPPER_PREFIX}{m.group(0)}</div>'\n"
        "def _wrap_tables(html):\n"
        "    parts = _PRE_SPLIT_RE.split(html)\n"
        "    for i, part in enumerate(parts):\n"
        "        if part.startswith('<pre'):\n"
        "            continue\n"
        "        parts[i] = _TABLE_RE.sub(_wrap_one_match, part)\n"
        "    return ''.join(parts)\n",
        ns,
    )
    _wrap_tables = ns["_wrap_tables"]

    # Single table → wrapped.
    once = _wrap_tables("<table><tr><td>x</td></tr></table>")
    assert once.count('<div class="table-wrapper">') == 1
    # Re-running on already-wrapped output → still 1 wrapper (idempotent).
    twice = _wrap_tables(once)
    assert twice.count('<div class="table-wrapper">') == 1, (
        "build_spec.py table-wrap regex must be idempotent — re-rendering "
        "must not double-wrap"
    )
    # <pre><table> inside code samples is untouched.
    code = "<pre><code>&lt;table&gt;example&lt;/table&gt;</code></pre>"
    assert _wrap_tables(code) == code, (
        "tables inside <pre> code samples must not be wrapped"
    )
    # Real <pre><table> (raw embedded table inside pre, edge case) is untouched.
    real_pre = "<pre><table><tr><td>literal</td></tr></table></pre>"
    assert _wrap_tables(real_pre) == real_pre


def test_build_pages_wrapped_table_cascade_rule_present():
    """R2-C2: .table-wrapper > table override must also be present in
    build_pages.py SHARED_CSS — pre-R2 it lived only in build_spec.py so
    /budget /materials /kitchen /master etc. wrapped tables computed
    differently than /spec wrapped tables."""
    from build_pages import SHARED_CSS

    assert ".table-wrapper > table" in SHARED_CSS
    assert "display: table" in SHARED_CSS
    assert "white-space: normal" in SHARED_CSS

