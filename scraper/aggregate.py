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


def name_tokens(name):
    n = norm_name(name)
    return frozenset(n.split()) if n else frozenset()


def shift_date(iso, days):
    from datetime import date, timedelta
    try:
        y, m, d = map(int, iso.split("-"))
        return (date(y, m, d) + timedelta(days=days)).isoformat()
    except Exception:
        return None


def fix_case(name):
    """Final Rep stores many names lowercase — title-case them for display."""
    if name and name == name.lower():
        return " ".join(w.capitalize() for w in name.split())
    return name


def names_compatible(a, b):
    """True when one name's tokens are a subset of the other's
    (e.g. 'Pere Coll' vs 'Pere Coll Fernandez'). Requires >= 2 common tokens."""
    ta, tb = name_tokens(a), name_tokens(b)
    if not ta or not tb:
        return False
    return (ta <= tb or tb <= ta) and len(ta & tb) >= 2


# Final Rep event types kept: 4-movement 1RM streetlifting only.
# Underground events are the same All4 format — no distinction kept.
FR_TYPES = {"Calisthenics ONERM", "FinalRep Underground"}
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

    # OSL sometimes holds duplicate athlete profiles whose slug is the same
    # plus a uuid suffix (truncated name variants) — fold them together.
    UUID_SUFFIX = re.compile(r"-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
    osl_athletes = {a["id"]: a for a in osl["athletes"]}
    for aid in list(osl_athletes):
        base = UUID_SUFFIX.sub("", aid)
        if base != aid:
            twin = osl_athletes.get(base) or osl_athletes.get(base.rstrip("."))
            if twin and names_compatible(twin.get("name"), osl_athletes[aid].get("name")):
                twin["performances"] = twin.get("performances", []) + osl_athletes[aid].get("performances", [])
                names = [n.rstrip(". ") for n in (twin.get("name"), osl_athletes[aid].get("name")) if n]
                if names:
                    twin["name"] = max(names, key=len)
                del osl_athletes[aid]

    # ── source 1: Official Streetlifting (athlete histories) ──
    for a in osl_athletes.values():
        gender = a.get("gender")
        athlete_meta[a["id"]] = {
            "id": a["id"], "name": a.get("name"), "country": a.get("country"),
            "gender": gender, "profile_url": a.get("profile_url"), "instagram": None,
        }
        seen = set()
        for p in a.get("performances", []):
            if p.get("style") != "All4":   # 4-movement 1RM competitions only
                continue
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
        by_date_total = {}
        for row in performances:
            if row["total"] and row["date"]:
                by_key[(norm_name(row["athlete"]), row["date"], round(row["total"], 2))] = row
                by_date_total.setdefault((row["date"], round(row["total"], 2)), []).append(row)
        name_to_id = {norm_name(m["name"]): aid for aid, m in athlete_meta.items() if m["name"]}

        def find_match(r):
            """Same performance across sources: same total and compatible
            athlete name, within +/-2 days (multi-day competitions are dated
            differently by each source)."""
            if not (r.get("date") and r.get("total")):
                return None
            total = round(r["total"], 2)
            nm = norm_name(r.get("athlete"))
            for delta in (0, -1, 1, -2, 2):
                d = shift_date(r["date"], delta)
                if not d:
                    return None
                row = by_key.get((nm, d, total))
                if row is not None:
                    return row
            cands = []
            for delta in (0, -1, 1, -2, 2):
                d = shift_date(r["date"], delta)
                cands += [x for x in by_date_total.get((d, total), [])
                          if names_compatible(x["athlete"], r.get("athlete"))]
            return cands[0] if len({id(x) for x in cands}) >= 1 and len(cands) == 1 else None

        def find_athlete_id(name):
            """Unique athlete whose name is compatible (token subset) with `name`."""
            aid = name_to_id.get(norm_name(name))
            if aid:
                return aid
            cands = {a for n, a in name_to_id.items()
                     if names_compatible(n, name)}
            return cands.pop() if len(cands) == 1 else None

        for r in fr_api.get("results", []):
            if r.get("event_type") not in FR_TYPES or r.get("disqualified") or not r.get("best"):
                continue  # not 4-lift 1RM streetlifting, or no valid lift
            gender, klass = parse_fr_group(r.get("weight_class"))
            best = r["best"]
            extras = {
                "place": r.get("place"),
                "place_by_ris": True if (r.get("place") and r.get("ranked_by_ris")) else None,
                "instagram": r.get("instagram"),
                "ris_official": r.get("ris") or None,
                "attempts": [[a["movement"], a["attempt"], a["weight"], a["success"]]
                             for a in r.get("attempts", [])],
            }
            match = find_match(r)
            if match is not None:
                match.update({k: v for k, v in extras.items() if v})
                if extras["ris_official"]:
                    match["ris"] = extras["ris_official"]
                match["source"] = "osl+finalrep"
                owner = athlete_meta.get(match["athlete_id"])
                if owner and r.get("athlete"):
                    # OSL truncates long names ("Yanis Capitolin Na.."):
                    # if the FR name matches all but a short trailing fragment,
                    # prefer the FR (complete) form
                    ot = list((owner.get("name") or "").rstrip(". ").split())
                    ft = name_tokens(r["athlete"])
                    on = [norm_name(x) for x in ot]
                    if (len(on) >= 3 and len(on[-1]) <= 2
                            and set(on[:-1]) == set(ft) and on[-1] not in ft):
                        owner["name"] = fix_case(r["athlete"])
                if owner:   # backfill identity fields OSL doesn't always have
                    for field, value in (("instagram", r.get("instagram")),
                                         ("country", r.get("country")),
                                         ("gender", gender)):
                        if not owner.get(field) and value:
                            owner[field] = value
                fr_dupes += 1
                continue

            # new performance (event not covered by OSL)
            aid = find_athlete_id(r.get("athlete"))
            if aid is None:
                aid = f"fr-{r['athlete_id']}"
                if aid not in athlete_meta:
                    athlete_meta[aid] = {
                        "id": aid, "name": fix_case(r.get("athlete")), "country": r.get("country"),
                        "gender": gender, "profile_url": None, "instagram": r.get("instagram"),
                    }
                if r.get("athlete"):
                    name_to_id[norm_name(r["athlete"])] = aid
            meta = athlete_meta[aid]
            for field, value in (("instagram", r.get("instagram")),
                                 ("country", r.get("country")),
                                 ("gender", gender)):
                if not meta.get(field) and value:
                    meta[field] = value
            row = {
                "athlete_id": aid,
                "athlete": meta["name"] or r.get("athlete"),
                "country": meta["country"] or r.get("country"),
                "gender": meta["gender"] or gender,
                "class": klass,
                "bodyweight": None,
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

    # An athlete cannot post two results with the same total within 2 days:
    # such rows are source-side duplicates — keep the most informative one.
    def richness(row):
        return (bool(row.get("attempts")), bool(row.get("place")),
                sum(1 for v in row.values() if v is not None))
    groups = {}
    for row in performances:
        groups.setdefault((row["athlete_id"],
                           round(row["total"], 2) if row.get("total") else None), []).append(row)
    deduped, dropped = [], 0
    for rows in groups.values():
        rows.sort(key=lambda x: x.get("date") or "")
        kept = []
        for row in rows:
            near = next((k for k in kept if row.get("date") and k.get("date")
                         and abs((int(row["date"][:4]) * 372 + int(row["date"][5:7]) * 31 + int(row["date"][8:10]))
                                 - (int(k["date"][:4]) * 372 + int(k["date"][5:7]) * 31 + int(k["date"][8:10]))) <= 2), None)
            if near is None:
                kept.append(row)
            else:
                dropped += 1
                if richness(row) > richness(near):
                    near.update({k: v for k, v in row.items() if v is not None})
        deduped.extend(kept)
    performances = deduped
    if dropped:
        print(f"dropped {dropped} near-duplicate rows (same total within 2 days)")

    # Compute placements for rows that lack one (OSL-only competitions):
    # rank within (competition, gender, weight class) by total, lighter
    # bodyweight breaking ties — the standard streetlifting rule.
    comp_groups = {}
    for row in performances:
        if row.get("total") and row.get("competition") and row.get("gender"):
            comp_groups.setdefault(
                (row["competition"], row["gender"], row.get("class")), []).append(row)
    computed_places = 0
    for rows in comp_groups.values():
        rows.sort(key=lambda r: (-(r["total"] or 0), r.get("bodyweight") or float("inf")))
        for i, r in enumerate(rows, 1):
            if not r.get("place"):
                r["place"] = i
                computed_places += 1
    print(f"computed {computed_places} missing placements")

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
