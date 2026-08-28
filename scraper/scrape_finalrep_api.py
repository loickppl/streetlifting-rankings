#!/usr/bin/env python3
"""
Authenticated scraper for the Final Rep app API (api.final-rep.com).

Final Rep's app (app.final-rep.com) is a Flutter SPA backed by a REST API.
Logged in, it exposes every competition and every athlete's detailed
attempts — far richer than the public records page. This scraper reuses a
browser session cookie (the `access` JWT) since the login itself is OAuth
(Google/Apple) and cannot be automated.

────────────────────────────────────────────────────────────────────────
AUTH — how to provide the session (access token lives ~20 min):
  1. Log into https://app.final-rep.com in your browser.
  2. DevTools (F12) → Application → Cookies → https://app.final-rep.com
     copy BOTH cookie values: `access` and `refresh`.
  3. Save them to  data/raw/.finalrep_cookie , one per line:
        access=<the-access-jwt>
        refresh=<the-refresh-token>
     (this file is .gitignored — it never leaves your machine).
The `access` token is short-lived; the scraper renews it via
POST /auth-api/v1/refresh using the long-lived `refresh` cookie and rewrites
the cookie file. With `refresh` present the crawl runs unattended (and from
cron); without it, only ~20 min of work fits before a re-capture is needed.
────────────────────────────────────────────────────────────────────────

Endpoints (all on https://api.final-rep.com, cookie auth):
  /feed-api/v1/feed                              list events (filterable)
  /events-api/v1/events/{id}                     event meta
  /events-api/v1/events/{id}/groups              weight classes + starters
  /events-api/v1/events/{id}/attempts/{uid}/history   per-athlete attempts
  /users-api/v1/users/{id}                        athlete profile
  /notifications-api/v1/token  (POST)             refresh access token

Output: data/raw/finalrep_api.json
"""

import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

API = "https://api.final-rep.com"
ORIGIN = "https://app.final-rep.com"
ROOT = Path(__file__).resolve().parents[1]
COOKIE_PATH = ROOT / "data" / "raw" / ".finalrep_cookie"
OUT_PATH = ROOT / "data" / "raw" / "finalrep_api.json"
DELAY = 0.5

HEADERS = {
    "Origin": ORIGIN,
    "Referer": ORIGIN + "/",
    "accept": "application/json",
    "content-type": "application/json",
    "User-Agent": "streetlifting-rankings-aggregator (github.com/loickppl/streetlifting-rankings)",
}

# Streetlifting movements as they appear in Final Rep attempt/exercise names.
MOVEMENT_ALIASES = {
    "muscle up": "muscle_up", "muscle-up": "muscle_up",
    "pull up": "pull_up", "pull/chin up": "pull_up", "pull-up": "pull_up", "chin up": "pull_up",
    "dip": "dip", "dips": "dip",
    "squat": "squat",
}


def norm_movement(name):
    if not name:
        return None
    n = name.strip().lower()
    return MOVEMENT_ALIASES.get(n, MOVEMENT_ALIASES.get(n.rstrip("s"), None))


class FinalRepClient:
    def __init__(self, cookie_path=COOKIE_PATH):
        self.session = requests.Session()
        self.cookie_path = Path(cookie_path)
        self.access = None
        self.refresh_token = None   # long-lived httpOnly `refresh` cookie
        self._load_cookie()

    def _load_cookie(self):
        if not self.cookie_path.exists():
            sys.exit(f"Missing {self.cookie_path}. See the AUTH block in this file's docstring.")
        raw = self.cookie_path.read_text(encoding="utf-8").strip()
        m = re.search(r"access=([^\s;]+)", raw)
        if not m:
            sys.exit(f"{self.cookie_path} must contain 'access=<jwt>'.")
        self.access = m.group(1)
        r = re.search(r"refresh=([^\s;]+)", raw)
        self.refresh_token = r.group(1) if r else None

    def _save_cookie(self):
        lines = [f"access={self.access}"]
        if self.refresh_token:
            lines.append(f"refresh={self.refresh_token}")
        self.cookie_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _cookie_header(self):
        cookies = f"access={self.access}"
        if self.refresh_token:
            cookies += f"; refresh={self.refresh_token}"
        return {"Cookie": cookies}

    @staticmethod
    def _jwt_exp(token):
        try:
            import base64
            payload = token.split(".")[1]
            payload += "=" * (-len(payload) % 4)
            return json.loads(base64.urlsafe_b64decode(payload)).get("exp")
        except Exception:
            return None

    def refresh(self):
        """Slide the session before the access token expires.

        The app renews via /auth-api/v1/refresh using the long-lived, httpOnly
        `refresh` cookie; the server replies with fresh `access` (and possibly
        `refresh`) Set-Cookie headers. We try that first, then a couple of
        fallbacks. Without a `refresh` cookie in the cookie file this cannot
        work — recapture including `refresh=`.
        """
        for path in ("/auth-api/v1/refresh", "/auth-api/v1/token", "/notifications-api/v1/token"):
            try:
                r = self.session.post(API + path,
                                      headers={**HEADERS, **self._cookie_header()}, timeout=30)
            except requests.RequestException:
                continue
            new = r.cookies.get("access")
            new_refresh = r.cookies.get("refresh")
            if new:
                self.access = new
                if new_refresh:
                    self.refresh_token = new_refresh
                self._save_cookie()
                return True
        return False

    def _maybe_refresh(self):
        exp = self._jwt_exp(self.access)
        if exp and exp - time.time() < 120:  # <2 min left
            if self.refresh():
                print("  (token refreshed)")

    def get(self, path, params=None, retries=3):
        return self._request("GET", path, params=params, retries=retries)

    def post(self, path, body, retries=3):
        return self._request("POST", path, json_body=body, retries=retries)

    def _request(self, method, path, params=None, json_body=None, retries=3):
        self._maybe_refresh()
        url = path if path.startswith("http") else API + path
        for attempt in range(retries):
            try:
                r = self.session.request(method, url, params=params, json=json_body,
                                         headers={**HEADERS, **self._cookie_header()}, timeout=40)
                if r.status_code == 200:
                    return r.json()
                if r.status_code in (401, 403):
                    if self.refresh():
                        continue
                    sys.exit("Session expired and refresh failed — recapture the access cookie.")
                if r.status_code == 404:
                    return None
                print(f"  HTTP {r.status_code} {method} {url}", file=sys.stderr)
            except requests.RequestException as e:
                print(f"  error {url}: {e}", file=sys.stderr)
            time.sleep(1.5 * (attempt + 1))
        return None

    def embedded(self, resp):
        """Unwrap the HAL-style {_embedded, _meta} envelope."""
        if resp is None:
            return None
        return resp.get("_embedded", resp) if isinstance(resp, dict) else resp


# ── crawl ───────────────────────────────────────────────────────────────

def list_events(client, continents=None):
    """Enumerate events from both feeds:
      /feed-api/v1/feed     — upcoming events
      /feed-api/v1/results  — finished events with results ("Latest Results")
    Both are filterable by continent/country; we sweep continents to widen
    coverage. De-duplicated by event id.
    """
    continents = continents or ["europe", "north_america", "south_america",
                                "asia", "africa", "oceania"]
    events = {}

    def harvest(path, params, label):
        resp = client.get(path, params=params)
        emb = client.embedded(resp) or {}
        items = emb.get("items", []) if isinstance(emb, dict) else []
        new = 0
        for it in items:
            ev = (it.get("data") or {}).get("event") or {}
            eid = ev.get("id")
            if not eid or eid in events:
                continue
            events[eid] = {
                "id": eid, "name": ev.get("name"), "type": ev.get("type"),
                "state": ev.get("event_state"), "affiliated": ev.get("finalrep_affiliated"),
                "start_date": ev.get("start_date"), "end_date": ev.get("end_date"),
                "location": ev.get("location"),
                "country": (ev.get("coordinates") or {}).get("country"),
                "continent": (ev.get("coordinates") or {}).get("continent"),
                "finished": path.endswith("/results"),
            }
            new += 1
        print(f"  {label}: {len(items)} items, +{new} new ({len(events)} total)")
        time.sleep(DELAY)
        return len(items)

    # countries come from the feed's filter_options (fallback list below)
    resp = client.get("/feed-api/v1/feed")
    fo = (client.embedded(resp) or {}).get("filter_options", {}) if resp else {}
    countries = fo.get("countries", [])

    for path, tag in [("/feed-api/v1/results", "results"), ("/feed-api/v1/feed", "feed")]:
        harvest(path, {"continent": "", "country": ""}, f"{tag}[all]")
        for cont in continents:
            harvest(path, {"continent": cont, "country": ""}, f"{tag}[{cont}]")
        for country in countries:
            harvest(path, {"continent": "", "country": country}, f"{tag}[{country}]")

    # The finished-events feed only reaches ~6 months back. The global ranking
    # (POST /events/ranking) aggregates best-per-athlete across ALL history and
    # each entry names its event — so sweeping it surfaces historical event ids.
    for eid, name in ranking_event_ids(client).items():
        if eid not in events:
            events[eid] = {
                "id": eid, "name": name, "type": None, "state": None,
                "affiliated": None, "start_date": None, "end_date": None,
                "location": None, "country": None, "continent": None,
                "finished": True, "from_ranking": True,
            }
    print(f"  + ranking sweep: {len(events)} events total")
    return list(events.values())


# We keep ONLY 4-movement 1RM streetlifting (MU + PU + Dip + Squat):
#   Calisthenics ONERM   = official "Streetlifting 4 Lift"
#   FinalRep Underground = same 4-lift format, underground series
# Reduced formats (Classic 2-lift, 3L) and max-rep (LOR/AMRAP) are excluded.
STREETLIFTING_TYPES = ["Calisthenics ONERM"]          # ranking sweep
STREETLIFTING_STAT_TYPES = {"Calisthenics ONERM", "FinalRep Underground"}


def ranking_event_ids(client):
    """Sweep POST /events-api/v1/events/ranking over the 1RM event types and
    paginate to collect every referenced (historical) event id."""
    event_ids = {}
    for et in STREETLIFTING_TYPES:
        offset = 0
        while True:
            d = client.post("/events-api/v1/events/ranking", {
                "event_type": et, "sort_by_ris": False, "finalrep_affiliated": False,
                "continent": "", "country": "", "limit": 100, "offset": offset,
                "start_date": "2015-01-01T00:00:00Z", "end_date": "2035-12-31T23:59:59Z",
            })
            emb = client.embedded(d) if d else None
            if not emb:
                break
            for x in emb.get("overall", []):
                if x.get("event_id"):
                    event_ids[x["event_id"]] = x.get("event_name")
            for g in emb.get("groups", []):
                for s in g.get("stats", []):
                    if s.get("event_id"):
                        event_ids[s["event_id"]] = s.get("event_name")
            offset += 100
            if offset >= (emb.get("max_results") or 0):
                break
            time.sleep(DELAY)
    return event_ids


def event_statistics(client, eid):
    """Full results of one event in a single call:
    /events-api/v1/events/{id}/statistics returns every group (weight class)
    with athlete_stats: user profile, place, total, official RIS, and every
    attempt per movement (weight, attempt number, success)."""
    return client.embedded(client.get(f"/events-api/v1/events/{eid}/statistics"))


def parse_statistics(stats, ev):
    """Condense a statistics payload into per-athlete result rows."""
    results = []
    for gs in stats.get("group_stats", []):
        group = gs.get("group") or {}
        weight_class = group.get("name")
        for ast in gs.get("athlete_stats", []):
            user = ast.get("user") or {}
            attempts = []
            for raw_name, tries in (ast.get("attempts") or {}).items():
                movement = norm_movement(raw_name) or raw_name
                for t in tries or []:
                    attempts.append({
                        "movement": movement,
                        "attempt": t.get("attempt"),
                        "weight": t.get("weight"),
                        "success": t.get("success"),
                    })
            best = {}
            for a in attempts:
                if a["success"] and isinstance(a["weight"], (int, float)):
                    m = a["movement"]
                    if a["weight"] > best.get(m, 0):
                        best[m] = a["weight"]
            results.append({
                "event_id": ev["id"], "event": ev["name"], "event_type": ev["type"],
                "date": (ast.get("date") or ev.get("start_date") or "")[:10] or None,
                "affiliated": ev.get("affiliated"),
                "weight_class": weight_class,
                "athlete_id": user.get("id"),
                "athlete": user.get("name"),
                "country": (user.get("country") or "").upper() or None,
                "gender": (user.get("gender") or "").lower() or None,
                "instagram": user.get("tag"),
                "place": ast.get("place"),
                "total": ast.get("total"),
                "ris": round(ast["ris"], 2) if isinstance(ast.get("ris"), (int, float)) else None,
                "disqualified": ast.get("disqualified"),
                "best": best,
                "attempts": attempts,
            })
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit-events", type=int, default=0, help="crawl only N events (debug)")
    parser.add_argument("--list-only", action="store_true", help="just enumerate events, no results")
    args = parser.parse_args()

    client = FinalRepClient()

    print("Listing events...")
    events = list_events(client)
    print(f"Found {len(events)} events")

    if args.list_only:
        OUT_PATH.write_text(json.dumps(
            {"source": "api.final-rep.com", "scraped_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
             "events": events, "results": []}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        print(f"Wrote {OUT_PATH} (events only)")
        return

    # only finished events carry results; skip events whose type is already
    # known to not be 4-lift 1RM (no API call wasted on them)
    finished = [e for e in events
                if e.get("finished")
                and (e.get("type") is None or e["type"] in STREETLIFTING_STAT_TYPES)]
    if args.limit_events:
        finished = finished[: args.limit_events]

    records = []
    skipped_maxrep = 0
    for i, ev in enumerate(finished, 1):
        stats = event_statistics(client, ev["id"])
        if not stats:
            print(f"  [{i}/{len(finished)}] {ev['name']}: no statistics")
            time.sleep(DELAY)
            continue
        etype = stats.get("event_type") or ev.get("type")
        ev["type"] = etype
        # keep only 1RM streetlifting; drop max-rep (League of Reps / AMRAP) events
        if etype not in STREETLIFTING_STAT_TYPES:
            skipped_maxrep += 1
            print(f"  [{i}/{len(finished)}] {ev['name']}: skipped ({etype})")
            time.sleep(DELAY)
            continue
        rows = parse_statistics(stats, ev)
        records.extend(rows)
        print(f"  [{i}/{len(finished)}] {ev['name']}: {len(rows)} results ({etype})")
        time.sleep(DELAY)
    print(f"Skipped {skipped_maxrep} non-1RM (max-rep) events")

    kept_events = [e for e in events
                   if e.get("type") is None or e["type"] in STREETLIFTING_STAT_TYPES]
    OUT_PATH.write_text(json.dumps({
        "source": "api.final-rep.com",
        "scraped_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "events": kept_events,
        "results": records,
    }, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"Wrote {OUT_PATH} ({len(records)} athlete-results across {len(events)} events)")


if __name__ == "__main__":
    main()
