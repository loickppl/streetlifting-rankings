#!/usr/bin/env python3
"""
Aggregate raw scraped data into the JSON files served by the site.

Inputs  : data/raw/osl_athletes.json, data/raw/finalrep_records.json
Outputs : data/site/athletes.json      — athlete index + full histories
          data/site/performances.json  — flat list, one row per competition result
          data/site/records.json       — Final Rep official records + records
                                         computed from the performance database
          data/site/meta.json          — freshness + stats

RIS (Relative Index for Streetlifting, warisradji.com/ris, 2025 constants):
    RIS = Total * 100 / (A + (K - A) / (1 + Q * exp(-B * (BW - v))))
Recomputed here whenever bodyweight is known; the site-reported value is kept
as `ris_site` for reference.
"""

import json
import math
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


def main():
    osl = load("osl_athletes.json")
    finalrep = load("finalrep_records.json")
    if osl is None:
        raise SystemExit("data/raw/osl_athletes.json missing — run scrape_osl.py first")

    athletes = []
    performances = []

    for a in osl["athletes"]:
        gender = a.get("gender")
        perfs = []
        for p in a.get("performances", []):
            ris = ris_score(gender, p.get("bodyweight"), p.get("total"))
            row = {
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
            }
            perfs.append(row)
            performances.append(row)

        athletes.append({
            "id": a["id"],
            "name": a.get("name"),
            "country": a.get("country"),
            "gender": gender,
            "profile_url": a.get("profile_url"),
            "n_competitions": len(perfs),
            "best": {m: max((p[m] for p in perfs if p.get(m)), default=None) for m in MOVEMENTS},
            "best_ris": max((p["ris"] for p in perfs if p.get("ris")), default=None),
        })

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
        },
    }

    SITE.mkdir(parents=True, exist_ok=True)
    for name, payload in [
        ("athletes.json", athletes),
        ("performances.json", performances),
        ("records.json", records),
        ("meta.json", meta),
    ]:
        (SITE / name).write_text(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        print(f"wrote data/site/{name}")

    # The GitHub Pages site reads from docs/data/ — mirror the output there.
    docs_data = ROOT / "docs" / "data"
    docs_data.mkdir(parents=True, exist_ok=True)
    for name in ["athletes.json", "performances.json", "records.json", "meta.json"]:
        docs_data.joinpath(name).write_bytes((SITE / name).read_bytes())
    print("mirrored to docs/data/")

    print(f"{len(athletes)} athletes, {len(performances)} performances, "
          f"{len(records['finalrep'])} finalrep records, {len(records['computed_osl'])} computed records")


if __name__ == "__main__":
    main()
