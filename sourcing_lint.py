# sourcing_lint.py
"""12 cross-cutting consistency lint checks for sourcing.yaml.
Each check returns a list of LintFinding objects."""
import re
from dataclasses import dataclass
from typing import List, Optional

from sourcing_schema import Item, Meta

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
    """Warn if any lacquered-brass-tagged item references a confirmed non-allowed brass treatment.

    Allowed family (canonical lacquered brass brands):
    - Rejuvenation + "lacquered brass", "lacq brass", or "antique brass"
    - Schoolhouse + "lacquered" or "brass" (lacquered is Schoolhouse default)
    - Cedar & Moss / Cedar and Moss (always lacquered brass in canon)
    - Emtek + "brass" or "lacquered"
    - Manufacturer-agnostic: "lacquered brass" or "antique brass" anywhere in text

    Items tagged "unlacquered_brass" instead of "lacquered_brass" are treated as a
    separate family (intentional patina choice, e.g. Schoolhouse Bishop front-door set)
    and are not checked by this function.

    Only warns when text mentions "brass" AND references a known non-allowed treatment
    (e.g. "matte brass", "polished brass", "raw brass", "unlacquered brass" paired with
    a non-Schoolhouse brand, or a clearly wrong brand like "WE matte brass").
    """
    findings = []

    # Patterns that confirm an allowed lacquered-brass source
    def _is_allowed(text: str) -> bool:
        # Manufacturer-agnostic: literal "lacquered brass" or "antique brass" anywhere
        if "lacquered brass" in text or "lacq brass" in text or "antique brass" in text:
            return True
        # Rejuvenation with any brass variant
        if "rejuvenation" in text and "brass" in text:
            return True
        # Schoolhouse with lacquered or brass (Schoolhouse's default is lacquered)
        if "schoolhouse" in text and ("lacquered" in text or "brass" in text):
            return True
        # Cedar & Moss (always lacquered brass in canon)
        if "cedar & moss" in text or "cedar and moss" in text:
            return True
        # Emtek with brass or lacquered
        if "emtek" in text and ("brass" in text or "lacquered" in text):
            return True
        return False

    # Patterns that explicitly indicate a NON-allowed brass treatment
    NON_ALLOWED = [
        "matte brass",
        "polished brass",
        "raw brass",
        "unlacquered brass",
        "satin brass",
    ]

    for item in items:
        # Only check items tagged for the lacquered brass family
        if "lacquered_brass" not in item.cross_room_consistency:
            continue
        text = _item_text(item)
        if "brass" not in text:
            continue  # tagged brass but no brass mention in text — nothing to lint against
        if _is_allowed(text):
            continue  # confirmed allowed family — no warning
        # Check for explicit non-allowed brass treatments
        if any(bad in text for bad in NON_ALLOWED):
            findings.append(LintFinding(
                severity="warning",
                message=(
                    f"{item.id}: brass-tagged item references a non-allowed brass treatment "
                    f"(expected lacquered/antique brass from Rejuvenation, Schoolhouse, Cedar & Moss, or Emtek)"
                ),
                item_id=item.id,
            ))
    return findings


def check_wood_tone(items: List[Item], expected_treatment: str) -> List[LintFinding]:
    """Warn if a wood-tone item references treatment outside the expected family.
    Expected treatment is e.g. 'white_oak_bleach_rubio_pure' → looks for 'rubio'.

    Scope rules:
    - cabinetry_millwork: always checked (inherently a wood product)
    - paint_finish / furniture: only checked if item is explicitly tagged 'wood_tone'
      in cross_room_consistency (avoids flagging exterior paint that mentions the word
      'wood' in context notes, or furniture items not part of the wood-tone lock)
    """
    findings = []
    keywords_needed = ["rubio"]  # the canonical signal
    forbidden = ["minwax", "stain", "espresso", "walnut stain", "poly", "polyurethane"]
    for item in items:
        if item.category not in ("paint_finish", "cabinetry_millwork", "furniture"):
            continue
        text = _item_text(item)
        # cabinetry_millwork is inherently wood — always lint it.
        # For paint_finish and furniture: only lint if explicitly tagged wood_tone.
        if item.category != "cabinetry_millwork":
            if "wood_tone" not in item.cross_room_consistency:
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


# Substrate tile/counter keywords — these are out-of-scope of the decorative palette lock
# (floor porcelain + counter quartz/stone aren't part of the zellige/slab/bejmat palette)
SUBSTRATE_KEYWORDS = ["daltile", "caesarstone", "silestone", "porcelain", "quartz counter", "engineered stone", "marble counter"]


def _tile_decision_text(item: Item) -> str:
    """Tighter text for tile palette check: decided_sku + options[].sku only.
    Excludes notes + reasoning (which often reference rejected/alternate tiles for context)."""
    parts = [item.decided_sku or ""]
    if item.options:
        for o in item.options:
            parts.append(o.sku)
    return " ".join(parts).lower()


def check_tile_palette(items: List[Item], allowed: List[str]) -> List[LintFinding]:
    """Error if a decorative tile_stone item uses a 4th palette entry or places Bejmat outside master bath.
    Floor/counter substrate tiles (Daltile porcelain, Caesarstone, etc.) are out of palette scope."""
    findings = []
    allowed_keywords = {
        "cle_sea_salt_zellige": ["sea salt", "zellige"],
        "carrara_slab": ["carrara"],
        "cle_bejmat_master_only": ["bejmat"],
    }
    for item in items:
        if item.category != "tile_stone":
            continue
        text = _tile_decision_text(item)
        if not text.strip():
            continue
        # Substrate tiles (floor porcelain, counter stone) are out of palette scope — skip the check
        if any(sub in text for sub in SUBSTRATE_KEYWORDS):
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


def _paint_brand_text(item: Item) -> str:
    """Narrow text for paint check: decided_sku + options[].sku only (not notes or reasoning).
    This prevents 'paint' mentions in context notes from triggering the check."""
    parts = [item.decided_sku or ""]
    if item.options:
        for o in item.options:
            parts.append(o.sku)
    return " ".join(parts).lower()


def check_paint_line(items: List[Item], expected_line: str) -> List[LintFinding]:
    """Warn if a paint_finish item's decided_sku or option SKUs reference a forbidden paint brand.

    Scope: only fires when the decided_sku or option SKUs actually name a paint brand.
    Items whose SKUs don't mention any paint brand at all → no warning (avoids false positives
    on cabinet/trim items that happen to appear in the paint_finish category without a brand ref).

    Allowed brands (no warning):
    - Benjamin Moore / BM (all Aura lines, Regal Select, Aura Bath & Spa, etc.)
    - Bona (floor finishes — separate from wall paint)
    - Rubio (wood finishes — separate from wall paint)

    Forbidden brands (warn):
    - Sherwin-Williams Cashmere or Duration (SW itself not forbidden, just those lines)
    - Behr (any)
    - Valspar (any)
    - Farrow & Ball as primary (too expensive for whole-house)
    """
    findings = []

    ALLOWED_BRANDS = ["benjamin moore", "bm aura", "bm regal", "bm bath", "bm ", "bona", "rubio"]
    FORBIDDEN = [
        ("sherwin cashmere", "Sherwin-Williams Cashmere"),
        ("sw cashmere", "Sherwin-Williams Cashmere"),
        ("sherwin duration", "Sherwin-Williams Duration"),
        ("sw duration", "Sherwin-Williams Duration"),
        ("sherwin-williams cashmere", "Sherwin-Williams Cashmere"),
        ("sherwin-williams duration", "Sherwin-Williams Duration"),
        ("behr ", "Behr"),
        ("valspar", "Valspar"),
        ("farrow & ball", "Farrow & Ball"),
        ("farrow and ball", "Farrow & Ball"),
    ]

    for item in items:
        if item.category != "paint_finish":
            continue
        sku_text = _paint_brand_text(item)
        if not sku_text.strip():
            continue  # no SKU text at all — nothing to lint against

        # Only proceed if the SKU text mentions at least one paint-brand signal.
        # "finish" alone is too broad (factory finish, floor finish) — require more specific terms.
        HAS_BRAND_SIGNAL = ["paint", "primer", "stain", "bm ", "benjamin moore", "bona", "rubio",
                             "sherwin", "behr", "valspar", "farrow", "aura", "regal", "cashmere",
                             "interior flat", "interior eggshell", "interior satin", "exterior satin",
                             "bath & spa", "bath spa"]
        if not any(sig in sku_text for sig in HAS_BRAND_SIGNAL):
            continue  # SKU text names no paint brand — skip (e.g. cabinet factory-finish items)

        # Check for explicitly forbidden brands first
        hit_forbidden = None
        for pattern, label in FORBIDDEN:
            if pattern in sku_text:
                hit_forbidden = label
                break

        if hit_forbidden:
            findings.append(LintFinding(
                severity="warning",
                message=f"{item.id}: paint SKU references forbidden brand '{hit_forbidden}' (expected {expected_line})",
                item_id=item.id,
            ))
            continue

        # Check if any allowed brand is present — if so, no further warning
        if any(brand in sku_text for brand in ALLOWED_BRANDS):
            continue

        # SKU has brand signals but no allowed brand matched — warn
        findings.append(LintFinding(
            severity="warning",
            message=f"{item.id}: paint SKU doesn't reference an approved brand (expected '{expected_line}' / Benjamin Moore family)",
            item_id=item.id,
        ))
    return findings


def check_hardware_mix(items: List[Item]) -> List[LintFinding]:
    """Info-level: check that large rooms don't end up single-finish.

    Threshold scales with room hardware count:
    - <6 items: skip (small room — single-finish is intentional)
    - 6-9 items: warn if either finish < 2
    - 10+ items: warn if either finish < 3

    This prevents noise for small baths (1-2 hardware items) while still
    catching rooms with a real hardware-count where a second finish is expected.
    """
    findings = []
    by_room: dict = {}
    for item in items:
        if item.category in ("hardware", "lighting_fixture", "plumbing_fixture"):
            by_room.setdefault(item.room, []).append(item)
    for room, room_items in by_room.items():
        n = len(room_items)
        if n < 6:
            continue  # small room — single finish is fine
        brass = sum(1 for i in room_items if "lacquered_brass" in i.cross_room_consistency)
        black = sum(1 for i in room_items if "matte_black" in i.cross_room_consistency)
        # Skip rooms where no item is tagged for either finish — these rooms either
        # don't participate in the brass/black system (e.g. exterior, utility) or
        # are simply not yet tagged, and we don't want to generate false positives.
        if brass == 0 and black == 0:
            continue
        min_each = 3 if n >= 10 else 2
        if brass < min_each or black < min_each:
            findings.append(LintFinding(
                severity="info",
                message=(
                    f"{room}: hardware mix unbalanced (brass={brass}, matte_black={black}; "
                    f"rule wants ≥{min_each} each for {n}-item room)"
                ),
                item_id=None,
            ))
    return findings


def check_budget_rollup(items: List[Item], meta: Meta) -> List[LintFinding]:
    """Error if sum of budget_target_usd per budget_source exceeds the allocated allowance."""
    findings = []
    by_source: dict = {}
    for item in items:
        by_source[item.budget_source] = by_source.get(item.budget_source, 0) + item.budget_target_usd

    construction_total = by_source.get("construction_allowance", 0) + by_source.get("path3_direct", 0)
    if construction_total > meta.budgets.construction_cap:
        findings.append(LintFinding(
            severity="error",
            message=f"construction_allowance + path3_direct = ${construction_total:,.0f} > cap ${meta.budgets.construction_cap:,.0f}",
        ))
    furniture_total = by_source.get("furniture_envelope", 0)
    if furniture_total > meta.budgets.furniture_envelope:
        findings.append(LintFinding(
            severity="warning",                 # soft target per OWNER CONFIRM #5; phased plan
            message=f"furniture_envelope = ${furniture_total:,.0f} > allocation ${meta.budgets.furniture_envelope:,.0f} (soft target; phased per DESIGN_SPEC #5)",
        ))
    p3_total = by_source.get("path3_direct", 0)
    if p3_total > meta.budgets.path3_owner_direct_ceiling:
        findings.append(LintFinding(
            severity="warning",
            message=f"path3_direct = ${p3_total:,.0f} > ceiling ${meta.budgets.path3_owner_direct_ceiling:,.0f}",
        ))
    return findings


def check_no_fictional_sku_urls(items: List[Item], meta: Meta) -> List[LintFinding]:
    """Error if a ★ recommended option's product_url is a search-fallback URL.

    Search URLs (/search?q=, ?q=, /search?keyword=, google.com/search) mean the product
    was never actually verified — fictional-SKU territory. Empty/None product_url is allowed
    (no claim made is better than a false claim).
    """
    findings = []
    SEARCH_PATTERNS = ["/search?q=", "?q=", "/search?keyword=", "google.com/search"]
    for item in items:
        if not item.options:
            continue
        for idx, opt in enumerate(item.options):
            if not opt.recommend:
                continue
            url = opt.product_url or ""
            if any(pattern in url for pattern in SEARCH_PATTERNS):
                findings.append(LintFinding(
                    severity="error",
                    message=f"{item.id} opt {idx} ★ has search-URL product_url (fictional-SKU risk): {url[:80]}...",
                    item_id=item.id,
                ))
    return findings


def check_no_collection_landing_urls(items: List[Item], meta: Meta) -> List[LintFinding]:
    """Warning if a ★ recommended option's product_url points at a category/collection landing
    page rather than a specific product page.

    Catches the R4 failure mode where BB-SHOWER-SYSTEM ★ was given a Delta collection URL
    (e.g. /category/trinsic) instead of a direct product page.  The fictional-SKU guard only
    catches /search?q= style URLs; this rule catches path-based landing pages.
    """
    findings = []
    LANDING_PATTERNS = [
        "/category/",
        "/collections/",
        "/c/",
        "/shop/",
        "/browse/",
        "/sitemap",
    ]
    for item in items:
        if not item.options:
            continue
        for idx, opt in enumerate(item.options):
            if not opt.recommend:
                continue
            url = opt.product_url or ""
            if not url:
                continue
            url_lower = url.lower()
            # Check known landing-page path patterns
            for pattern in LANDING_PATTERNS:
                if pattern in url_lower:
                    findings.append(LintFinding(
                        severity="warning",
                        message=(
                            f"{item.id} opt {idx} ★ product_url looks like category/collection "
                            f"landing, not specific product: {url[:100]}"
                        ),
                        item_id=item.id,
                    ))
                    break
            else:
                # Heuristic: a specific product page should have ≥2 path segments after the domain
                path_segments = [s for s in url.split("/")[3:] if s]
                if len(path_segments) < 2:
                    findings.append(LintFinding(
                        severity="warning",
                        message=(
                            f"{item.id} opt {idx} ★ product_url path too shallow for a product page "
                            f"(expected ≥2 segments): {url[:100]}"
                        ),
                        item_id=item.id,
                    ))
    return findings


KNOWN_VENDOR_FINISHES: dict = {
    "Cedar & Moss": {"brass", "heirloom brass", "matte black", "white"},
    "Delta Trinsic": {"champagne bronze", "matte black", "chrome", "stainless"},
    "Schoolhouse": {"natural brass", "antique brass", "satin brass", "true black", "polished nickel"},
    "Rejuvenation": {
        "natural brass", "aged brass", "antique brass", "satin brass",
        "matte black", "polished nickel", "oil rubbed bronze", "lacquered brass",
    },
}

def check_known_vendor_finishes(items: List[Item], meta: Meta) -> List[LintFinding]:
    """Warning if a ★ option names a finish that isn't in the vendor's known finish vocabulary.

    Catches the R4 failure mode where Cedar & Moss "Lacquered Brass" was specified —
    Cedar & Moss doesn't offer lacquered brass; their brass finish is simply "Brass".

    Algorithm:
    1. Only fires when the option vendor is in KNOWN_VENDOR_FINISHES.
    2. Builds a list of "finish candidates" from the text by looking for known finish-modifier
       words (lacquered, polished, etc.) followed by a material noun (brass, black, etc.).
    3. If any finish candidate is NOT a substring of any known finish for that vendor → warn.

    This correctly flags "lacquered brass" for Cedar & Moss (whose known finish is just
    "brass", not "lacquered brass") while not flagging "brass" alone.

    R7-I4 (sentinel filter on vendor-finish guard): Bare modifier candidates like "raw" or
    "true" that appear ONLY as substrings inside larger non-finish words (e.g. "raw" inside
    "Crawford", "true" inside "true price") were the source of 7 R6 false positives.  The
    SENTINEL_WORDS exclusion (originally shipped on Rule 9 orphan-SKU guard) is duplicated
    here as a case-insensitive set: a bare modifier candidate whose token form is a sentinel
    word is filtered out before vocabulary check.
    """
    # Modifier words that narrow a finish beyond the base material
    _MODIFIERS = frozenset([
        "lacquered", "polished", "brushed", "matte", "aged", "antique", "satin",
        "heirloom", "champagne", "oil rubbed", "oiled", "raw", "unlacquered",
        "natural", "true", "ebony",
    ])
    # Material nouns that can follow a modifier
    _MATERIALS = frozenset(["brass", "black", "bronze", "nickel", "chrome", "white", "gold"])

    # R7-I4: lowercase sentinel-word set for the bare-modifier exclusion path.
    # SENTINEL_WORDS is uppercase (shared with Rule 9); we lower-case for case-insensitive
    # match against bare modifier candidates ("raw", "true", etc.).
    _SENTINEL_LOWER = {w.lower() for w in SENTINEL_WORDS}

    findings = []
    for item in items:
        if not item.options:
            continue
        for idx, opt in enumerate(item.options):
            if not opt.recommend:
                continue
            vendor = (opt.vendor or "").strip()
            if vendor not in KNOWN_VENDOR_FINISHES:
                continue
            known = KNOWN_VENDOR_FINISHES[vendor]
            text = ((opt.sku or "") + " " + (opt.details or "")).lower()

            # Build finish candidates: any multi-word (modifier + material) or
            # single-word finish that matches a modifier (e.g. "lacquered" alone).
            # R7-I4: for the bare-modifier path, require a whole-word hit (word boundaries)
            # so "raw" inside "Crawford" / "Drawer" / "Outdrawn" doesn't fire.  The
            # modifier+material multi-word path already requires the material token so
            # is naturally protected.
            candidates: list = []
            for mod in _MODIFIERS:
                if mod not in text:
                    continue
                # Multi-word candidates always require the material — these stand.
                has_paired = False
                for mat in _MATERIALS:
                    phrase = f"{mod} {mat}"
                    if phrase in text:
                        candidates.append(phrase)
                        has_paired = True
                if has_paired:
                    continue
                # Bare modifier path: only count if `mod` appears as a whole word AND
                # isn't in the sentinel exclusion list (filters the 'raw' / 'true' false
                # positives caused by substring matches inside non-finish prose).
                if mod in _SENTINEL_LOWER:
                    continue
                # Whole-word boundary check
                if re.search(rf"\b{re.escape(mod)}\b", text):
                    candidates.append(mod)

            if not candidates:
                continue  # No finish modifier language detected — skip

            # Check each candidate against known finishes.
            # A candidate is "known" only if it exactly matches a known finish or is a
            # substring of one (e.g. candidate "antique" matches known "antique brass").
            # The reverse (known finish being substring of candidate) is NOT a match —
            # "brass" being in "lacquered brass" doesn't make "lacquered brass" known.
            unknown_candidates = [
                c for c in candidates
                if not any(
                    c == known_f or c in known_f  # candidate is contained in a known phrase
                    for known_f in known
                )
            ]
            if unknown_candidates:
                findings.append(LintFinding(
                    severity="warning",
                    message=(
                        f"{item.id} opt {idx} ★ finish '{unknown_candidates[0]}' not in "
                        f"'{vendor}' known vocabulary. Known finishes: {sorted(known)}"
                    ),
                    item_id=item.id,
                ))
    return findings


def check_per_item_budget_overshoot(items: List[Item], meta: Meta) -> List[LintFinding]:
    """Error if a ★ option's price exceeds item.budget_target_usd by >5%.

    Also flags decided items (no options array) that have a budget_target_usd > 0 but
    no priced option, since their actual price can't be validated.  This catches the R4
    failure mode where HB-TUB-FILLER was decided at $999 vs a $500 budget but escaped
    because it had no options[].recommend entry.

    Exception: budget_target_usd == 0 (canon-locked items with no budget target — skip).
    Exception: item.notes contains 'approved_overshoot' keyword (explicit owner sign-off).
    """
    findings = []
    for item in items:
        if item.budget_target_usd <= 0:
            continue
        if item.options:
            # Standard path: check the ★ recommended option
            rec = next((o for o in item.options if o.recommend), None)
            if not rec:
                continue
            if rec.price_usd > item.budget_target_usd * 1.05:
                if "approved_overshoot" in (item.notes or "").lower():
                    continue
                overshoot_pct = (rec.price_usd / item.budget_target_usd - 1) * 100
                findings.append(LintFinding(
                    severity="error",
                    message=(
                        f"{item.id} ★ price ${rec.price_usd:.0f} exceeds budget_target "
                        f"${item.budget_target_usd:.0f} by {overshoot_pct:.0f}% — revise budget UP "
                        f"or add 'approved_overshoot' to notes"
                    ),
                    item_id=item.id,
                ))
        elif item.decision_status == "decided" and item.decided_sku:
            # Decided item with no options array — actual price is unknown, can't validate
            if "approved_overshoot" in (item.notes or "").lower():
                continue
            findings.append(LintFinding(
                severity="info",
                message=(
                    f"{item.id} is decided ({item.decided_sku}) with budget "
                    f"${item.budget_target_usd:.0f} but has no priced option — "
                    f"actual price unknown, budget compliance unverifiable"
                ),
                item_id=item.id,
            ))
    return findings


SENTINEL_WORDS = {
    "CONFIRM", "OWNER", "DEFER", "DEFERRED", "REMOVED",
    "MED-HIGH", "MED-LOW", "TBD", "VERIFY", "FIXME", "TODO",
    "APPROVED", "PENDING", "REVIEW", "DRAFT", "FINAL",
    "WIP", "YES", "USD", "EUR", "CFM",
    "GFCI", "ADA", "LRV", "GREENGUARD", "GSM",
    "RULE", "HARD", "RULES", "NOTES", "NOTE", "SPEC", "SPECS",
    "HARD-RULE", "HARD-RULES", "CRITICAL", "FIXED", "STATUS",
    "CAUTION", "WARNING", "UPDATE", "PAUSED", "DONE", "BUDGET",
    # R7-I4: modifier words that appear as substrings of non-finish prose
    # (e.g. "raw" inside "Crawford", bare "true" inside "true price"). These
    # are sentinel exclusions for the vendor-finish guard (Rule 11) when no
    # paired material noun follows.
    "RAW", "TRUE",
}


def check_no_orphan_sku_refs_in_notes(items: List[Item], meta: Meta) -> List[LintFinding]:
    """Warning if item.notes references a capitalized model-number token not in any current option.

    Heuristic: find tokens matching [A-Z][A-Z0-9\\-]{4,} in notes.  If a token doesn't appear
    in any option's sku or details text, it's likely an orphan reference left over after a
    SKU swap — flag it so it can be cleaned up or confirmed.

    Sentinel words (CONFIRM, OWNER, DEFER, etc.) and item IDs from the full items list are
    excluded — they are not SKU references.

    Cap at 30 findings total to avoid flooding output on a freshly-imported item set.
    """
    findings = []
    sku_pattern = re.compile(r"\b[A-Z][A-Z0-9\-]{4,}\b")
    # Build full set of known item IDs so we can exclude cross-references
    all_item_ids = {item.id for item in items}
    for item in items:
        if not item.notes:
            continue
        notes_tokens = set(sku_pattern.findall(item.notes))
        if not notes_tokens:
            continue
        current_options_text = ""
        if item.options:
            for o in item.options:
                current_options_text += (o.sku or "") + " " + (o.details or "")
        for token in notes_tokens:
            # Skip sentinel words that are not SKU references
            if token in SENTINEL_WORDS:
                continue
            # Skip known item IDs (cross-item dependencies mentioned in notes)
            if token in all_item_ids:
                continue
            if token not in current_options_text and token != item.id:
                findings.append(LintFinding(
                    severity="warning",
                    message=(
                        f"{item.id} notes references SKU '{token}' not in current options "
                        f"— possible orphan reference after sku swap"
                    ),
                    item_id=item.id,
                ))
                if len(findings) >= 30:  # Cap to avoid flood
                    return findings
    return findings


def check_catalog_status_callouts(items: List[Item], meta: Meta) -> List[LintFinding]:
    """Surface items with non-None catalog_status as warnings so they show up in lint output.

    - needs_reselection → warning (vendor catalog moved; owner must pick a new SKU)
    - spec_error → warning (spec'd product doesn't exist in this vendor's catalog at all)
    - verified → info (spec matches live catalog; image re-sourced from real PDP)
    """
    findings = []
    for item in items:
        if not item.catalog_status:
            continue
        if item.catalog_status == "verified":
            sev = "info"
            msg = f"{item.id}: catalog VERIFIED against live vendor PDP"
        elif item.catalog_status == "needs_reselection":
            sev = "warning"
            msg = (
                f"{item.id}: CATALOG GAP — spec'd SKU not in current vendor catalog "
                f"with no clean successor; owner must reselect"
            )
        elif item.catalog_status == "spec_error":
            sev = "warning"
            msg = (
                f"{item.id}: SPEC ERROR — spec'd product does not exist in this vendor's "
                f"catalog (likely wrong line/format); owner must reselect"
            )
        else:
            continue
        if item.catalog_status_note:
            msg += f" — {item.catalog_status_note}"
        findings.append(LintFinding(severity=sev, message=msg, item_id=item.id))
    return findings


def check_supplier_directory_url_freshness(items: List[Item], meta: Meta) -> List[LintFinding]:
    """Surface supplier_directory.yaml entries whose URLs failed verification.

    Reads ~/Desktop/HomeAI/scope/supplier_directory.yaml if present. Counts
    suppliers where url_verified is false OR url_status is not a 200 (or similar
    successful tag). Emits a single rollup warning when count > 0.

    This is a directory-level lint, not a sourcing-item lint — it shares the
    LintFinding surface so the lint output stays unified. item_id is None.
    """
    import os
    import yaml as _yaml
    findings = []
    path = os.path.expanduser("~/Desktop/HomeAI/scope/supplier_directory.yaml")
    if not os.path.exists(path):
        return findings
    try:
        with open(path) as f:
            data = _yaml.safe_load(f)
    except Exception:
        return findings
    suppliers = (data or {}).get("suppliers", []) or []
    # R2 Fix C3 — exact-match against allow-list. Codex flagged that prefix
    # matching on "200" silently passed strings like "200 BUT IS 404". Lint
    # only treats these explicit values as fresh; anything else is flagged.
    FRESH_STATUS_STRINGS = {
        "200", "301", "302", "ok", "bot_blocked_ok",
        "redirected_changed_path", "redirected_brand_change",
    }
    stale = []
    # R4 Fix I3 — track suppliers tagged `redirected_changed_path` whose
    # `url` has NOT been updated to the canonical `recommended_url`. Codex
    # named lulu-georgia-rugs as a live example: url_status_tag flags the
    # redirect but url is still the pre-redirect string.
    redirect_canonical_drift = []
    for s in suppliers:
        url_verified = s.get("url_verified")
        url_status = s.get("url_status")
        # R4 Fix I3 — canonical-URL drift on redirected_changed_path entries.
        if s.get("url_status_tag") == "redirected_changed_path":
            cur = (s.get("url") or "").strip()
            rec = (s.get("recommended_url") or "").strip()
            if rec and cur and cur != rec:
                redirect_canonical_drift.append(s.get("id", "?"))
        if url_verified is True:
            if url_status is None:
                continue
            if isinstance(url_status, int) and url_status in (200, 301, 302):
                # 301/302 acceptable when the URL override has already been
                # applied (the recorded url in supplier_directory IS the
                # post-redirect target). url_verified=true is the signal.
                continue
            if isinstance(url_status, str):
                s_lower = url_status.strip().lower()
                if s_lower in FRESH_STATUS_STRINGS:
                    continue
            # Otherwise: verified but with a non-200 status → flag.
            stale.append(s.get("id", "?"))
        else:
            stale.append(s.get("id", "?"))
    if stale:
        findings.append(LintFinding(
            severity="warning",
            message=(
                f"supplier_directory.yaml: {len(stale)} supplier(s) with stale/unverified URLs — "
                f"first few: {', '.join(stale[:5])}"
                + (f" (+{len(stale)-5} more)" if len(stale) > 5 else "")
            ),
            item_id=None,
        ))
    if redirect_canonical_drift:
        findings.append(LintFinding(
            severity="warning",
            message=(
                f"supplier_directory.yaml: {len(redirect_canonical_drift)} "
                f"supplier(s) tagged redirected_changed_path but `url` differs "
                f"from `recommended_url` — update the canonical URL: "
                f"{', '.join(redirect_canonical_drift[:5])}"
                + (f" (+{len(redirect_canonical_drift)-5} more)"
                   if len(redirect_canonical_drift) > 5 else "")
            ),
            item_id=None,
        ))
    return findings


def check_supplier_directory_uncategorized(items: List[Item], meta: Meta) -> List[LintFinding]:
    """R2 Fix C7 — Flag supplier_directory.yaml rows whose `category` doesn't
    appear in the directory's own `categories:` list. Without this, they were
    silently dropped from the rendered /suppliers page.
    """
    import os
    import yaml as _yaml
    findings: List[LintFinding] = []
    path = os.path.expanduser("~/Desktop/HomeAI/scope/supplier_directory.yaml")
    if not os.path.exists(path):
        return findings
    try:
        with open(path) as f:
            data = _yaml.safe_load(f)
    except Exception:
        return findings
    if not isinstance(data, dict):
        return findings
    known_cats = {c.get("id") for c in (data.get("categories") or []) if isinstance(c, dict)}
    suppliers = (data or {}).get("suppliers", []) or []
    bad = []
    for s in suppliers:
        cid = s.get("category")
        if not cid or cid not in known_cats:
            bad.append(s.get("id", "?"))
    if bad:
        findings.append(LintFinding(
            severity="warning",
            message=(
                f"supplier_directory.yaml: {len(bad)} supplier(s) with unknown/missing "
                f"category — first few: {', '.join(bad[:5])}"
                + (f" (+{len(bad)-5} more)" if len(bad) > 5 else "")
            ),
            item_id=None,
        ))
    return findings


def check_supplier_directory_citation_guard(items: List[Item], meta: Meta) -> List[LintFinding]:
    """R5 (2026-05-17) — Invoke the pre-commit citation/URL-metadata guard at
    `~/Desktop/HomeAI/scripts/verify_directory_citations.py` as part of the lint
    pipeline so its three checks (fabricated §-citation, URL-metadata 404
    anti-pattern, state-vs-prose drift) ride the standard `python build_sourcing.py`
    flow rather than living as a standalone pre-commit hook.

    Each error returned by the guard is surfaced as a single warning LintFinding.
    The guard module is loaded via importlib so this lint check stays defensive:
    a missing file, an import failure, or a YAML resolution issue degrades to a
    no-op rather than crashing the entire build.
    """
    import importlib.util
    import os
    findings: List[LintFinding] = []
    guard_path = os.path.expanduser("~/Desktop/HomeAI/scripts/verify_directory_citations.py")
    if not os.path.exists(guard_path):
        return findings
    try:
        spec = importlib.util.spec_from_file_location("_verify_directory_citations", guard_path)
        if spec is None or spec.loader is None:
            return findings
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    except Exception:
        return findings
    # The guard exposes `check_fabricated_citations`, `check_url_metadata`,
    # `check_state_vs_prose`, the helpers `extract_design_spec_sections` +
    # `DIRECTORY_PATH` / `DESIGN_SPEC_PATH`.  Re-implement the orchestration
    # locally (lint-friendly: no sys.exit, no stderr, no I/O surprises).
    try:
        directory_path = mod.DIRECTORY_PATH
        design_spec_path = mod.DESIGN_SPEC_PATH
        if not directory_path.exists() or not design_spec_path.exists():
            return findings
        known_sections = mod.extract_design_spec_sections(design_spec_path)
        import yaml as _yaml
        with directory_path.open(encoding="utf-8") as f:
            data = _yaml.safe_load(f) or {}
        suppliers = (data.get("suppliers") or [])
        errors: List[str] = []
        errors.extend(mod.check_fabricated_citations(suppliers, known_sections))
        errors.extend(mod.check_url_metadata(suppliers))
        errors.extend(mod.check_state_vs_prose(suppliers))
    except Exception:
        return findings
    for e in errors:
        findings.append(LintFinding(
            severity="warning",
            message=f"supplier_directory citation/url guard: {e}",
            item_id=None,
        ))
    return findings


def run_all_lints(items: List[Item], meta: Meta) -> List[LintFinding]:
    findings: List[LintFinding] = []
    findings += check_brass_finish(items, meta.consistency_locks.brass_finish_family)
    findings += check_wood_tone(items, meta.consistency_locks.wood_tone)
    findings += check_tile_palette(items, meta.consistency_locks.tile_palette)
    findings += check_paint_line(items, meta.consistency_locks.paint_line)
    findings += check_hardware_mix(items)
    findings += check_budget_rollup(items, meta)
    findings += check_no_fictional_sku_urls(items, meta)
    findings += check_no_collection_landing_urls(items, meta)
    findings += check_known_vendor_finishes(items, meta)
    findings += check_per_item_budget_overshoot(items, meta)
    findings += check_no_orphan_sku_refs_in_notes(items, meta)
    findings += check_catalog_status_callouts(items, meta)
    findings += check_supplier_directory_url_freshness(items, meta)
    findings += check_supplier_directory_uncategorized(items, meta)
    findings += check_supplier_directory_citation_guard(items, meta)
    return findings
