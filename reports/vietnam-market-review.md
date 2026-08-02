# Vietnam New-Car Market — Analysis & Conclusions

> Generated from `data/market.db` by `src/analysis.py`. Source: VAMA monthly sales reports (model-level PDF). **Member companies only** — VinFast and (some periods) Hyundai Thanh Cong publish separately and are excluded.

## 1. Market at a glance

| Metric | Value |
| --- | --- |
| Data window (VAMA) | 2024-01 → 2026-06 |
| Months covered | 30 |
| Latest month (member) sales | 23,686 units |
| Period low / high | 9,853 / 38,910 |
| Top maker (latest) | Toyota (6,494, 27.4%) |
| Top model (latest) | Truck (2,173) |
| Regional split (N/C/S) | 10,098 / 4,636 / 8,952 |

## 2. Monthly sales trend

![Vietnam monthly total](data/analysis/vn_01_monthly_total.png)

VAMA member sales (this excludes VinFast and part-period Hyundai) track a market that is smaller in absolute volume than Thailand but has been more resilient. Note the figures are the *VAMA-member slice*, not the whole Vietnamese market.

## 3. Brand landscape

![Vietnam top makers](data/analysis/vn_02_top_makers.png)

Toyota leads comfortably (27.4% in the latest month, 2026-06); Mitsubishi, Ford, THACO KIA and Hyundai (where reported) follow. Unlike Thailand, **Chinese brands are barely present in VAMA data** — VinFast (domestic EV leader) is not a VAMA member, so the EV story is invisible in this dataset.

## 4. Best-selling models

![Vietnam top models](data/analysis/vn_03_top_models.png)

Top model in 2026-06: **Truck** (2,173 units). Mitsubishi Xpander, Toyota Veloz/Vios and Ford Ranger-type pickups/SUV consistently rank high.

## 5. Regional structure

![Vietnam regional split](data/analysis/vn_04_region_split.png)

VAMA splits every month into North / Central / South. In the latest month (2026-06): North **10,098**, Central **4,636**, South **8,952**. The South (Ho Chi Minh City + Mekong Delta) is the largest regional market, with the North (Hanoi) close behind.

## 6. Conclusions


1. **Toyota-led, Japanese-heavy.** The VAMA member market is dominated by Toyota, Mitsubishi, Ford and
   THACO KIA; Japanese/Korean/U.S. incumbents hold ~all share visible here.
2. **The dataset understates the true market.** VinFast (the domestic EV champion) is absent, so Vietnam's
   real EV penetration is *not* measurable from VAMA alone.
3. **Two-region duel.** North and South are the dominant demand poles; Central is a long tail.
4. **No powertrain detail.** VAMA publishes model/brand/region volume but not ICEvsEV split — a structural
   gap versus Thailand's FTI powertrain data.


---
*Data: VAMA (vama.org.vn). VinFast & part-period Hyundai excluded by source definition.*