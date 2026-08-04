"""Extract real numbers from market.db for the detailed report (corrected)."""
import sqlite3, json, statistics
from pathlib import Path

DB = Path(__file__).resolve().parent / "data" / "market.db"
c = sqlite3.connect(DB)
c.row_factory = sqlite3.Row

CHINESE = ("BYD","MG","GWM","GREAT WALL","CHANGAN","CHERY","JAECOO","OMODA",
           "NETA","LEAPMOTOR","ZEEKR","LYNK","DEEPAL","HAVAL","TANK","GEELY",
           "ORA","GAC","DENZA","IM","AITO","XIAOMI","VOYAH","BRILLIANCE","BAIC","DONGFENG")
JAPANESE = ("TOYOTA","HONDA","ISUZU","MITSUBISHI","NISSAN","MAZDA","SUZUKI",
            "SUBARU","DAIHATSU","LEXUS","INFINITI","ACURA")
KOREAN = ("HYUNDAI","KIA","GENESIS")
US = ("FORD","CHEVROLET","CHEV","TESLA","GMC","JEEP","CADILLAC","DODGE","RAM")
EU = ("MERCEDES","BMW","MINI","AUDI","VOLKSWAGEN","VW","PORSCHE","VOLVO",
      "PEUGEOT","RENAULT","CITROEN","FIAT","SKODA","LAND ROVER","JAGUAR",
      "BENTLEY","FERRARI","LAMBORGHINI","MASERATI")

def origin(name):
    if not name:
        return "other"
    u = name.upper().strip()
    for grp, lst in (("chinese",CHINESE),("japanese",JAPANESE),("korean",KOREAN),
                     ("us",US),("eu",EU)):
        for b in lst:
            if b in u:
                return grp
    return "other"

out = {}

# ---- TH: latest month overall & latest month with maker data ----
r = c.execute("SELECT MAX(year*100+month) m FROM sales_monthly WHERE country='TH'").fetchone()["m"]
out["latest_overall"] = {"TH": {"year": r//100, "month": r%100}}
r = c.execute("SELECT MAX(year*100+month) m FROM sales_monthly WHERE country='VN'").fetchone()["m"]
out["latest_overall"]["VN"] = {"year": r//100, "month": r%100}
r = c.execute("SELECT MAX(year*100+month) m FROM sales_monthly WHERE country='TH' AND level='maker'").fetchone()["m"]
TH_MK = {"year": r//100, "month": r%100}
out["th_latest_maker_month"] = f"{TH_MK['year']}-{TH_MK['month']:02d}"

# ---- TH monthly total trend (level=total, FTI) ----
out["th_total_trend"] = [{"period": f"{r['year']}-{r['month']:02d}",
                          "units": r["units"], "ytd": r["ytd"]}
    for r in c.execute("""SELECT year, month, SUM(units) units, SUM(units_ytd) ytd
        FROM sales_monthly WHERE country='TH' AND level='total'
        GROUP BY year, month ORDER BY year, month""")]

# ---- TH powertrain mix latest overall month ----
ly = out["latest_overall"]["TH"]
th_pt = [{"category": r["category"], "units": r["units"]} for r in c.execute("""
    SELECT category, SUM(units) units FROM sales_monthly
    WHERE country='TH' AND level='powertrain' AND year=? AND month=?
    GROUP BY category ORDER BY units DESC""", (ly["year"], ly["month"]))]
out["th_powertrain_latest"] = {"period": f"{ly['year']}-{ly['month']:02d}", "rows": th_pt}
pt_total = sum(x["units"] for x in th_pt) or 1
elec = sum(x["units"] for x in th_pt if x["category"] in ("BEV","HEV","PHEV","REEV"))
out["th_powertrain_latest"]["electrified_pct"] = round(100*elec/pt_total, 1)

# ---- TH maker ranking + origin share (use latest month WITH maker data) ----
th_makers = []
for r in c.execute("""
    SELECT maker, SUM(units) units FROM sales_monthly
    WHERE country='TH' AND level='maker' AND year=? AND month=?
    GROUP BY maker ORDER BY units DESC LIMIT 20""", (TH_MK["year"], TH_MK["month"])):
    th_makers.append({"maker": r["maker"], "units": r["units"], "origin": origin(r["maker"])})
out["th_top_makers"] = {"period": out["th_latest_maker_month"], "rows": th_makers}
tot = sum(m["units"] for m in th_makers) or 1
orig_share = {}
for m in th_makers:
    orig_share[m["origin"]] = orig_share.get(m["origin"], 0) + m["units"]
out["th_origin_share"] = {k: {"units": v, "pct": round(100*v/tot,1)}
                          for k, v in sorted(orig_share.items(), key=lambda x:-x[1])}

# ---- TH top models (latest maker month) ----
th_models = []
for r in c.execute("""
    SELECT maker, model, SUM(units) units FROM sales_monthly
    WHERE country='TH' AND level='model' AND year=? AND month=?
    GROUP BY maker, model ORDER BY units DESC LIMIT 20""", (TH_MK["year"], TH_MK["month"])):
    th_models.append({"maker": r["maker"], "model": r["model"], "units": r["units"]})
out["th_top_models"] = {"period": out["th_latest_maker_month"], "rows": th_models}

# ---- TH coverage ----
out["th_sales_coverage"] = [dict(r) for r in c.execute("""
    SELECT source, COUNT(*) rows, MIN(year*100+month) first, MAX(year*100+month) last,
           COUNT(DISTINCT year*100+month) months
    FROM sales_monthly WHERE country='TH' GROUP BY source""")]

# ---- TH listings stats ----
lst = c.execute("""SELECT COUNT(*) n, COUNT(DISTINCT maker) makers, COUNT(DISTINCT province) prov,
    MIN(price_thb) pmin, MAX(price_thb) pmax,
    SUM(CASE WHEN condition='new' THEN 1 ELSE 0 END) new_c,
    SUM(CASE WHEN condition='used' THEN 1 ELSE 0 END) used_c,
    MIN(year) ymin, MAX(year) ymax FROM th_car_listings""").fetchone()
prices = [r[0] for r in c.execute("SELECT price_thb FROM th_car_listings WHERE price_thb>0")]
out["th_listings"] = {"count": lst["n"], "makers": lst["makers"], "provinces": lst["prov"],
    "price_min": lst["pmin"], "price_max": lst["pmax"],
    "price_median": int(statistics.median(prices)) if prices else None,
    "price_mean": int(statistics.mean(prices)) if prices else None,
    "new": lst["new_c"], "used": lst["used_c"], "year_min": lst["ymin"], "year_max": lst["ymax"]}
out["th_listing_brands"] = [dict(r) for r in c.execute("""
    SELECT maker, COUNT(*) n, ROUND(AVG(price_thb),0) avg_price FROM th_car_listings
    GROUP BY maker ORDER BY n DESC LIMIT 15""")]
out["th_provinces"] = [dict(r) for r in c.execute("""
    SELECT province, COUNT(*) n FROM th_car_listings GROUP BY province ORDER BY n DESC LIMIT 12""")]
out["th_fuel"] = [dict(r) for r in c.execute("""
    SELECT COALESCE(NULLIF(fuel_type,''),'(未知)') fuel_type, COUNT(*) n FROM th_car_listings
    GROUP BY fuel_type ORDER BY n DESC LIMIT 6""")]

# ---- VN monthly national total (maker subtotal, region=ALL) ----
out["vn_total_trend"] = [{"period": f"{r['year']}-{r['month']:02d}", "units": r["units"]}
    for r in c.execute("""SELECT year, month, SUM(units) units FROM sales_monthly
        WHERE country='VN' AND level='maker' AND is_subtotal=1 AND region='ALL'
        GROUP BY year, month ORDER BY year, month""")]

# ---- VN top makers latest (region=ALL) ----
vy = out["latest_overall"]["VN"]
vn_makers = []
for r in c.execute("""
    SELECT maker, SUM(units) units FROM sales_monthly
    WHERE country='VN' AND level='maker' AND is_subtotal=1 AND region='ALL'
      AND year=? AND month=? GROUP BY maker ORDER BY units DESC LIMIT 15""", (vy["year"], vy["month"])):
    vn_makers.append({"maker": r["maker"], "units": r["units"]})
out["vn_top_makers"] = {"period": f"{vy['year']}-{vy['month']:02d}", "rows": vn_makers}

# ---- VN top models latest (region=ALL) ----
vn_models = []
for r in c.execute("""
    SELECT maker, model, SUM(units) units FROM sales_monthly
    WHERE country='VN' AND level='model' AND region='ALL' AND year=? AND month=?
    GROUP BY maker, model ORDER BY units DESC LIMIT 15""", (vy["year"], vy["month"])):
    vn_models.append({"maker": r["maker"], "model": r["model"], "units": r["units"]})
out["vn_top_models"] = {"period": f"{vy['year']}-{vy['month']:02d}", "rows": vn_models}

# ---- VN regional split latest month ----
vn_reg = []
for r in c.execute("""
    SELECT region, SUM(units) units FROM sales_monthly
    WHERE country='VN' AND level='maker' AND is_subtotal=1 AND year=? AND month=?
    GROUP BY region ORDER BY units DESC""", (vy["year"], vy["month"])):
    vn_reg.append({"region": r["region"], "units": r["units"]})
out["vn_region_latest"] = {"period": f"{vy['year']}-{vy['month']:02d}", "rows": vn_reg}

# ---- VN regional trend (South vs North vs Central), national via ALL ----
vn_reg_trend = []
for r in c.execute("""
    SELECT year, month, region, SUM(units) units FROM sales_monthly
    WHERE country='VN' AND level='maker' AND is_subtotal=1
    GROUP BY year, month, region ORDER BY year, month, region"""):
    vn_reg_trend.append({"period": f"{r['year']}-{r['month']:02d}",
                         "region": r["region"], "units": r["units"]})
out["vn_region_trend"] = vn_reg_trend

# ---- VN coverage ----
out["vn_sales_coverage"] = [dict(r) for r in c.execute("""
    SELECT source, COUNT(*) rows, MIN(year*100+month) first, MAX(year*100+month) last,
           COUNT(DISTINCT year*100+month) months
    FROM sales_monthly WHERE country='VN' GROUP BY source""")]

# ---- cross-country brand overlap (maker level) ----
th_brands = set(r[0] for r in c.execute(
    "SELECT DISTINCT maker FROM sales_monthly WHERE country='TH' AND level='maker'"))
vn_brands = set(r[0] for r in c.execute(
    "SELECT DISTINCT maker FROM sales_monthly WHERE country='VN' AND level='maker'"))
out["brand_overlap"] = {"th_count": len(th_brands), "vn_count": len(vn_brands),
                        "both": sorted(th_brands & vn_brands)}

# ---- data quality ----
out["row_counts"] = {r["tbl"]: r["n"] for r in c.execute("""
    SELECT 'sales_monthly' tbl, COUNT(*) n FROM sales_monthly
    UNION ALL SELECT 'th_car_listings', COUNT(*) FROM th_car_listings
    UNION ALL SELECT 'news_articles', COUNT(*) FROM news_articles
    UNION ALL SELECT 'data_quality_flags', COUNT(*) FROM data_quality_flags""")}
prov = {}
for tbl, cols in (("sales_monthly","source,source_url,source_name,source_site"),
                  ("th_car_listings","source,source_url,source_name,source_site"),
                  ("news_articles","source,source_site")):
    nulls = {}
    for col in cols.split(","):
        q = c.execute(f"SELECT COUNT(*) n FROM {tbl} WHERE {col} IS NULL OR {col}=''").fetchone()["n"]
        nulls[col] = q
    prov[tbl] = nulls
out["provenance_nulls"] = prov
out["news_counts"] = {f"{r['country']}/{r['source']}": r["n"] for r in c.execute(
    "SELECT country, source, COUNT(*) n FROM news_articles GROUP BY country, source")}

print(json.dumps(out, ensure_ascii=False, indent=1))
