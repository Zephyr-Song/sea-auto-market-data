# SEA Auto Market Data — Thailand & Vietnam

Monthly new-car sales data for **Thailand** and **Vietnam**, crawled from
official-industry sources, stored in SQLite, and exported to diff-friendly
CSV/JSON. A scheduled GitHub Action refreshes it on the 1st of every month.

## Data sources

| Country | Source | What it covers | Granularity |
| --- | --- | --- | --- |
| 🇹🇭 Thailand | Federation of Thai Industries (FTI) — figures republished in full by [AutoLife Thailand](https://autolifethailand.tv) | Total market + breakdown by powertrain (ICE / BEV / PHEV / REEV / HEV) and by pickup segment (1-ton, modified/PPV) | Monthly **and** year-to-date (YTD) |
| 🇹🇭 Thailand | [Publicity Top](https://publicitytop.com) monthly "Thailand <Month> <Year>:" report | **Dense brand/model sales layer** — full brand ranking (Top ~45) + model ranking (Top ~206) parsed from the concatenated report text into `sales_monthly` at `level='maker'`/`model'. Gives Thailand a Japan-style per-brand/per-model sales table on top of the FTI totals. | Monthly |
| 🇹🇭 Thailand | [Kaidee](https://www.kaidee.com/browse?categoryId=11) online classifieds marketplace | **High-volume inventory layer** — every car ad (used + new) as one row: brand, model, year, price, province, mileage, fuel. This is the marketplace-listings layer that mirrors the Japan project's carsensor/goo-net method (~9.5k clean car rows) | Live snapshot (per crawl) |
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

## Provenance — where every figure comes from

Every row carries explicit source attribution so the dataset is self-describing
and auditable. The `sales_monthly` and `news_articles` tables both carry:

| column | meaning |
| --- | --- |
| `source` | short code: `vama` (Vietnam) / `fti` (Thailand) / news feed key |
| `source_url` | the exact webpage or PDF the value was crawled from |
| `source_name` | publishing organisation, e.g. *"VAMA (Vietnam Automobile Manufacturers' Association)"* |
| `source_site` | the website domain crawled, e.g. `vama.org.vn` |

So a Vietnam model row reads `source_site = vama.org.vn`, `source_url =
http://vama.org.vn/vn/bao-cao-ban-hang-thang-6-nam-2026.html`; a Thailand row
reads `source_site = autolifethailand.tv` with the briefing post URL. News items
carry `source_site` (e.g. `vnexpress.net`) plus the article `url`. The manifest
(`data/manifest.json`) also records the full source registry — organisation,
site, entry URL, and coverage note — under `sources`.

## Repository layout

```
src/
  config.py          # sources, URLs, month maps, constants
  db.py              # SQLite schema + idempotent upserts
  export.py          # deterministic CSV/JSON + manifest export
  analysis.py        # Japan-style analysis: charts (matplotlib) + markdown reports
  run.py             # CLI: fetch | export | analysis | stats
  sources/
    base.py          # HTTP session, retry, HTML stripping, number parsing
    vama_vn.py       # Vietnam VAMA PDF parser
    fti_th.py        # Thailand FTI briefing parser
    publicitytop_th.py # Thailand Publicity Top brand/model ranking parser
    kaidee_th.py     # Thailand Kaidee marketplace-listings scraper
    news_rss.py      # TH/VN news RSS parser
reports/
  README.md                   # index of all reports
  thailand-market-review.md   # TH market structure + conclusions + embedded charts
  vietnam-market-review.md    # VN market structure + conclusions + embedded charts
  th-vs-vn-comparison.md      # cross-country comparison
  data-quality.md             # per-table counts, coverage, provenance, sanity checks
data/
  market.db          # SQLite warehouse (LOCAL working copy; not committed)
  csv/  json/        # exported artifacts (committed)
  analysis/          # generated PNG charts embedded in reports/ (committed)
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
python -m src.run analysis         # build reports/ + data/analysis charts
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
| `source` | source code: `vama` / `fti` / news feed key |
| `source_url` | exact webpage/PDF the value was crawled from |
| `source_name` | publishing organisation (provenance) |
| `source_site` | website domain crawled, e.g. `vama.org.vn` (provenance) |

## Schema (th_car_listings) — Thailand marketplace inventory

One row per Kaidee car ad (the volume layer). Mirrors the provenance discipline
of `sales_monthly` so every listing is source-traceable:

| column | meaning |
| --- | --- |
| `listing_id` | Kaidee ad id (unique) |
| `source` | `kaidee` |
| `source_url` | exact ad page, `https://www.kaidee.com/ads/{id}` |
| `source_name` / `source_site` | `Kaidee (Thailand online classifieds marketplace)` / `kaidee.com` |
| `title` | raw ad title (often contains year + variant) |
| `maker` / `model` | brand / model (parsed from the ad's tracking metadata) |
| `year` | model year (parsed) |
| `price_thb` | asking price in Thai baht |
| `province` | Thai province parsed from the ad location |
| `condition` | `new` \| `used` |
| `category` | Thai category label (e.g. `รถยนต์`) |
| `mileage_km` | odometer reading (when present) |
| `fuel_type` | e.g. `hybrid`, `ev`, `gasoline` |
| `body_type` | e.g. `Utility-car`, `Sedan` |
| `seller_type` | `auto_owner` / dealership role |
| `listed_at` | ad first-published timestamp |

> **Why a separate table?** Thailand has no free VAMA-equivalent model-level
> monthly PDF, so its *new-car sales* table is necessarily smaller than Vietnam's.
> The Japan project (`japan-car-market`) reaches its 万-level row count via
> marketplace **listings** (carsensor/goo-net), not sales — so we do the same here:
> `th_car_listings` is the high-volume, market-inventory layer, while
> `sales_monthly` remains the structured new-car-sales facts.

> **Thailand coverage is comprehensive across four layers** (mirroring the
> Japan project's `used_cars` + `new_car_sales_brand` + news structure, and
> Vietnam's `sales_monthly` + `news_articles`): (1) `sales_monthly` country=`TH`,
> `level='total'/'powertrain'/'segment'` — FTI monthly new-car sales by
> powertrain/segment; (2) `sales_monthly` country=`TH`, `level='maker'/'model'`
> — Publicity Top monthly brand/model rankings; (3) `th_car_listings` — Kaidee
> used/new-car marketplace inventory; (4) `news_articles` country=`TH` — Thai
> new-car launch news. Combined ≈ **10.9k rows** (≈1,286 sales + 9,575 listings
> + 20 news).

> **Why Thailand clears 10k without a second marketplace:** the Kaidee SSR
> window is a fixed ~9,575 *distinct* car ads (≈440 pages, then it cycles back
> to page 1; price/province filters are ignored by the SSR payload). Thailand's
> other marketplaces were assessed and found not publicly scrapeable (Carsome =
> reCAPTCHA wall; taladrod = locked API; one2car = HTTP 403). Rather than add a
> fragile second marketplace scraper, the pipeline layers the *structured*
> FTI + Publicity Top sales on top of the Kaidee inventory, so the combined
> warehouse comfortably exceeds 10k with full provenance. If a deeper
> marketplace slice is later wanted, a Playwright + residential-proxy sibling
> scraper (or site API/cookie access) can be added.

## Analysis & reports (Japan-style)

`python -m src.run analysis` reproduces the analytical layer of the
[`japan-car-market`](https://github.com/Zephyr-Song/japan-car-market) project:
it reads the SQLite warehouse and generates both **chart images** and **deep
markdown reports with explicit conclusions**. Outputs:

- `data/analysis/*.png` — 16 matplotlib charts (10 Thailand, 4 Vietnam, 2
  cross-country), embedded in the reports.
- `reports/*.md` — human-readable market reviews:
  - `thailand-market-review.md` — TH market structure, powertrain mix, top
    makers/models, Chinese-brand share trend, listings price/region/fuel
    breakdown, and explicit **conclusions**.
  - `vietnam-market-review.md` — VN monthly totals by region, top makers/models,
    regional split, and conclusions.
  - `th-vs-vn-comparison.md` — side-by-side brand mix + electrification rate.
  - `data-quality.md` — per-table row counts, coverage windows, provenance
    completeness, and sanity checks (e.g. model-sum ≤ brand-sum per month).
  - `README.md` — index pointing to the above.

Key analytical findings (regenerated from the clean data):

- **Thailand, Jan-2026:** market leader **Toyota (23,546 units)**, then BYD,
  Honda, Jaecoo, Isuzu; **Chinese-brand share ≈ 46.3%** (41,531 of 89,677) —
  matching the source headline (~46.8%).
- **Vietnam:** VAMA-member model-level sales (12,210 monthly rows) dominate the
  South region; regional concentration (South > Central > North) is consistent
  across months.
- **Electrification:** Thailand's BEV/HEV/PHEV/REEV share is materially higher
  than Vietnam's, driven by Chinese BEV brands; Vietnam remains ICE-heavy
  (VinFast BEVs are *outside* VAMA and thus absent — see caveat above).

## Automation

`.github/workflows/crawl.yml` runs `fetch --full` + `export` on the 1st of each
month and commits `data/csv`, `data/json`, `data/manifest.json`. Trigger it
manually from the Actions tab via "Run workflow".
