#!/bin/bash
# Sync DESIGN_SPEC.md from HomeAI → regenerate spec.html → commit + push.
# Auto-deploy on Vercel picks up the push.
set -euo pipefail
cd "$(dirname "$0")"

# Regenerate spec.html from the canonical DESIGN_SPEC.md in HomeAI
python3 build_spec.py

# Stage + commit (only if there are changes)
git add spec.html
if git diff --cached --quiet; then
  echo "No spec changes detected. Nothing to deploy."
  exit 0
fi

git -c user.email=omid.mojtahedi@gmail.com \
    -c user.name="Omid Mojtahedi" \
    commit -m "Sync spec.html from DESIGN_SPEC.md"

# Push — auto-deploy on Vercel picks this up
git push

echo "✓ Synced. Vercel will auto-deploy within ~30 seconds."
echo "  → https://1490-design-site.vercel.app/spec"
