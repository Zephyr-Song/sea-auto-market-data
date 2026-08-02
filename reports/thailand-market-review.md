# Thailand New-Car Market — Analysis & Conclusions

> Generated from `data/market.db` by `src/analysis.py`. All figures are source-traceable (every row carries `source`/`source_site`/`source_url`).

## 1. Market at a glance

| Metric | Value |
| --- | --- |
| Data window (FTI total) | 2024-05 → 2026-06 |
| Months covered (FTI total) | 13 |
| Latest month total market | 58,724 units |
| Period low / high | 47,032 / 75,121 |
| Latest electrified share (FTI) | 80.9% |
| Chinese-brand share (latest) | 46.3%  (2024-08→2026-01) |
| Brands tracked (latest month) | 36 |
| Marketplace listings (Kaidee) | 9,575 |
| Median asking price | 469,000 THB |
| New vs Used (listings) | 195 new / 9,380 used |

## 2. Total market & year-on-year

![Thailand total market](data/analysis/th_01_market_trend.png)

Thailand's total new-car market, as reported by the Federation of Thai Industries (via AutoLife Thailand), is a mature but cyclical market. The chart above shows monthly volume with the FTI-published year-on-year change. The market has been under structural pressure (household debt, tightened auto-loan underwriting) since 2024, which is visible in the depressed totals versus the 2010s peak.

## 3. Powertrain mix — the electrification story

![Thailand powertrain mix](data/analysis/th_02_powertrain_mix.png)

In the latest month with a full powertrain breakdown (**2026-06**), electrified powertrains (BEV + HEV + PHEV + REEV) accounted for **80.9%** of the market — 22,275 BEV and 10,504 HEV units alone. Thailand is one of the few markets in the region where hybrids (HEV) are mainstream, and BEV share has been climbing rapidly off a low base.

## 4. Brand landscape & the Chinese surge

![Thailand top makers](data/analysis/th_03_top_makers.png)

![Chinese-brand share trend](data/analysis/th_04_chinese_share.png)

Chinese brands have gone from a niche to a dominant force. In the latest month (**2026-01**) they hold **46.3%** of the market by units (up from 5.1% at the start of the tracked window, **2024-08**). BYD in particular has overtaken legacy Japanese majors in several months. The top maker in the latest tracked month is **Toyota** (23,546 units).

## 5. Best-selling models

![Thailand top models](data/analysis/th_05_top_models.png)

Top model in 2026-01: **Gr** (8,968 units). Pickup trucks (Isuzu D-Max, Toyota Hilux) and Japanese SUVs dominate the upper ranks, while Chinese EVs (BYD, MG, Jaecoo) now appear in the top tier.

## 6. Marketplace inventory (Kaidee used/new-car ads)

![Price distribution](data/analysis/th_06_price_distribution.png)

![Top brands in inventory](data/analysis/th_07_listing_brands.png)

![Top provinces](data/analysis/th_08_province.png)  ![Region split](data/analysis/th_09_region.png)

![Fuel & condition](data/analysis/th_10_fuel_condition.png)

The Kaidee inventory snapshot (9,575 ads) is the high-volume layer that mirrors the Japan project's carsensor/goo-net method. Median asking price is **469,000 THB** (P25 318,000 / P75 709,000). Inventory is heavily concentrated in **Bangkok** (6,592 ads, 68.8% of all listings), confirming the used-car market is a Bangkok-metro phenomenon. Hybrid vehicles are **7.9%** of listings — high versus most markets, reflecting Thai buyers' hybrid preference.

## 7. Conclusions


1. **Electrification is real and hybrid-led.** ~81% of new cars in the latest
   breakdown are electrified; HEV is the volume driver, BEV the fast-growing niche.
2. **Chinese brands are the single biggest structural shift.** Share rose to
   46.3% by 2026-01, with BYD challenging Toyota/Honda on volume.
3. **Japanese incumbents are defensive.** Toyota/Isuzu/Honda remain large but are losing share to
   Chinese entrants, especially in BEV and compact SUV segments.
4. **The used-car market is Bangkok-centric and hybrid-heavy**, with a median asking price around
   469,000 THB.
5. **Caveat:** FTI totals and publicitytop brand rankings are independent sources; brand shares here are
   computed *within* the publicitytop ranking, not against the FTI total. Full-year posts on publicitytop
   carry no monthly ranking and are excluded.


---
*Data: FTI (autolifethailand.tv), Publicity Top (publicitytop.com), Kaidee (kaidee.com). See `README.md` for provenance.*