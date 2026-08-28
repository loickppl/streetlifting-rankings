#!/usr/bin/env python3
"""
Scraper for final-rep.com/records/ (FinalRep World Records).

The page is WordPress/Elementor: a linear sequence of
  <h2>{Gender} {class} category</h2>
  <h2>Total|Muscle up|Pull up|Dip|Squat</h2>
  ... athlete name ... "123,45 kg" ... instagram link ...
so we tokenize headings / text / instagram hrefs in document order and walk
through them with a small state machine.

Output: data/raw/finalrep_records.json
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

URL = "https://final-rep.com/records/"
HEADERS = {"User-Agent": "streetlifting-rankings-aggregator (github.com/loickppl)"}

MOVEMENTS = {"total": "total", "muscle up": "muscle_up", "pull up": "pull_up",
             "dip": "dip", "squat": "squat"}
CATEGORY_RE = re.compile(r"^(Women|Men)\s+([+\-]?\d+kg)\s+category$", re.I)
WEIGHT_RE = re.compile(r"^(\d+(?:[.,]\d+)?)\s*kg$", re.I)


def tokenize(html):
    """Yield ('h2', text) | ('ig', handle_url) | ('text', text) in document order."""
    html = re.sub(r"<script.*?</script>", "", html, flags=re.S)
    pattern = re.compile(
        r'<h2[^>]*>(?P<h2>.*?)</h2>'
        r'|<a[^>]*href="(?P<ig>https://www\.instagram\.com/[^"]+)"[^>]*>'
        r'|>(?P<text>[^<>]+)(?=<)',
        re.S,
    )
    for m in pattern.finditer(html):
        if m.group("h2") is not None:
            text = re.sub(r"<[^>]+>", "", m.group("h2")).strip()
            if text:
                yield ("h2", text)
        elif m.group("ig") is not None:
            yield ("ig", m.group("ig"))
        else:
            text = m.group("text").strip()
            if text:
                yield ("text", text)


def parse_records(html):
    records = []
    category = gender = movement = None
    pending_names = []  # text tokens seen since last weight, candidates for athlete name
    current = None      # record waiting for its instagram handle

    for kind, value in tokenize(html):
        if kind == "h2":
            m = CATEGORY_RE.match(value)
            if m:
                gender = "female" if m.group(1).lower() == "women" else "male"
                category = m.group(2) if m.group(2).startswith(("+", "-")) else "-" + m.group(2)
                movement = None
            elif value.lower() in MOVEMENTS:
                movement = MOVEMENTS[value.lower()]
            else:
                # Any other h2 ends the world-records flow context
                if not CATEGORY_RE.match(value):
                    movement = None
            pending_names = []
            current = None
        elif kind == "text":
            w = WEIGHT_RE.match(value.replace(" ", " ").strip())
            if w and movement and category and pending_names:
                current = {
                    "gender": gender,
                    "class": category,
                    "movement": movement,
                    "athlete": pending_names[-1],
                    "weight_kg": float(w.group(1).replace(",", ".")),
                    "instagram": None,
                }
                records.append(current)
                pending_names = []
            elif not w and movement and category:
                # skip icon/arrow artifacts
                if len(value) > 2 and not value.startswith(("@", "#")):
                    pending_names.append(value)
        elif kind == "ig" and current and current["instagram"] is None:
            handle = value.split("instagram.com/")[1].split("?")[0].strip("/")
            current["instagram"] = "@" + handle
            current = None

    return records


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(Path(__file__).resolve().parents[1] / "data" / "raw" / "finalrep_records.json"))
    parser.add_argument("--html", help="parse a local HTML file instead of fetching (debug)")
    args = parser.parse_args()

    if args.html:
        html = Path(args.html).read_text(encoding="utf-8", errors="replace")
    else:
        r = requests.get(URL, headers=HEADERS, timeout=30)
        r.raise_for_status()
        html = r.text

    records = parse_records(html)
    if not records:
        print("WARNING: no records parsed — page structure may have changed", file=sys.stderr)

    out = {
        "source": "final-rep.com/records",
        "scraped_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "records": records,
    }
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Wrote {out_path} ({len(records)} records)")


if __name__ == "__main__":
    main()
