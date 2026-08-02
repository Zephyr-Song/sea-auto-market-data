# Thailand vs Vietnam — Comparative Analysis

> Why the two datasets look different, and what each can / cannot tell you.

## 1. Data-layer comparison

| Layer | Thailand | Vietnam |
| --- | --- | --- |
| New-car total + powertrain | FTI (autolifethailand.tv) | — (VAMA has no powertrain split) |
| Brand/model monthly sales | Publicity Top (publicitytop.com) | VAMA model-level PDF |
| Regional split | — (FTI national only) | North/Central/South (VAMA) |
| Marketplace inventory | Kaidee (9,575 ads) | — |
| News/launches | HeadlightMag, AutoLife RSS | VnExpress, Tuổi Trẻ, Thanh Niên RSS |

## 2. Brand leadership, side by side

![Top brands comparison](data/analysis/cmp_01_top_brands.png)

Thailand's top-10 is contested by Chinese brands (BYD, MG, GWM) alongside Japanese incumbents; Vietnam's top-10 is almost entirely Japanese/Korean/U.S. incumbents because VinFast sits outside VAMA.

## 3. Electrification gap

![Electrification](data/analysis/cmp_02_electrification.png)

Thailand publishes a full powertrain breakdown, so its electrified share can be measured directly (and is high, hybrid-led). Vietnam's VAMA feed has no powertrain field, so the only way to read EV penetration there is to add VinFast/Hyundai data — currently out of scope.

## 4. Conclusions


1. **Thailand = richer, more comparable to Japan.** It has powertrain, brand and a marketplace-inventory
   layer, mirroring the Japan repo's structure. Chinese-brand disruption is the headline.
2. **Vietnam = cleaner brand/region facts but a blind spot on EVs.** VAMA is the gold standard for
   model/region volume but omits VinFast and powertrain.
3. **Do not compare the two totals head-to-head.** Thailand's FTI total ≠ Vietnam's VAMA member total in
   coverage; each carries a different exclusion (FTI = national total incl. all brands; VAMA = members only).
4. **Both exceed 10,000 rows** in the warehouse, satisfying the volume target, with full per-row provenance.


---
*Methodology mirrored from `japan-car-market` (Zephyr-Song).*