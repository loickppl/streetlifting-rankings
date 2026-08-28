#!/usr/bin/env python3
"""
Scraper for rankings.officialstreetlifting.com

Strategy:
  1. Paginate /athletes to collect every athlete profile URL.
  2. Scrape each athlete page: full competition history
     (class, bodyweight, style, muscle-up, pull-up, dip, squat, total, RIS,
      competition, date, country).

Output: data/raw/osl_athletes.json
Stdlib + requests only (no bs4) — the site is server-rendered Rails with
plain, regular <table> markup.
"""

import argparse
import json
import re
import sys
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import requests

BASE = "https://rankings.officialstreetlifting.com"
HEADERS = {"User-Agent": "streetlifting-rankings-aggregator (github.com/loickppl)"}
DELAY = 0.6  # polite delay between requests, seconds

ROW_RE = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S)
CELL_RE = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.S)
TAG_RE = re.compile(r"<[^>]+>")
ATHLETE_LINK_RE = re.compile(r'href="(/athletes/[^"?#]+)"')
FLAG_RE = re.compile(r"[\U0001F1E6-\U0001F1FF]{2}")


def fetch(session, url, retries=3):
    for attempt in range(retries):
        try:
            r = session.get(url, headers=HEADERS, timeout=30)
            if r.status_code == 200:
                return r.text
            if r.status_code == 404:
                return None
            print(f"  HTTP {r.status_code} on {url}, retry {attempt + 1}", file=sys.stderr)
        except requests.RequestException as e:
            print(f"  error on {url}: {e}, retry {attempt + 1}", file=sys.stderr)
        time.sleep(2 * (attempt + 1))
    return None


def clean(cell_html):
    """Strip tags/entities and collapse whitespace in a table cell."""
    text = TAG_RE.sub(" ", cell_html)
    text = (
        text.replace("&amp;", "&").replace("&nbsp;", " ")
        .replace("&#39;", "'").replace("&quot;", '"')
    )
    return re.sub(r"\s+", " ", text).strip()


def flag_to_iso(flag):
    """🇮🇹 -> IT (regional indicator symbols to ISO 3166-1 alpha-2)."""
    if not flag:
        return None
    return "".join(chr(ord(c) - 0x1F1E6 + ord("A")) for c in flag)


def parse_float(s):
    s = s.replace(",", ".").strip()
    try:
        v = float(s)
    except ValueError:
        return None
    return v if v > 0 else None  # site uses 0.00 for "unknown"


def parse_date(s):
    s = re.sub(r"\s+", " ", s).strip()
    for fmt in ("%b %d, %Y", "%B %d, %Y"):
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            pass
    return s or None


def slug_from_url(url):
    return url.rstrip("/").rsplit("/", 1)[-1]


def collect_athlete_urls(session):
    """Paginate /athletes until no new profiles show up."""
    urls, page = set(), 1
    while True:
        html = fetch(session, f"{BASE}/athletes?page={page}")
        if html is None:
            break
        found = set(ATHLETE_LINK_RE.findall(html))
        new = found - urls
        print(f"  /athletes page {page}: {len(new)} new athletes")
        if not new:
            break
        urls |= new
        page += 1
        time.sleep(DELAY)
    return sorted(urls)


def parse_athlete_page(html, slug):
    """Extract athlete identity + full competition history from a profile page."""
    rows = ROW_RE.findall(html)
    if not rows:
        return None

    header = [clean(c).lower() for c in CELL_RE.findall(rows[0])]

    def idx(*names):
        for n in names:
            for i, h in enumerate(header):
                if n in h:
                    return i
        return None

    cols = {
        "lifter": idx("lifter"),
        "gender": idx("gender"),
        "class": idx("class"),
        "bw": idx("body weight"),
        "style": idx("style"),
        "muscle_up": idx("muscle up"),
        "pull_up": idx("pull"),
        "dip": idx("dip"),
        "squat": idx("squat"),
        "total": idx("total"),
        "ris": idx("ris"),
        "competition": idx("competition"),
        "date": idx("date"),
    }

    athlete = {"id": slug, "name": None, "country": None, "gender": None,
               "profile_url": f"{BASE}/athletes/{slug}", "performances": []}

    for row in rows[1:]:
        cells = CELL_RE.findall(row)
        if len(cells) < 10:
            continue

        def cell(key):
            i = cols.get(key)
            return clean(cells[i]) if i is not None and i < len(cells) else ""

        lifter_raw = cell("lifter")
        flag = FLAG_RE.search(lifter_raw)
        name = FLAG_RE.sub("", re.sub(r"^\d+\s", "", lifter_raw)).strip()
        if athlete["name"] is None and name:
            athlete["name"] = name
        if athlete["country"] is None and flag:
            athlete["country"] = flag_to_iso(flag.group())
        if athlete["gender"] is None and cell("gender"):
            athlete["gender"] = cell("gender").lower()

        perf = {
            "class": cell("class") or None,
            "bodyweight": parse_float(cell("bw")),
            "style": cell("style") or None,
            "muscle_up": parse_float(cell("muscle_up")),
            "pull_up": parse_float(cell("pull_up")),
            "dip": parse_float(cell("dip")),
            "squat": parse_float(cell("squat")),
            "total": parse_float(cell("total")),
            "ris_site": parse_float(cell("ris")),
            "competition": cell("competition") or None,
            "date": parse_date(cell("date")),
        }
        if perf["total"] or perf["muscle_up"] or perf["pull_up"] or perf["dip"] or perf["squat"]:
            athlete["performances"].append(perf)

    if athlete["name"] is None:
        # Fallback: page <title>
        m = re.search(r"<title>([^<]+)</title>", html)
        if m:
            athlete["name"] = m.group(1).split("|")[0].strip()
    return athlete if athlete["performances"] else athlete


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(Path(__file__).resolve().parents[1] / "data" / "raw" / "osl_athletes.json"))
    parser.add_argument("--limit", type=int, default=0, help="scrape only N athletes (debug)")
    args = parser.parse_args()

    session = requests.Session()

    print("Collecting athlete URLs...")
    urls = collect_athlete_urls(session)
    print(f"Found {len(urls)} athletes")
    if args.limit:
        urls = urls[: args.limit]

    athletes = []
    for i, url in enumerate(urls, 1):
        slug = slug_from_url(url)
        html = fetch(session, BASE + url)
        if html is None:
            print(f"  [{i}/{len(urls)}] FAILED {slug}", file=sys.stderr)
            continue
        athlete = parse_athlete_page(html, slug)
        if athlete:
            athletes.append(athlete)
        if i % 20 == 0 or i == len(urls):
            print(f"  [{i}/{len(urls)}] scraped ({sum(len(a['performances']) for a in athletes)} performances)")
        time.sleep(DELAY)

    out = {
        "source": "rankings.officialstreetlifting.com",
        "scraped_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "athletes": athletes,
    }
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Wrote {out_path} ({len(athletes)} athletes)")


if __name__ == "__main__":
    main()
