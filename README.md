# SEA Auto Market Data — Thailand & Vietnam

Monthly new-car sales data for **Thailand** and **Vietnam**, crawled from
official-industry sources, stored in SQLite, and exported to diff-friendly
CSV/JSON. A scheduled GitHub Action refreshes it on the 1st of every month.

## Data sources

| Country | Source | What it covers | Granularity |
| --- | --- | --- | --- |
| 🇹🇭 Thailand | Federation of Thai Industries (FTI) — figures republished in full by [AutoLife Thailand](https://autolifethailand.tv) | Total market + breakdown by powertrain (ICE / BEV / PHEV / REEV / HEV) and by pickup segment (1-ton, modified/PPV) | Monthly **and** year-to-date (YTD) |
| 🇻🇳 Vietnam | [VAMA](http://vama.org.vn) monthly sales report (model-level `Detail.pdf`) | Every model sold by a VAMA member, broken out by region (North / Central / South) + YTD | Monthly, model-level |
| 🇹🇭🇻🇳 News | HeadlightMag, AutoLife Thailand, VnExpress ô-tô, Tuổi Trẻ Xe, Thanh Niên Xe (RSS) | New-model launches & market commentary | Rolling feed archive |

## Important coverage caveats

- **Vietnam VAMA = member companies only.** VinFast, and for some periods Hyundai
  Thanh Cong, publish separately and are **absent** from these figures. Treat VAMA
  as "the VAMA-member slice" of the market, not the whole Vietnamese market.
- **Thai calendar.** FTI reports use the Buddhist Era (2569 BE = 2026 CE, offset
  543). The pipeline converts to Common Era automatically.
- **Monthly vs YTD.** The `units` column is the monthly figure; `units_ytd` is the
  cumulative figure when the source published it. Some months' briefings report
  only one of the two — a row may legitimately have `units` *or* `units_ytd` null.
- **Subtotals.** VAMA `Sub-total` / `Total` rows are kept but tagged via
  `is_subtotal = 1` so aggregate queries can exclude them.

## Repository layout

```
src/
  config.py          # sources, URLs, month maps, constants
  db.py              # SQLite schema + idempotent upserts
  export.py          # deterministic CSV/JSON + manifest export
  run.py             # CLI: fetch | export | stats
  sources/
    base.py          # HTTP session, retry, HTML stripping, number parsing
    vama_vn.py       # Vietnam VAMA PDF parser
    fti_th.py        # Thailand FTI briefing parser
    news_rss.py      # TH/VN news RSS parser
data/
  market.db          # SQLite warehouse (LOCAL working copy; not committed)
  csv/  json/        # exported artifacts (committed)
  manifest.json      # coverage + run summary
  raw/vama/          # downloaded Detail PDFs (not committed)
```

## Run it locally

```bash
python -m venv .venv && .venv/Scripts/activate   # or: source .venv/bin/activate
pip install -r requirements.txt

python -m src.run fetch --full     # clean re-crawl of all history
python -m src.run fetch            # incremental refresh (newest months only)
python -m src.run export           # write CSV/JSON + manifest
python -m src.run stats            # coverage summary
```

## Schema (sales_monthly)

One row per `(country, year, month, level, maker, model, category, region, source)`:

| column | meaning |
| --- | --- |
| `level` | `total` \| `powertrain` \| `segment` \| `maker` \| `model` |
| `category` | powertrain code (ICE/BEV/PHEV/REEV/HEV) or segment (PICKUP_1T/PPV) or VAMA class |
| `units` | monthly units (may be null) |
| `units_ytd` | year-to-date units (may be null) |
| `yoy_pct` | year-over-year % (Thai `ลดลง` negated automatically) |
| `region` | `North` \| `Central` \| `South` \| `ALL` (VAMA only) |
| `is_subtotal` | 1 for VAMA Sub-total/Total roll-up rows |

## Automation

`.github/workflows/crawl.yml` runs `fetch --full` + `export` on the 1st of each
month and commits `data/csv`, `data/json`, `data/manifest.json`. Trigger it
manually from the Actions tab via "Run workflow".
