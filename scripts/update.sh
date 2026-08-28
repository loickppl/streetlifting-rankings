#!/usr/bin/env bash
# Daily data refresh — designed to run from cron on a homelab box.
#
# Cron example (every day at 06:00):
#   0 6 * * * /path/to/streetlifting-rankings/scripts/update.sh >> /var/log/streetlifting-update.log 2>&1
#
# Daily runs use the incremental delta scraper (~a dozen requests: new/recent
# competitions only). On the 1st of the month — or with FULL=1 — a full crawl
# resyncs the whole athlete database (~1h polite crawl) to catch corrections.
#
# Requirements: git (with push access to the repo), python3, python3-requests.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

echo "=== streetlifting-rankings update $(date -Is) ==="

git pull --rebase --quiet

if [[ "${FULL:-0}" = "1" || "$(date +%d)" = "01" ]]; then
    echo "--- full resync ---"
    python3 scraper/scrape_osl.py --mode full
else
    echo "--- delta update ---"
    python3 scraper/scrape_osl.py --mode delta
fi
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
