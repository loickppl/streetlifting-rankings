# 🏋️ Streetlifting World Rankings

**FR** — Agrégateur de données streetlifting : records mondiaux officiels et classements
d'athlètes en compétition officielle, collectés automatiquement depuis les sources fiables
de la discipline et présentés sur un site statique avec tous les classements possibles
(total, RIS, par mouvement, par catégorie de poids ou toutes catégories confondues).

**EN** — Streetlifting data aggregator: official world records and athlete rankings from
sanctioned competitions, automatically collected from the sport's reliable sources and
presented on a static site with every ranking you may want (total, RIS, per movement,
per weight class or open).

**Site**: https://loickppl.github.io/streetlifting-rankings/

## Sources / Data

| Source | Data |
|---|---|
| [Official Streetlifting rankings](https://rankings.officialstreetlifting.com/) | Full athlete competition histories: muscle-up, pull-up, dip, squat, total, RIS, weight class, bodyweight, style, competition, date |
| [Final Rep records](https://final-rep.com/records/) | Official world records per weight class and movement |
| [RIS — warisradji.com](https://warisradji.com/ris/) | Relative Index for Streetlifting formula (2025 constants), recomputed locally |

### RIS

`RIS = Total × 100 / (A + (K − A) / (1 + Q·e^(−B·(BW − v))))`

| | A | K | B | v | Q |
|---|---|---|---|---|---|
| Men | 338.0 | 549.0 | 0.11354 | 74.777 | 0.53096 |
| Women | 164.0 | 270.0 | 0.13776 | 57.855 | 0.37089 |

## Architecture

```
scraper/
  scrape_osl.py        # scrape rankings.officialstreetlifting.com (athletes + histories)
  scrape_finalrep.py   # scrape final-rep.com world records
  aggregate.py         # merge, recompute RIS, build the site JSON files
data/
  raw/                 # raw scraped JSON (one file per source)
  site/                # aggregated output
docs/                  # static site (GitHub Pages) — reads docs/data/*.json
scripts/
  update.sh            # daily cron entrypoint: scrape → aggregate → commit → push
```

Plain Python (stdlib + `requests`), plain HTML/CSS/JS — no build step, no framework.
The JSON files are the "database"; migrating later to a real DB (PostgreSQL, SQLite)
only requires importing `data/site/performances.json`.

## Local usage

```bash
pip install -r scraper/requirements.txt
python3 scraper/scrape_osl.py        # ~5 min, polite crawl
python3 scraper/scrape_finalrep.py
python3 scraper/aggregate.py
# serve the site locally:
python3 -m http.server -d docs 8080
```

## Daily refresh (homelab)

```cron
0 6 * * * /path/to/streetlifting-rankings/scripts/update.sh >> /var/log/streetlifting-update.log 2>&1
```

The script scrapes both sources, regenerates the JSON, and pushes only when the data
changed. GitHub Pages redeploys automatically on push.

## Disclaimer

Unaffiliated community project. Data is aggregated automatically from public pages and
belongs to its respective publishers; scrapers use a polite crawl delay and an
identifying User-Agent.
