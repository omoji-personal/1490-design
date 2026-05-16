# sourcing_queue.py
"""Queue logic: when does an item enter the 'decide this week' queue?"""
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Tuple

from sourcing_loader import Schedule
from sourcing_schema import Item, Option


def _parse_iso(d: str) -> date:
    return datetime.strptime(d, "%Y-%m-%d").date()


@dataclass
class ScheduleLookup:
    schedule: Schedule
    meta_last_updated: str
    today: date

    def days_until(self, phase_name: str) -> Tuple[int, bool]:
        """Returns (days_until_phase, schedule_locked). When date is null,
        falls back to meta.last_updated + 12 weeks with locked=False."""
        if phase_name not in self.schedule.phases:
            raise KeyError(f"unknown phase: {phase_name}")
        val = self.schedule.phases[phase_name]
        if val is None:
            fallback = _parse_iso(self.meta_last_updated) + timedelta(weeks=12)
            return (fallback - self.today).days, False
        return (_parse_iso(val) - self.today).days, True


T0_PHASES = [
    "roof_phase_start", "bath_gut_start", "kitchen_gut_start",
    "electrical_rough_start", "plumbing_rough_start",
]


def is_in_decision_queue(item: Item, lookup: ScheduleLookup, manual_trigger_t3: bool) -> bool:
    if item.decision_status != "options_drafted":
        return False
    if item.urgency == "T0":
        # earliest of the construction-rough phases
        days_list = [lookup.days_until(p)[0] for p in T0_PHASES]
        return min(days_list) <= 14
    if item.urgency == "T1":
        days, _ = lookup.days_until("finish_phase_start")
        return days <= 7
    if item.urgency == "T2":
        days, _ = lookup.days_until("move_back_in")
        return days <= 21
    if item.urgency == "T3":
        return manual_trigger_t3
    return False
