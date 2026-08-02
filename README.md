# SEA Auto Market Data — Thailand & Vietnam

Monthly new-car sales data for **Thailand** and **Vietnam**, crawled from
official-industry sources, stored in SQLite, and exported to diff-friendly
CSV/JSON. A scheduled GitHub Action refreshes it on the 1st of every month.

## Data sources

| Country | Source | What it covers | Granularity |
| --- | --- | --- | --- |
| 🇹🇭 Thailand | Federation of Thai Industries (FTI) — figures republished in full by [AutoLife Thailand](https://autolifethailand.tv) | Total market + breakdown by powertrain (ICE / BEV / PHEV / REEV / HEV) and by pickup segment (1-ton, modified/PPV) | Monthly **and** year-to-date (YTD) |
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
  run.py             # CLI: fetch | export | stats
  sources/
    base.py          # HTTP session, retry, HTML stripping, number parsing
    vama_vn.py       # Vietnam VAMA PDF parser
    fti_th.py        # Thailand FTI briefing parser
    kaidee_th.py     # Thailand Kaidee marketplace-listings scraper
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

> **Thailand coverage is comprehensive across three layers** (mirroring the
> Japan project's `used_cars` + `new_car_sales_brand` + news structure, and
> Vietnam's `sales_monthly` + `news_articles`): (1) `sales_monthly` country=`TH`
> — FTI monthly new-car sales by powertrain/segment; (2) `th_car_listings` —
> Kaidee used/new-car marketplace inventory; (3) `news_articles` country=`TH` —
> Thai new-car launch news. Total ≈ **9.6k rows** (≈9,575 listings + 51 sales +
> 20 news).
>
> **Volume ceiling (transparency):** Kaidee's server-rendered car browse is a
> fixed window — it returns ~9,575 *distinct* car ads (≈440 pages) and then
> cycles back to page 1; price/province-name filters are ignored by the SSR
> payload, and per-province feeds are small disjoint slices of the same
> aggregate. Thailand's other marketplaces were assessed and found not
> publicly scrapeable (Carsome = reCAPTCHA wall; taladrod = locked API;
> one2car = HTTP 403). So a single free scrapeable Thai source caps the
> used-car layer at ~9,575. To genuinely exceed 10k, a **second** Thai
> marketplace source is needed — feasible via Playwright + a residential proxy
> or with site API access/cookies, which would be added as a sibling scraper.

## Automation

`.github/workflows/crawl.yml` runs `fetch --full` + `export` on the 1st of each
month and commits `data/csv`, `data/json`, `data/manifest.json`. Trigger it
manually from the Actions tab via "Run workflow".
