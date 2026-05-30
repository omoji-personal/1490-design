#!/usr/bin/env bash
# sync_sourcing.sh — regenerate sourcing outputs and push both repos
# Usage: ./sync_sourcing.sh "commit message subject"

set -euo pipefail

SITE_DIR="$HOME/Desktop/1490-design-site"
HOMEAI_DIR="$HOME/Desktop/HomeAI"
MSG="${1:-Sourcing: regenerate tracker outputs}"

cd "$SITE_DIR"
python3 build_sourcing.py

# Switch gh to personal account for any gh commands later
gh auth switch -u omoji-tb >/dev/null 2>&1 || true

# Commit HomeAI (data + rendered markdown)
cd "$HOMEAI_DIR"
if git status --porcelain | grep -qE "scope/sourcing\.yaml|scope/SOURCING_TRACKER\.md|scope/needs-decision-now\.md|scope/annika-queue\.md|data/construction_schedule\.yaml"; then
  git add scope/sourcing.yaml scope/SOURCING_TRACKER.md scope/needs-decision-now.md scope/annika-queue.md data/construction_schedule.yaml 2>/dev/null || true
  git commit -m "$MSG" || echo "(no HomeAI changes)"
  git push origin main
else
  echo "(no HomeAI changes)"
fi

# Commit site (all sourcing-derived pages + any image additions)
# I16 — build_sourcing.py also regenerates for-annika.html, vendors.html,
# suppliers.html, and the 6 sourcing-<room>.html pages; the prior `git add`
# only staged sourcing.html, so those silently went stale on deploy.
cd "$SITE_DIR"
if git status --porcelain | grep -qE "sourcing\.html|for-annika\.html|vendors\.html|suppliers\.html|sourcing-.*\.html|images/sourcing/"; then
  git add sourcing.html for-annika.html vendors.html suppliers.html sourcing-*.html images/sourcing/ 2>/dev/null || true
  git commit -m "$MSG" || echo "(no site changes)"
  git push origin main
else
  echo "(no site changes)"
fi

echo ""
echo "Sourcing sync complete."
