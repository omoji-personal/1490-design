# tests/test_build_pages.py
"""Tests for build_pages.py — covers the topnav helper that renders the static
index/budget/decisions/mood-board/spectrum/6-room/4-canon/materials/rejected
pages. Mirrors the dropdown-collapse pattern from sourcing_render_html._build_topnav_html()."""

from pathlib import Path
import sys

# build_pages lives at repo root; tests/ is a sibling — make it importable.
sys.path.insert(0, str(Path(__file__).parent.parent))
from build_pages import topnav  # noqa: E402


def test_topnav_rooms_collapsed_into_dropdown():
    """Rooms is rendered as a <details class='nav-dropdown'> dropdown, not inline links."""
    nav = topnav("/budget")
    assert 'details class="nav-dropdown"' in nav
    assert "<summary>Rooms</summary>" in nav
    # All 6 room links live inside the menu
    for href in ("/kitchen", "/master", "/baths", "/lr", "/nursery", "/office"):
        assert f'href="{href}"' in nav


def test_topnav_canon_collapsed_into_dropdown():
    """Canon is rendered as a <details class='nav-dropdown'> dropdown."""
    nav = topnav("/budget")
    assert "<summary>Canon</summary>" in nav
    for href in ("/cathie-hong", "/owiu", "/sss", "/jenni-kayne"):
        assert f'href="{href}"' in nav


def test_topnav_inline_entries_stay_inline():
    """Home, Mood, Spectrum, Decisions, Budget, Sourcing, Suppliers, Vendors,
    Annika, Spec, Materials, Rejected stay as bare <a> tags."""
    nav = topnav("/budget")
    for href in (
        "/", "/mood-board", "/spectrum", "/decisions", "/budget",
        "/sourcing", "/suppliers", "/vendors", "/for-annika", "/spec",
        "/materials", "/rejected",
    ):
        assert f'href="{href}"' in nav


def test_topnav_marks_current_inline_link():
    """Inline links get class='current' when active."""
    nav = topnav("/budget")
    assert '<a href="/budget" class="current">Budget</a>' in nav
    # And /sourcing should not be marked current
    assert '<a href="/sourcing" class="current">' not in nav


def test_topnav_marks_current_link_inside_rooms_dropdown():
    """When on a room page, the room link inside the dropdown gets class='current'
    AND the Rooms <details> renders with the 'open' attribute so the active entry
    is visible without a click."""
    nav = topnav("/kitchen")
    assert '<a href="/kitchen" class="current">Kitchen</a>' in nav
    # Rooms dropdown should be open
    assert 'details class="nav-dropdown" open aria-label="Rooms"' in nav
    # Canon should NOT be open
    assert 'details class="nav-dropdown" open aria-label="Canon designers"' not in nav


def test_topnav_marks_current_link_inside_canon_dropdown():
    """Canon dropdown opens when on a canon-designer page."""
    nav = topnav("/owiu")
    assert '<a href="/owiu" class="current">OWIU</a>' in nav
    assert 'details class="nav-dropdown" open aria-label="Canon designers"' in nav
    # Rooms should not auto-open on a canon page
    assert 'details class="nav-dropdown" open aria-label="Rooms"' not in nav


def test_topnav_no_dropdown_open_on_neutral_pages():
    """On a non-room, non-canon page neither dropdown is auto-opened."""
    nav = topnav("/decisions")
    assert 'details class="nav-dropdown" open' not in nav
    assert '<a href="/decisions" class="current">Decisions</a>' in nav


def test_topnav_renders_for_all_known_slugs():
    """Sanity check: topnav doesn't crash for any of the 17 slugs the static
    pages currently pass in."""
    for slug in (
        "/", "/mood-board", "/spectrum", "/decisions", "/budget",
        "/kitchen", "/master", "/baths", "/lr", "/nursery", "/office",
        "/cathie-hong", "/owiu", "/sss", "/jenni-kayne",
        "/materials", "/rejected",
    ):
        nav = topnav(slug)
        assert "<summary>Rooms</summary>" in nav
        assert "<summary>Canon</summary>" in nav


def test_topnav_dropdown_pattern_matches_sourcing_render_html():
    """Byte-level check: the dropdown structure produced by build_pages.topnav()
    matches the pattern produced by sourcing_render_html._build_topnav_html() so
    a user navigating between /sourcing (sourcing_render_html) and /budget
    (build_pages) sees the same chrome."""
    from sourcing_render_html import _build_topnav_html

    src_nav = _build_topnav_html("budget")
    bp_nav = topnav("/budget")

    # Both render the Rooms + Canon dropdowns with the same summary text and
    # role/aria-label attributes.
    for needle in (
        "<summary>Rooms</summary>",
        "<summary>Canon</summary>",
        'class="nav-dropdown-menu" role="menu"',
        'aria-label="Rooms"',
        'aria-label="Canon designers"',
    ):
        assert needle in src_nav, f"{needle!r} missing from sourcing_render_html topnav"
        assert needle in bp_nav, f"{needle!r} missing from build_pages topnav"


def test_rendered_budget_page_contains_dropdown_html():
    """End-to-end: a freshly rendered budget.html contains the dropdown HTML and
    the CSS that styles it."""
    from build_pages import budget_page

    html = budget_page()
    assert 'details class="nav-dropdown"' in html
    assert "<summary>Rooms</summary>" in html
    assert "<summary>Canon</summary>" in html
    # CSS that styles the dropdown ships in the same page
    assert ".topnav-inner details.nav-dropdown" in html


# =====================================================================
# R1 mobile-fit baseline (2026-05-17) — see audits/2026-05-17-mobile-fit-baseline/
# =====================================================================

def test_shared_css_includes_mobile_baseline():
    """The SHARED_CSS string in build_pages.py carries the R1 mobile baseline:
    overflow-x guard, responsive image reset, --topnav-h variable, and the
    .table-wrapper helper. Without these, builds_pages-rendered pages cannot
    survive at 375px without breaking layout (see baseline.md §9)."""
    from build_pages import SHARED_CSS

    # Site-wide horizontal-overflow safety net (baseline §9).
    assert "overflow-x: hidden" in SHARED_CSS
    # Global responsive image reset (baseline §4).
    assert "img, picture, video" in SHARED_CSS
    assert "max-width: 100%" in SHARED_CSS
    # Topnav-height CSS variable used by sticky offsets (baseline §8 / Fix 4).
    assert "--topnav-h" in SHARED_CSS
    # Table wrapper class exists so wrapped tables can scroll on mobile.
    assert ".table-wrapper" in SHARED_CSS


def test_shared_css_topnav_mobile_scroll():
    """At ≤720px the topnav becomes a horizontally-scrollable single row with
    44px touch targets (baseline §5 + top-fix §3)."""
    from build_pages import SHARED_CSS

    # The mobile block must declare flex-wrap: nowrap + overflow-x: auto on the
    # topnav so links don't stack into 5-6 rows of mini-pills on a phone.
    assert "flex-wrap: nowrap" in SHARED_CSS
    assert "min-height: 44px" in SHARED_CSS


def test_shared_css_unified_720px_breakpoint():
    """R1 unifies the build_pages breakpoint on 720px (matches sourcing_render +
    build_spec) instead of the legacy 768px. The 480px micro-breakpoint stays
    for very-small phones."""
    from build_pages import SHARED_CSS

    assert "@media (max-width: 720px)" in SHARED_CSS
    assert "@media (max-width: 480px)" in SHARED_CSS
    # Legacy 768px should no longer be the primary breakpoint.
    assert "@media (max-width: 768px)" not in SHARED_CSS


def test_spec_table_wrapped_in_table_wrapper():
    """Every <table class='spec-table'> in build_pages.py output is wrapped in
    <div class='table-wrapper'> so it can horizontally scroll on mobile without
    blowing out the page width. Closes baseline §1."""
    from build_pages import budget_page, materials_page, kitchen_page

    for fn, label in (
        (budget_page, "budget"),
        (materials_page, "materials"),
        (kitchen_page, "kitchen"),
    ):
        html = fn()
        n_tables = html.count('<table class="spec-table">')
        n_wrapped = html.count('<div class="table-wrapper"><table class="spec-table">')
        assert n_tables > 0, f"{label}: no spec-tables found, fixture stale?"
        assert n_tables == n_wrapped, (
            f"{label}: {n_tables} spec-tables but only {n_wrapped} table-wrappers"
        )


def test_sticky_offset_uses_topnav_h_variable():
    """.section-header scroll-margin-top references --topnav-h so anchor jumps
    land in the right place on mobile where the topnav is taller (baseline §8)."""
    from build_pages import SHARED_CSS

    assert "var(--topnav-h)" in SHARED_CSS
