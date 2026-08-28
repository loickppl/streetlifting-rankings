#!/usr/bin/env python3
"""
Scraper for rankings.officialstreetlifting.com

Two modes:

  --mode full   Crawl every athlete profile (~3300 athletes, ~1h polite crawl).
                Use for the initial baseline and an occasional resync.

  --mode delta  (default) Incremental daily update:
                  1. list competitions (upcoming + past index, ~10 pages)
                  2. scrape only competitions not yet in the local state,
                     plus recent ones (results can arrive/change late)
                  3. merge results into the athlete database; newly discovered
                     athletes get their full profile fetched
                Typical daily cost: a dozen requests instead of ~3500.

State:  data/raw/osl_competitions.json   (slug -> name, dates, last_scraped)
Output: data/raw/osl_athletes.json

Stdlib + requests only — the site is server-rendered Rails with plain,
regular <table> markup.
"""

import argparse
import json
import re
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

BASE = "https://rankings.officialstreetlifting.com"
HEADERS = {"User-Agent": "streetlifting-rankings-aggregator (github.com/loickppl/streetlifting-rankings)"}
DELAY = 0.6          # polite delay between requests, seconds
RESYNC_DAYS = 45     # re-scrape competitions whose latest result is this recent

ROOT = Path(__file__).resolve().parents[1]
ATHLETES_PATH = ROOT / "data" / "raw" / "osl_athletes.json"
STATE_PATH = ROOT / "data" / "raw" / "osl_competitions.json"

ROW_RE = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S)
CELL_RE = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.S)
TAG_RE = re.compile(r"<[^>]+>")
ATHLETE_LINK_RE = re.compile(r'href="(/athletes/[^"?#]+)"')
COMP_LINK_RE = re.compile(r'href="/competitions/([^"?#]+)"')
FLAG_RE = re.compile(r"[\U0001F1E6-\U0001F1FF]{2}")


# ── HTTP / parsing helpers ──────────────────────────────────────────────

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
    return v if v > 0 else None  # 0.00 means "unknown" (bodyweight, RIS, total)


def parse_lift(s):
    """Movement columns: in All4 every lift is contested, so 0.00 is a real
    scored zero (bodyweight-only or bombed lift), not a missing value."""
    s = s.replace(",", ".").strip()
    try:
        v = float(s)
    except ValueError:
        return None
    return v if v >= 0 else None


def parse_date(s):
    s = re.sub(r"\s+", " ", s).strip()
    for fmt in ("%b %d, %Y", "%B %d, %Y"):
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            pass
    return s or None


def header_index(header, *names):
    """Index of the first header cell containing one of `names` (checked in order)."""
    for n in names:
        for i, h in enumerate(header):
            if n in h:
                return i
    return None


def parse_result_row(cells, cols):
    """One <tr> of a results table -> performance dict (without competition)."""
    def cell(key):
        i = cols.get(key)
        return clean(cells[i]) if i is not None and i < len(cells) else ""

    return {
        "class": cell("class") or None,
        "bodyweight": parse_float(cell("bw")),
        "style": cell("style") or None,
        "muscle_up": parse_lift(cell("muscle_up")),
        "pull_up": parse_lift(cell("pull_up")),
        "dip": parse_lift(cell("dip")),
        "squat": parse_lift(cell("squat")),
        "total": parse_float(cell("total")),
        "ris_site": parse_float(cell("ris")),
        "date": parse_date(cell("date")),
    }


def result_columns(header):
    """Column map for both athlete pages and competition pages.
    More specific names first ('competition style' must not bind 'competition')."""
    return {
        "class": header_index(header, "weight class", "class"),
        "bw": header_index(header, "body weight"),
        "style": header_index(header, "competition style", "style"),
        "muscle_up": header_index(header, "muscle up"),
        "pull_up": header_index(header, "pull"),
        "dip": header_index(header, "dip"),
        "squat": header_index(header, "squat"),
        "total": header_index(header, "total"),
        "ris": header_index(header, "ris"),
        "date": header_index(header, "date"),
    }


def slug_from_url(url):
    return url.rstrip("/").rsplit("/", 1)[-1]


ATHLETE_ANCHOR_RE = re.compile(r'<a[^>]*href="/athletes/[^"]*"[^>]*>(.*?)</a>', re.S)
ISO3_RE = re.compile(r"\b[A-Z]{3}\b")


def extract_name(row_html, first_cell_html):
    """Athlete display name: prefer the /athletes/ anchor text, else clean the cell
    (dropping flag emoji, leading rank digits and stray ISO alpha-3 codes)."""
    m = ATHLETE_ANCHOR_RE.search(row_html)
    if m:
        name = clean(m.group(1))
        if name:
            return name
    raw = clean(first_cell_html)
    raw = FLAG_RE.sub("", re.sub(r"^\d+\s", "", raw))
    raw = ISO3_RE.sub("", raw)
    return re.sub(r"\s+", " ", raw).strip() or None


def has_lift(perf):
    return any(perf.get(k) for k in ("total", "muscle_up", "pull_up", "dip", "squat"))


# ── athlete profile pages (full mode + new athletes in delta) ───────────

def parse_athlete_page(html, slug):
    """Extract athlete identity + full competition history from a profile page."""
    rows = ROW_RE.findall(html)
    if not rows:
        return None

    header = [clean(c).lower() for c in CELL_RE.findall(rows[0])]
    cols = result_columns(header)
    # athlete pages do have a real Competition column
    comp_i = header_index(header, "competition")
    style_i = cols["style"]
    if comp_i == style_i:  # only "competition style" matched
        comp_i = None

    athlete = {"id": slug, "name": None, "country": None, "gender": None,
               "profile_url": f"{BASE}/athletes/{slug}", "performances": []}

    for row in rows[1:]:
        cells = CELL_RE.findall(row)
        if len(cells) < 10:
            continue
        lifter_raw = clean(cells[0])
        flag = FLAG_RE.search(lifter_raw)
        name = extract_name(row, cells[0])
        if athlete["name"] is None and name:
            athlete["name"] = name
        if athlete["country"] is None and flag:
            athlete["country"] = flag_to_iso(flag.group())
        gender_i = header_index(header, "gender")
        if athlete["gender"] is None and gender_i is not None:
            athlete["gender"] = clean(cells[gender_i]).lower() or None

        perf = parse_result_row(cells, cols)
        perf["competition"] = clean(cells[comp_i]) if comp_i is not None and comp_i < len(cells) else None
        # 4-movement 1RM competitions only (drop 1/2/3-lift formats)
        if perf.get("style") == "All4" and has_lift(perf):
            athlete["performances"].append(perf)

    if athlete["name"] is None:
        m = re.search(r"<title>([^<]+)</title>", html)
        if m:
            athlete["name"] = m.group(1).split("|")[0].strip()
    return athlete


def collect_athlete_urls(session):
    """Paginate /athletes until no new profiles show up."""
    urls, page = set(), 1
    while True:
        html = fetch(session, f"{BASE}/athletes?page={page}")
        if html is None:
            break
        found = set(ATHLETE_LINK_RE.findall(html))
        new = found - urls
        if not new:
            break
        urls |= new
        if page % 20 == 0:
            print(f"  /athletes page {page}: {len(urls)} athletes so far")
        page += 1
        time.sleep(DELAY)
    return sorted(urls)


# ── competition pages (delta mode) ──────────────────────────────────────

def collect_competition_slugs(session):
    """All competition slugs from the upcoming index + the paginated past index."""
    slugs = set()
    html = fetch(session, f"{BASE}/competitions")
    if html:
        slugs |= set(COMP_LINK_RE.findall(html))
    page = 1
    while True:
        html = fetch(session, f"{BASE}/competitions/past?page={page}")
        if html is None:
            break
        found = set(COMP_LINK_RE.findall(html))
        new = found - slugs
        if not new:
            break
        slugs |= new
        page += 1
        time.sleep(DELAY)
    slugs.discard("past")
    return sorted(slugs)


def parse_competition_page(html):
    """-> (competition_name, [result rows with athlete identity])."""
    name = None
    for m in re.finditer(r"<h2[^>]*>(.*?)</h2>", html, re.S):
        txt = clean(m.group(1))
        if txt and txt.lower() not in ("footer", "general"):
            name = txt
            break
    if not name:
        m = re.search(r"<title>([^<]+)</title>", html)
        name = m.group(1).split("|")[0].strip() if m else None

    rows = ROW_RE.findall(html)
    if not rows:
        return name, []
    header = [clean(c).lower() for c in CELL_RE.findall(rows[0])]
    cols = result_columns(header)
    gender_i = header_index(header, "gender")

    results = []
    for row in rows[1:]:
        cells = CELL_RE.findall(row)
        if len(cells) < 10:
            continue
        m = re.search(r'href="/athletes/([^"?#]+)"', row)
        flag = FLAG_RE.search(clean(cells[0]))
        perf = parse_result_row(cells, cols)
        if perf.get("style") != "All4" or not has_lift(perf):
            continue
        results.append({
            "athlete_slug": m.group(1) if m else None,
            "athlete_name": extract_name(row, cells[0]),
            "country": flag_to_iso(flag.group()) if flag else None,
            "gender": (clean(cells[gender_i]).lower() or None) if gender_i is not None else None,
            "perf": perf,
        })
    return name, results


# ── persistence ─────────────────────────────────────────────────────────

def load_json(path, default):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return default


def save_athletes(athletes_by_id):
    out = {
        "source": "rankings.officialstreetlifting.com",
        "scraped_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "athletes": sorted(athletes_by_id.values(), key=lambda a: a["id"]),
    }
    ATHLETES_PATH.parent.mkdir(parents=True, exist_ok=True)
    ATHLETES_PATH.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    n = sum(len(a["performances"]) for a in athletes_by_id.values())
    print(f"Wrote {ATHLETES_PATH} ({len(athletes_by_id)} athletes, {n} performances)")


def save_state(state):
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")


# ── modes ───────────────────────────────────────────────────────────────

def run_full(session, limit=0):
    print("FULL crawl: collecting athlete URLs...")
    urls = collect_athlete_urls(session)
    print(f"Found {len(urls)} athletes")
    if limit:
        urls = urls[:limit]

    athletes = {}
    for i, url in enumerate(urls, 1):
        slug = slug_from_url(url)
        html = fetch(session, BASE + url)
        if html is None:
            print(f"  [{i}/{len(urls)}] FAILED {slug}", file=sys.stderr)
            continue
        a = parse_athlete_page(html, slug)
        if a:
            athletes[slug] = a
        if i % 100 == 0 or i == len(urls):
            print(f"  [{i}/{len(urls)}] scraped")
        time.sleep(DELAY)
    save_athletes(athletes)


def run_delta(session):
    data = load_json(ATHLETES_PATH, None)
    if data is None:
        print("No baseline database — falling back to FULL crawl.")
        return run_full(session)
    athletes = {a["id"]: a for a in data["athletes"]}
    state = load_json(STATE_PATH, {})

    print("DELTA: listing competitions...")
    slugs = collect_competition_slugs(session)
    print(f"  {len(slugs)} competitions on site, {len(state)} known")

    cutoff = (date.today() - timedelta(days=RESYNC_DAYS)).isoformat()
    to_scrape = []
    for slug in slugs:
        st = state.get(slug)
        if st is None:
            to_scrape.append(slug)                       # new competition
        elif (st.get("latest_date") or "") >= cutoff:
            to_scrape.append(slug)                       # recent → may still change
    print(f"  {len(to_scrape)} competitions to scrape")

    new_athletes, merged = set(), 0
    for i, slug in enumerate(to_scrape, 1):
        html = fetch(session, f"{BASE}/competitions/{slug}")
        time.sleep(DELAY)
        if html is None:
            continue
        name, results = parse_competition_page(html)
        if not name:
            continue

        # replace this competition's results for every athlete it mentions
        touched = {r["athlete_slug"] for r in results if r["athlete_slug"]}
        for aslug in touched:
            if aslug in athletes:
                athletes[aslug]["performances"] = [
                    p for p in athletes[aslug]["performances"]
                    if p.get("competition") != name
                ]
        for r in results:
            aslug = r["athlete_slug"]
            if not aslug:
                continue
            if aslug not in athletes:
                athletes[aslug] = {
                    "id": aslug, "name": r["athlete_name"], "country": r["country"],
                    "gender": r["gender"], "profile_url": f"{BASE}/athletes/{aslug}",
                    "performances": [],
                }
                new_athletes.add(aslug)
            perf = dict(r["perf"])
            perf["competition"] = name
            athletes[aslug]["performances"].append(perf)
            merged += 1

        dates = [r["perf"]["date"] for r in results
                 if r["perf"]["date"] and re.match(r"^\d{4}-", r["perf"]["date"] or "")]
        state[slug] = {
            "name": name,
            "latest_date": max(dates) if dates else None,
            "n_results": len(results),
            "last_scraped": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        print(f"  [{i}/{len(to_scrape)}] {name}: {len(results)} results")

    # enrich newly discovered athletes with their full profile (country, history)
    for i, aslug in enumerate(sorted(new_athletes), 1):
        html = fetch(session, f"{BASE}/athletes/{aslug}")
        time.sleep(DELAY)
        if html is None:
            continue
        a = parse_athlete_page(html, aslug)
        if a and a["performances"]:
            athletes[aslug] = a
        print(f"  new athlete [{i}/{len(new_athletes)}]: {athletes[aslug].get('name')}")

    save_athletes(athletes)
    save_state(state)
    print(f"Delta done: {len(to_scrape)} competitions, {merged} results merged, "
          f"{len(new_athletes)} new athletes")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["delta", "full"], default="delta")
    parser.add_argument("--limit", type=int, default=0, help="full mode: scrape only N athletes (debug)")
    args = parser.parse_args()

    session = requests.Session()
    if args.mode == "full":
        run_full(session, args.limit)
    else:
        run_delta(session)


if __name__ == "__main__":
    main()
