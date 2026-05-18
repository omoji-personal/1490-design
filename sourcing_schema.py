"""Schema + validation for sourcing.yaml. Three row variants:
- Standard item: options array present, decided_sku may be null
- Vintage item: vintage_brief present, no options
- Canon-locked: status=decided, decided_sku set, no options, no vintage_brief
"""
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

VALID_CATEGORIES = {
    "plumbing_fixture", "lighting_fixture", "hardware", "tile_stone",
    "cabinetry_millwork", "appliance", "paint_finish", "window_treatment",
    "furniture", "decor_softgoods",
}
VALID_ROOMS = {
    "kitchen", "master_br", "master_bath", "hall_bath", "basement_bath",
    "lr", "dining", "office", "nursery", "mudroom_carport", "basement",
    "exterior", "common",
}
VALID_URGENCY = {"T0", "T1", "T2", "T3"}
VALID_BUDGET_SOURCES = {"construction_allowance", "furniture_envelope", "path3_direct"}
VALID_ACTORS = {"tcw", "owner_direct", "owner_furniture", "vintage_hunt"}
VALID_STATUSES = {
    "stub", "options_drafted", "awaiting_sample", "sample_in_hand",
    "decided", "ordered", "received", "installed",
    "deferred_p2", "cancelled",
    # vintage-only states
    "watch_list", "found_candidate",
}

# Catalog reconciliation flags (set when vendor catalog disagrees with spec).
# - "verified": spec matches live catalog, image confirmed at PDP (informational)
# - "needs_reselection": spec'd SKU is gone with no clean successor; owner must reselect
# - "spec_error": spec'd product/format doesn't exist in this vendor's catalog at all
VALID_CATALOG_STATUSES = {"verified", "needs_reselection", "spec_error"}


class ValidationError(Exception):
    pass


@dataclass
class Option:
    sku: str
    vendor: str
    price_usd: float
    image: str
    reasoning: str
    recommend: bool = False
    details: Optional[str] = None          # NEW
    product_url: Optional[str] = None      # NEW


@dataclass
class VintageBrief:
    style: str
    not_: str
    target_price_usd: str
    hunt_venues: List[str]
    aspirational_refs: List[str]


@dataclass
class Item:
    id: str
    title: str
    category: str
    room: str
    urgency: str
    lead_time_weeks: int
    budget_source: str
    budget_target_usd: float
    sourcing_actor: str
    decision_status: str
    annika_loop: bool
    cross_room_consistency: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    sample_required: bool = False
    options: Optional[List[Option]] = None
    vintage_brief: Optional[VintageBrief] = None
    decided_sku: Optional[str] = None
    ordered_date: Optional[str] = None
    received_date: Optional[str] = None
    installed_date: Optional[str] = None
    notes: str = ""
    revision_history: List[Dict[str, str]] = field(default_factory=list)
    # Top-level image — used for canon-decided items (no options/vintage_brief)
    # so locked-in selections can show their representative product photo.
    image: Optional[str] = None
    # Catalog reconciliation flag — None for normal items. Set when vendor
    # catalog disagrees with spec (see VALID_CATALOG_STATUSES).
    catalog_status: Optional[str] = None
    catalog_status_note: Optional[str] = None
    # Top-level vendor attribution — used for canon-decided items where the
    # vendor lives in `decided_sku` prose only (no options[] to read .vendor
    # from). Drives /vendors-page bucketing so canon-decided $ doesn't fall
    # into the "(other / TCW / specialty)" bucket by default.
    vendor: Optional[str] = None


@dataclass
class Budgets:
    construction_cap: int
    furniture_envelope: int
    path3_owner_direct_ceiling: int


@dataclass
class ConsistencyLocks:
    brass_finish_family: str
    wood_tone: str
    tile_palette: List[str]
    paint_line: str


@dataclass
class Meta:
    last_updated: str
    budgets: Budgets
    consistency_locks: ConsistencyLocks


def parse_option(raw: Dict[str, Any]) -> Option:
    return Option(
        sku=raw["sku"],
        vendor=raw["vendor"],
        price_usd=float(raw["price_usd"]),
        image=raw.get("image", ""),
        reasoning=raw["reasoning"],
        recommend=bool(raw.get("recommend", False)),
        details=raw.get("details"),                 # NEW
        product_url=raw.get("product_url"),         # NEW
    )


def parse_vintage_brief(raw: Dict[str, Any]) -> VintageBrief:
    return VintageBrief(
        style=raw["style"],
        not_=raw.get("not", ""),
        target_price_usd=str(raw.get("target_price_usd", "")),
        hunt_venues=list(raw.get("hunt_venues", [])),
        aspirational_refs=list(raw.get("aspirational_refs", [])),
    )


def parse_item(raw: Dict[str, Any]) -> Item:
    # Validate enums
    if raw["category"] not in VALID_CATEGORIES:
        raise ValidationError(f"{raw.get('id', '?')}: invalid category '{raw['category']}'")
    if raw["room"] not in VALID_ROOMS:
        raise ValidationError(f"{raw.get('id', '?')}: invalid room '{raw['room']}'")
    if raw["urgency"] not in VALID_URGENCY:
        raise ValidationError(f"{raw.get('id', '?')}: invalid urgency '{raw['urgency']}'")
    if raw["budget_source"] not in VALID_BUDGET_SOURCES:
        raise ValidationError(f"{raw.get('id', '?')}: invalid budget_source '{raw['budget_source']}'")
    if raw["sourcing_actor"] not in VALID_ACTORS:
        raise ValidationError(f"{raw.get('id', '?')}: invalid sourcing_actor '{raw['sourcing_actor']}'")
    if raw["decision_status"] not in VALID_STATUSES:
        raise ValidationError(f"{raw.get('id', '?')}: invalid decision_status '{raw['decision_status']}'")
    if raw.get("catalog_status") is not None and raw["catalog_status"] not in VALID_CATALOG_STATUSES:
        raise ValidationError(
            f"{raw.get('id', '?')}: invalid catalog_status '{raw['catalog_status']}' "
            f"(allowed: {sorted(VALID_CATALOG_STATUSES)})"
        )

    options = [parse_option(o) for o in raw["options"]] if raw.get("options") else None
    vintage = parse_vintage_brief(raw["vintage_brief"]) if raw.get("vintage_brief") else None

    # Variant validation: exactly one of (options) or (vintage_brief) or (canon-locked decided)
    # Exception: stub rows are placeholders by definition (hidden from site) — allowed bare.
    canon_locked = (
        raw["decision_status"] == "decided"
        and raw.get("decided_sku") is not None
        and options is None
        and vintage is None
    )
    is_stub = raw["decision_status"] == "stub"
    if not canon_locked and not is_stub and options is None and vintage is None:
        raise ValidationError(
            f"{raw.get('id', '?')}: must have either options, vintage_brief, "
            f"or (decision_status=decided AND decided_sku set), or decision_status=stub"
        )
    if options is not None and vintage is not None:
        raise ValidationError(f"{raw.get('id', '?')}: cannot have both options and vintage_brief")

    return Item(
        id=raw["id"],
        title=raw["title"],
        category=raw["category"],
        room=raw["room"],
        urgency=raw["urgency"],
        lead_time_weeks=int(raw["lead_time_weeks"]),
        budget_source=raw["budget_source"],
        budget_target_usd=float(raw["budget_target_usd"]),
        sourcing_actor=raw["sourcing_actor"],
        decision_status=raw["decision_status"],
        annika_loop=bool(raw["annika_loop"]),
        cross_room_consistency=list(raw.get("cross_room_consistency", [])),
        dependencies=list(raw.get("dependencies", [])),
        sample_required=bool(raw.get("sample_required", False)),
        options=options,
        vintage_brief=vintage,
        decided_sku=raw.get("decided_sku"),
        ordered_date=raw.get("ordered_date"),
        received_date=raw.get("received_date"),
        installed_date=raw.get("installed_date"),
        notes=raw.get("notes", ""),
        revision_history=list(raw.get("revision_history", [])),
        image=raw.get("image"),
        catalog_status=raw.get("catalog_status"),
        catalog_status_note=raw.get("catalog_status_note"),
        vendor=raw.get("vendor"),
    )


# ---------------------------------------------------------------------------
# Supplier directory schema (R2 Fix C2)
# ---------------------------------------------------------------------------
# Validates ~/Desktop/HomeAI/scope/supplier_directory.yaml. Unlike sourcing.yaml
# (decision tracker), the supplier_directory is a *browse map* across 15 design
# categories. /suppliers consumes it directly. Adding a typed dataclass + parser
# lets the renderer/lint pipeline fail loud on malformed entries.

VALID_PRICE_TIERS = {"entry", "mid", "premium", "aspirational"}
VALID_FITS = {"STRONG", "GOOD", "MIXED", "CANON-ADJACENT", "WATCH_LIST"}
# R4 Fix V1 — canonical supplier-directory category vocabulary. parse_supplier()
# enforces membership so direct probes can't slip an unknown category past the
# loader-level check. Kept aligned with supplier_directory.yaml `categories:`
# and the _SUPPLIER_CATEGORY_SCOPE map in sourcing_render_html.py.
VALID_SUPPLIER_CATEGORIES = {
    "furniture-seating", "furniture-tables", "furniture-bedroom",
    "lighting", "tile", "plumbing", "hardware", "paint", "cabinetry",
    "counters", "appliances", "rugs", "decor-art", "window-treatments",
    "outdoor", "hvac", "smart_home",
}


@dataclass
class Supplier:
    id: str
    category: str
    name: str
    url: str
    price_tier: str
    fit: str
    style_fingerprint: str
    fit_for_project: str
    # Optional / variable fields
    off_canon_warning: Optional[str] = None
    collections_to_browse: List[Dict[str, Any]] = field(default_factory=list)
    lead_time_typical: Optional[str] = None
    sample_policy: Optional[str] = None
    notes: Optional[str] = None
    # R2 Fix UX4: operator_notes is OPERATOR-INTERNAL and must NEVER render in
    # user-facing HTML. The schema accepts it so YAML can carry context, but
    # render_suppliers_page() must not surface it.
    operator_notes: Optional[str] = None
    url_verified: Optional[bool] = None
    url_status: Any = None  # int or str
    hero_image: Optional[str] = None
    hero_image_source_url: Optional[str] = None
    hero_image_source: Optional[str] = None
    price_validation: List[Dict[str, Any]] = field(default_factory=list)
    price_range_typical: Dict[str, Any] = field(default_factory=dict)
    justification: Optional[str] = None
    canon_classification_basis: Optional[str] = None
    canon_classification_reasoning: Optional[str] = None
    url_status_note: Optional[str] = None
    verification_source_batch: Optional[str] = None
    # R4 Fix I2 — round-trip URL verification metadata. Codex R3 flagged that
    # `recommended_url`, `url_status_tag`, and `price_validation_status` were
    # dropped by the loader, breaking lint's canonical-URL check and any
    # downstream tool that needs to see post-verification corrections.
    recommended_url: Optional[str] = None
    url_status_tag: Optional[str] = None
    price_validation_status: Optional[str] = None


def parse_supplier(raw: Dict[str, Any]) -> Supplier:
    """Validate and parse a supplier dict. Raises ValidationError on missing or
    invalid required fields. Unknown keys are tolerated (forward-compat with
    Alpha-introduced fields).

    R4 Fix V1 — strict required-field validation now lives HERE, not only in
    `load_supplier_directory()`. Codex R3 flagged that a direct probe of
    `parse_supplier({"category": "not-a-real-category", ...})` was accepted
    and `url: None` was stringified to literal `"None"`. The loader caught
    these against the file's `categories:` list and via a downstream null
    check, but the dataclass parser itself was permissive. R4 closes that
    gap by:
      (a) raising on null/missing/non-string url (was stringified)
      (b) raising on category not in VALID_SUPPLIER_CATEGORIES
      (c) raising on null/missing/non-string style_fingerprint / fit_for_project
    """
    if not isinstance(raw, dict):
        raise ValidationError(f"supplier must be a dict, got {type(raw).__name__}")
    sid = raw.get("id")
    if not sid or not isinstance(sid, str):
        raise ValidationError(f"supplier missing or non-string id: {raw!r}")
    name = raw.get("name")
    if not name or not isinstance(name, str):
        raise ValidationError(f"{sid}: supplier missing or non-string name")
    category = raw.get("category")
    if not category or not isinstance(category, str):
        raise ValidationError(f"{sid}: supplier missing or non-string category")
    # R4 Fix V1 (b) — category membership check moved earlier into parse_supplier.
    if category not in VALID_SUPPLIER_CATEGORIES:
        raise ValidationError(
            f"{sid}: unknown supplier category {category!r} "
            f"(allowed: {sorted(VALID_SUPPLIER_CATEGORIES)})"
        )
    price_tier = raw.get("price_tier")
    if price_tier not in VALID_PRICE_TIERS:
        raise ValidationError(
            f"{sid}: invalid price_tier {price_tier!r} (allowed: {sorted(VALID_PRICE_TIERS)})"
        )
    fit = raw.get("fit")
    if fit not in VALID_FITS:
        raise ValidationError(
            f"{sid}: invalid fit {fit!r} (allowed: {sorted(VALID_FITS)})"
        )
    # R4 Fix V1 (a) — url null/empty handled here instead of letting it
    # stringify through to literal "None" downstream.
    raw_url = raw.get("url")
    if raw_url is None or (isinstance(raw_url, str) and not raw_url.strip()):
        raise ValidationError(
            f"{sid}: supplier has null/empty url — every directory entry must "
            f"point somewhere (set url to '#' if intentionally absent)."
        )
    if not isinstance(raw_url, str):
        raise ValidationError(
            f"{sid}: supplier url must be a string, got {type(raw_url).__name__}"
        )
    # R4 Fix V1 (c) — required display fields validated at parse-time.
    # R5 Fix I1 — also reject non-string values BEFORE stringification. Lists,
    # dicts, ints etc. used to silently become "[]"/"{}"/"123" via str(), which
    # poisoned card render. Type-check first, then content-check.
    raw_sf = raw.get("style_fingerprint")
    if raw_sf is None:
        raise ValidationError(
            f"{sid}: supplier has null/empty style_fingerprint — required for card render."
        )
    if not isinstance(raw_sf, str):
        raise ValidationError(
            f"{sid}: supplier style_fingerprint must be a string, "
            f"got {type(raw_sf).__name__}"
        )
    if not raw_sf.strip():
        raise ValidationError(
            f"{sid}: supplier has null/empty style_fingerprint — required for card render."
        )
    raw_ffp = raw.get("fit_for_project")
    if raw_ffp is None:
        raise ValidationError(
            f"{sid}: supplier has null/empty fit_for_project — required for card render."
        )
    if not isinstance(raw_ffp, str):
        raise ValidationError(
            f"{sid}: supplier fit_for_project must be a string, "
            f"got {type(raw_ffp).__name__}"
        )
    if not raw_ffp.strip():
        raise ValidationError(
            f"{sid}: supplier has null/empty fit_for_project — required for card render."
        )
    return Supplier(
        id=sid,
        category=category,
        name=name,
        url=raw_url,
        price_tier=price_tier,
        fit=fit,
        style_fingerprint=raw_sf,
        fit_for_project=raw_ffp,
        off_canon_warning=raw.get("off_canon_warning"),
        collections_to_browse=list(raw.get("collections_to_browse") or []),
        lead_time_typical=raw.get("lead_time_typical"),
        sample_policy=raw.get("sample_policy"),
        notes=raw.get("notes"),
        operator_notes=raw.get("operator_notes"),
        url_verified=raw.get("url_verified"),
        url_status=raw.get("url_status"),
        hero_image=raw.get("hero_image"),
        hero_image_source_url=raw.get("hero_image_source_url"),
        hero_image_source=raw.get("hero_image_source"),
        price_validation=list(raw.get("price_validation") or []),
        price_range_typical=dict(raw.get("price_range_typical") or {}),
        justification=raw.get("justification"),
        canon_classification_basis=raw.get("canon_classification_basis"),
        canon_classification_reasoning=raw.get("canon_classification_reasoning"),
        url_status_note=raw.get("url_status_note"),
        verification_source_batch=raw.get("verification_source_batch"),
        # R4 Fix I2 — round-trip URL verification metadata onto the dataclass
        # so the loader can propagate it forward (lint + render need these).
        recommended_url=raw.get("recommended_url"),
        url_status_tag=raw.get("url_status_tag"),
        price_validation_status=raw.get("price_validation_status"),
    )


def load_supplier_directory(path) -> Dict[str, Any]:
    """Load supplier_directory.yaml and validate every supplier. Returns the
    parsed dict (meta + categories + suppliers-as-Supplier-instances under the
    'suppliers' key, with the original dict shape preserved for renderer
    convenience). Fails loud if the file is missing, malformed, or empty.

    R3 Fix C4 — additionally validates:
      (a) null required-display fields (`url`, `style_fingerprint`,
          `fit_for_project`, `name`, `id`) — `parse_supplier()` would
          stringify a literal `None` otherwise.
      (b) `category` membership against the directory's `categories:` list
          so unknown categories fail loud at load instead of silently
          falling into the renderer's "Uncategorized" bucket on the real
          build path.
    """
    import os
    import yaml as _yaml
    if not os.path.exists(path):
        raise ValidationError(f"supplier_directory.yaml not found at {path}")
    with open(path) as f:
        data = _yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValidationError(f"supplier_directory.yaml is not a mapping at {path}")
    if not data.get("suppliers"):
        raise ValidationError(f"supplier_directory.yaml has no suppliers at {path}")
    # R3 Fix C4 — build the allowed-categories set from the file's own
    # categories: list. Falls through to no-op when the file omits the list.
    # R4 Fix V1 — parse_supplier() now enforces VALID_SUPPLIER_CATEGORIES;
    # the per-file declared_categories check stays as an EXTRA guard (a
    # category present in our canonical vocabulary but missing from THIS
    # file's `categories:` block still fails loud).
    declared_categories = set()
    for c in (data.get("categories") or []):
        if isinstance(c, dict) and c.get("id"):
            declared_categories.add(c["id"])
    # Validate every supplier; collect typed instances back onto the dict so
    # downstream consumers can keep using mapping-style access while the
    # validation pass has already failed loud on bad data.
    validated = []
    for raw in data["suppliers"]:
        # parse_supplier raises ValidationError on bad data — keep loud failure.
        # R4 Fix V1 — null url / unknown category / null required-display
        # fields now raise INSIDE parse_supplier(), not here.
        sup = parse_supplier(raw)
        # File-scope category membership (in case file declares a subset).
        if declared_categories and sup.category not in declared_categories:
            raise ValidationError(
                f"{sup.id}: supplier category '{sup.category}' not in directory categories: "
                f"{sorted(declared_categories)}"
            )
        # Round-trip back to dict for renderer compatibility.
        validated.append({
            "id": sup.id,
            "category": sup.category,
            "name": sup.name,
            "url": sup.url,
            "price_tier": sup.price_tier,
            "fit": sup.fit,
            "style_fingerprint": sup.style_fingerprint,
            "fit_for_project": sup.fit_for_project,
            "off_canon_warning": sup.off_canon_warning,
            "collections_to_browse": sup.collections_to_browse,
            "lead_time_typical": sup.lead_time_typical,
            "sample_policy": sup.sample_policy,
            "notes": sup.notes,
            # operator_notes intentionally NOT propagated — renderer is the only
            # consumer and UX4 forbids surfacing it. Lint may read raw separately.
            "url_verified": sup.url_verified,
            "url_status": sup.url_status,
            "hero_image": sup.hero_image,
            "hero_image_source_url": sup.hero_image_source_url,
            "hero_image_source": sup.hero_image_source,
            "price_validation": sup.price_validation,
            "price_range_typical": sup.price_range_typical,
            "justification": sup.justification,
            "canon_classification_basis": sup.canon_classification_basis,
            "canon_classification_reasoning": sup.canon_classification_reasoning,
            "url_status_note": sup.url_status_note,
            "verification_source_batch": sup.verification_source_batch,
            # R4 Fix I2 — propagate URL verification metadata so lint and
            # downstream tools can read recommended_url / url_status_tag /
            # price_validation_status from the validated loader output.
            # Previously the loader dropped these three fields even though
            # the YAML carried them, breaking the lint canonical-URL check
            # that R4-I3 now enforces.
            "recommended_url": sup.recommended_url,
            "url_status_tag": sup.url_status_tag,
            "price_validation_status": sup.price_validation_status,
        })
    data["suppliers"] = validated
    return data


def parse_meta(raw: Dict[str, Any]) -> Meta:
    b = raw["budgets"]
    c = raw["consistency_locks"]
    return Meta(
        last_updated=str(raw["last_updated"]),
        budgets=Budgets(
            construction_cap=int(b["construction_cap"]),
            furniture_envelope=int(b["furniture_envelope"]),
            path3_owner_direct_ceiling=int(b["path3_owner_direct_ceiling"]),
        ),
        consistency_locks=ConsistencyLocks(
            brass_finish_family=c["brass_finish_family"],
            wood_tone=c["wood_tone"],
            tile_palette=list(c["tile_palette"]),
            paint_line=c["paint_line"],
        ),
    )
