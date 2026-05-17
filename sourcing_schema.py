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
