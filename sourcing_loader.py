"""Load sourcing.yaml + construction_schedule.yaml. Returns validated typed data."""
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional
import yaml

from sourcing_schema import Item, Meta, parse_item, parse_meta


@dataclass
class SourcingData:
    meta: Meta
    items: List[Item]


@dataclass
class Schedule:
    phases: Dict[str, Optional[str]]  # phase_name -> ISO date or None


def load_sourcing(path: Path) -> SourcingData:
    raw = yaml.safe_load(Path(path).read_text())
    meta = parse_meta(raw["meta"])
    items = [parse_item(it) for it in raw.get("items", [])]
    return SourcingData(meta=meta, items=items)


def load_schedule(path: Path) -> Schedule:
    raw = yaml.safe_load(Path(path).read_text())
    # YAML loads dates as date objects; coerce to ISO strings or None
    phases: Dict[str, Optional[str]] = {}
    for name, val in (raw.get("phases") or {}).items():
        if val is None:
            phases[name] = None
        else:
            phases[name] = str(val)
    return Schedule(phases=phases)
