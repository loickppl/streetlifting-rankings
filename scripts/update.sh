#!/usr/bin/env bash
# Daily data refresh — designed to run from cron on a homelab box.
#
# Cron example (every day at 06:00):
#   0 6 * * * /path/to/streetlifting-rankings/scripts/update.sh >> /var/log/streetlifting-update.log 2>&1
#
# Requirements: git (with push access to the repo), python3, python3-requests.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

echo "=== streetlifting-rankings update $(date -Is) ==="

git pull --rebase --quiet

python3 scraper/scrape_osl.py
python3 scraper/scrape_finalrep.py
python3 scraper/aggregate.py

if git status --porcelain data/ docs/data/ | grep -q .; then
    git add data/ docs/data/
    git commit -m "data: automatic refresh $(date -u +%F)"
    git push
    echo "Pushed new data."
else
    echo "No data changes."
fi
