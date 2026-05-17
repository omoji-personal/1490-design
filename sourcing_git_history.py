"""Build a {item_id: 'YYYY-MM-DD'} map of the last commit date for each item's
yaml block in scope/sourcing.yaml.

Strategy: a single `git log -p` pull is parsed locally so we never spawn 139 git
processes (one per item). The walk goes commit-by-commit, newest-first, and for
each commit records every item id whose yaml block was added/modified by that
commit. The first time an id appears wins (= most recent change).

Falls back to {} (no dates rendered) if:
- the yaml file is not in a git repo (e.g. fresh clone, CI cache strip)
- git is not on PATH
- the parse hits an unexpected format

Tested against ~/Desktop/HomeAI/scope/sourcing.yaml (~10K lines, 139 items).
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Dict

# Match `- id: SOME-ID-HERE` in a diff context line (after the +/- marker).
# Matches both added lines (`+- id: X`) and the canonical form (`- id: X`).
_ID_LINE_RE = re.compile(r"^[+\- ]?-\s+id:\s+([A-Za-z0-9_\-]+)\s*$")


def build_last_changed_map(yaml_path: Path) -> Dict[str, str]:
    """Return {item_id: 'YYYY-MM-DD'} for the last commit that touched each item.

    Implementation walks `git log --format=%cs|COMMITSEP -p -- <yaml_path>` once
    and parses diff hunks. Item id is detected by `- id: X` lines on any +/- side.
    On any error, returns {}.
    """
    if not yaml_path.exists():
        return {}
    repo_root = _find_repo_root(yaml_path)
    if repo_root is None:
        return {}
    try:
        rel = yaml_path.relative_to(repo_root)
    except ValueError:
        return {}

    try:
        proc = subprocess.run(
            [
                "git",
                "-C", str(repo_root),
                "log",
                "--format=__COMMIT__%cs",
                "--unified=0",
                "-p",
                "--",
                str(rel),
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return {}
    if proc.returncode != 0:
        return {}

    result: Dict[str, str] = {}
    current_date: str | None = None
    for raw in proc.stdout.splitlines():
        if raw.startswith("__COMMIT__"):
            current_date = raw[len("__COMMIT__"):].strip() or None
            continue
        if current_date is None:
            continue
        # Only consider added or removed lines (start with + or -, not +++ / ---)
        if not raw or raw[0] not in "+-":
            continue
        if raw.startswith(("+++", "---")):
            continue
        m = _ID_LINE_RE.match(raw)
        if m:
            item_id = m.group(1)
            # First time we see an id (walking newest -> oldest) is the last change.
            result.setdefault(item_id, current_date)
    return result


def _find_repo_root(start: Path) -> Path | None:
    """Walk up from start looking for a .git directory. Returns None if not found."""
    cur = start.resolve().parent if start.is_file() else start.resolve()
    for parent in [cur, *cur.parents]:
        if (parent / ".git").exists():
            return parent
    return None
