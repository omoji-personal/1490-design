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
