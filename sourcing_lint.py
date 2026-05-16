# sourcing_lint.py
"""6 cross-cutting consistency lint checks for sourcing.yaml.
Each check returns a list of LintFinding objects."""
from dataclasses import dataclass
from typing import List, Optional

from sourcing_schema import Item

Severity = str  # "error" | "warning" | "info"


@dataclass
class LintFinding:
    severity: Severity
    message: str
    item_id: Optional[str] = None


def _item_text(item: Item) -> str:
    """Concatenated lower-cased text we lint against (decided_sku + options skus + notes)."""
    parts = [item.decided_sku or "", item.notes or ""]
    if item.options:
        for o in item.options:
            parts.append(o.sku)
            parts.append(o.reasoning)
    return " ".join(parts).lower()


def check_brass_finish(items: List[Item], expected_family: str) -> List[LintFinding]:
    """Warn if any brass-tagged item references a brass treatment outside the expected family.
    Expected family is e.g. 'Rejuvenation lacquered brass'."""
    findings = []
    expected_lower = expected_family.lower()
    expected_keywords = [w for w in expected_lower.split() if len(w) > 3]
    for item in items:
        if "lacquered_brass" not in item.cross_room_consistency and "brass" not in item.cross_room_consistency:
            continue
        text = _item_text(item)
        if "brass" not in text:
            continue  # tagged brass but text doesn't mention brass — nothing to lint against
        if not all(kw in text for kw in expected_keywords):
            findings.append(LintFinding(
                severity="warning",
                message=f"{item.id}: brass-tagged but doesn't match expected family '{expected_family}'",
                item_id=item.id,
            ))
    return findings


def check_wood_tone(items: List[Item], expected_treatment: str) -> List[LintFinding]:
    """Warn if a wood-tone item references treatment outside the expected family.
    Expected treatment is e.g. 'white_oak_bleach_rubio_pure' → looks for 'bleach' + 'rubio' or 'pure'."""
    findings = []
    keywords_needed = ["rubio"]  # the canonical signal
    forbidden = ["minwax", "stain", "espresso", "walnut stain", "poly", "polyurethane"]
    for item in items:
        if item.category not in ("paint_finish", "cabinetry_millwork", "furniture"):
            continue
        text = _item_text(item)
        # cabinetry_millwork is inherently wood — always lint it.
        # For other categories only lint if the text mentions oak or wood.
        if item.category != "cabinetry_millwork" and "oak" not in text and "wood" not in text:
            continue
        if any(f in text for f in forbidden):
            findings.append(LintFinding(
                severity="warning",
                message=f"{item.id}: wood treatment references forbidden term (expected '{expected_treatment}')",
                item_id=item.id,
            ))
            continue
        if not any(k in text for k in keywords_needed):
            # only complain if it's clearly a wood-finish item (paint_finish category) without rubio
            if item.category == "paint_finish":
                findings.append(LintFinding(
                    severity="warning",
                    message=f"{item.id}: wood-finish item missing rubio reference (expected '{expected_treatment}')",
                    item_id=item.id,
                ))
    return findings


def check_tile_palette(items: List[Item], allowed: List[str]) -> List[LintFinding]:
    """Error if a tile_stone item uses a 4th tile line or places Bejmat outside master bath."""
    findings = []
    allowed_keywords = {
        "cle_sea_salt_zellige": ["sea salt", "zellige"],
        "carrara_slab": ["carrara"],
        "cle_bejmat_master_only": ["bejmat"],
    }
    for item in items:
        if item.category != "tile_stone":
            continue
        text = _item_text(item)
        if not text.strip():
            continue
        matched_keys = set()
        for key, kws in allowed_keywords.items():
            if key in allowed and any(kw in text for kw in kws):
                matched_keys.add(key)
        if not matched_keys:
            # Mentions a tile not in the allowed palette
            findings.append(LintFinding(
                severity="error",
                message=f"{item.id}: tile not in allowed palette {allowed}",
                item_id=item.id,
            ))
        if "cle_bejmat_master_only" in matched_keys and item.room != "master_bath":
            findings.append(LintFinding(
                severity="error",
                message=f"{item.id}: Bejmat tile used outside master_bath (room={item.room})",
                item_id=item.id,
            ))
    return findings
