#!/usr/bin/env python3
"""
Aggregate raw scraped data into the JSON files served by the site.

Inputs  : data/raw/*.json (one raw file per source — staging for the scrapers)
Output  : data/site/streetlifting.json — single consolidated database:
          meta + athletes (with embedded competition histories, recomputed RIS)
          + records from every source (Final Rep official + computed from the
          OSL performance database). Mirrored to docs/data/ for the site.

RIS (Relative Index for Streetlifting, warisradji.com/ris, 2025 constants):
    RIS = Total * 100 / (A + (K - A) / (1 + Q * exp(-B * (BW - v))))
Recomputed here whenever bodyweight is known; the site-reported value is kept
as `ris_site` for reference.
"""

import json
import math
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
SITE = ROOT / "data" / "site"

# 2025 RIS constants [A, K, B, v, Q] from warisradji.com/ris/static/ris.js
RIS_CONST = {
    "male": (338.0, 549.0, 0.11354, 74.777, 0.53096),
    "female": (164.0, 270.0, 0.13776, 57.855, 0.37089),
}

MOVEMENTS = ["muscle_up", "pull_up", "dip", "squat", "total"]


def ris_score(gender, bodyweight, total):
    if not bodyweight or not total or gender not in RIS_CONST:
        return None
    a, k, b, v, q = RIS_CONST[gender]
    coeff = 100.0 / (a + (k - a) / (1.0 + q * math.exp(-b * (bodyweight - v))))
    return round(coeff * total, 2)


def load(name):
    path = RAW / name
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def norm_name(name):
    """Diacritics/case-insensitive key for cross-source athlete matching."""
    if not name:
        return None
    s = unicodedata.normalize("NFKD", name)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


# Final Rep event types that are 1RM streetlifting, mapped to a style label
FR_STYLES = {
    "Calisthenics ONERM": "All4",
    "Calisthenics ONERM Classic": "Classic",
    "Calisthenics ONERM 3L": "3 Lift",
    "FinalRep Underground": "Underground",
    "FinalRep Underground Classic": "Underground",
    "FinalRep Underground 3L": "Underground",
}
FR_CLASS_RE = re.compile(r"^(Male|Female|Men|Women)\s*([+\-]\d+(?:\.\d+)?kg)?", re.I)


def parse_fr_group(weight_class):
    """'Male -94kg' -> ('male', '-94kg'); 'Female' -> ('female', None)."""
    if not weight_class:
        return None, None
    m = FR_CLASS_RE.match(weight_class.strip())
    if not m:
        return None, weight_class
    gender = "male" if m.group(1).lower() in ("male", "men") else "female"
    return gender, m.group(2)


def main():
    osl = load("osl_athletes.json")
    finalrep = load("finalrep_records.json")
    fr_api = load("finalrep_api.json")
    if osl is None:
        raise SystemExit("data/raw/osl_athletes.json missing — run scrape_osl.py first")

    performances = []          # flat rows, all sources
    athlete_meta = {}          # athlete_id -> identity record

    # ── source 1: Official Streetlifting (athlete histories) ──
    for a in osl["athletes"]:
        gender = a.get("gender")
        athlete_meta[a["id"]] = {
            "id": a["id"], "name": a.get("name"), "country": a.get("country"),
            "gender": gender, "profile_url": a.get("profile_url"), "instagram": None,
        }
        seen = set()
        for p in a.get("performances", []):
            key = tuple(sorted(p.items()))
            if key in seen:      # exact duplicate rows (source glitches)
                continue
            seen.add(key)
            ris = ris_score(gender, p.get("bodyweight"), p.get("total"))
            performances.append({
                "athlete_id": a["id"],
                "athlete": a.get("name"),
                "country": a.get("country"),
                "gender": gender,
                "class": p.get("class"),
                "bodyweight": p.get("bodyweight"),
                "style": p.get("style"),
                "muscle_up": p.get("muscle_up"),
                "pull_up": p.get("pull_up"),
                "dip": p.get("dip"),
                "squat": p.get("squat"),
                "total": p.get("total"),
                "ris": ris if ris is not None else (p.get("ris_site") or None),
                "ris_site": p.get("ris_site"),
                "competition": p.get("competition"),
                "date": p.get("date"),
                "source": "osl",
            })

    # ── source 2: Final Rep app API (attempt-level results) ──
    # Many competitions exist in both sources; a result is "the same" when
    # athlete (name, diacritics-insensitive), date and total all match.
    fr_new = fr_dupes = 0
    if fr_api:
        by_key = {}
        for row in performances:
            if row["total"] and row["date"]:
                by_key[(norm_name(row["athlete"]), row["date"], round(row["total"], 2))] = row
        name_to_id = {norm_name(m["name"]): aid for aid, m in athlete_meta.items() if m["name"]}

        for r in fr_api.get("results", []):
            style = FR_STYLES.get(r.get("event_type"))
            if style is None or r.get("disqualified") or not r.get("best"):
                continue  # not 1RM streetlifting, or no valid lift
            gender, klass = parse_fr_group(r.get("weight_class"))
            best = r["best"]
            extras = {
                "place": r.get("place"),
                "instagram": r.get("instagram"),
                "ris_official": r.get("ris") or None,
                "attempts": [[a["movement"], a["attempt"], a["weight"], a["success"]]
                             for a in r.get("attempts", [])],
            }
            key = (norm_name(r.get("athlete")), r.get("date"),
                   round(r["total"], 2) if r.get("total") else None)
            match = by_key.get(key)
            if match is not None:
                match.update({k: v for k, v in extras.items() if v})
                if extras["ris_official"]:
                    match["ris"] = extras["ris_official"]
                match["source"] = "osl+finalrep"
                owner = athlete_meta.get(match["athlete_id"])
                if owner and not owner.get("instagram") and r.get("instagram"):
                    owner["instagram"] = r["instagram"]
                fr_dupes += 1
                continue

            # new performance (event not covered by OSL)
            aid = name_to_id.get(norm_name(r.get("athlete")))
            if aid is None:
                aid = f"fr-{r['athlete_id']}"
                if aid not in athlete_meta:
                    athlete_meta[aid] = {
                        "id": aid, "name": r.get("athlete"), "country": r.get("country"),
                        "gender": gender, "profile_url": None, "instagram": r.get("instagram"),
                    }
                if r.get("athlete"):
                    name_to_id[norm_name(r["athlete"])] = aid
            meta = athlete_meta[aid]
            if meta.get("instagram") is None and r.get("instagram"):
                meta["instagram"] = r["instagram"]
            row = {
                "athlete_id": aid,
                "athlete": meta["name"] or r.get("athlete"),
                "country": meta["country"] or r.get("country"),
                "gender": meta["gender"] or gender,
                "class": klass,
                "bodyweight": None,
                "style": style,
                "muscle_up": best.get("muscle_up"),
                "pull_up": best.get("pull_up"),
                "dip": best.get("dip"),
                "squat": best.get("squat"),
                "total": r.get("total"),
                "ris": extras["ris_official"],
                "ris_site": None,
                "competition": r.get("event"),
                "date": r.get("date"),
                "source": "finalrep",
                **{k: v for k, v in extras.items() if v and k != "ris_official"},
            }
            performances.append(row)
            fr_new += 1
        print(f"finalrep api: {fr_new} new performances, {fr_dupes} merged into OSL rows")

    # ── athlete records built from the merged rows ──
    by_athlete = {}
    for row in performances:
        by_athlete.setdefault(row["athlete_id"], []).append(row)
    athletes = []
    for aid, perfs in by_athlete.items():
        meta = athlete_meta[aid]
        athletes.append({
            **meta,
            "n_competitions": len(perfs),
            "best": {m: max((p[m] for p in perfs if p.get(m)), default=None) for m in MOVEMENTS},
            "best_ris": max((p["ris"] for p in perfs if p.get("ris")), default=None),
            "performances": [
                {k: v for k, v in p.items()
                 if k not in ("athlete_id", "athlete", "country", "gender")}
                for p in perfs
            ],
        })
    athletes.sort(key=lambda a: a["id"])

    # Records computed from the OSL performance database:
    # best mark per (gender, class, movement) and per (gender, 'all', movement).
    computed = {}
    for p in performances:
        if not p["gender"]:
            continue
        for movement in MOVEMENTS + ["ris"]:
            value = p.get(movement)
            if not value:
                continue
            for klass in (p["class"], "all"):
                if not klass:
                    continue
                key = (p["gender"], klass, movement)
                if key not in computed or value > computed[key]["value"]:
                    computed[key] = {
                        "gender": p["gender"], "class": klass, "movement": movement,
                        "value": value, "athlete": p["athlete"], "athlete_id": p["athlete_id"],
                        "country": p["country"], "competition": p["competition"],
                        "date": p["date"], "bodyweight": p["bodyweight"],
                    }

    records = {
        "finalrep": finalrep["records"] if finalrep else [],
        "computed_osl": sorted(
            computed.values(),
            key=lambda r: (r["gender"], r["class"], r["movement"]),
        ),
    }

    meta = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sources": {
            "officialstreetlifting": {
                "scraped_at": osl.get("scraped_at"),
                "athletes": len(athletes),
                "performances": len(performances),
            },
            "finalrep": {
                "scraped_at": finalrep.get("scraped_at") if finalrep else None,
                "records": len(records["finalrep"]),
            },
            "finalrep_api": {
                "scraped_at": fr_api.get("scraped_at") if fr_api else None,
                "events": len(fr_api.get("events", [])) if fr_api else 0,
                "new_performances": fr_new if fr_api else 0,
                "merged_performances": fr_dupes if fr_api else 0,
            },
        },
    }

    database = {"meta": meta, "records": records, "athletes": athletes}

    SITE.mkdir(parents=True, exist_ok=True)
    out = SITE / "streetlifting.json"
    out.write_text(json.dumps(database, ensure_ascii=False, separators=(",", ":")),
                   encoding="utf-8")
    print(f"wrote {out}")

    # The GitHub Pages site reads from docs/data/ — mirror the output there.
    docs_data = ROOT / "docs" / "data"
    docs_data.mkdir(parents=True, exist_ok=True)
    docs_data.joinpath("streetlifting.json").write_bytes(out.read_bytes())
    print("mirrored to docs/data/streetlifting.json")

    print(f"{len(athletes)} athletes, {len(performances)} performances, "
          f"{len(records['finalrep'])} finalrep records, {len(records['computed_osl'])} computed records")


if __name__ == "__main__":
    main()
