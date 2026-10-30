"""Build the fictional shop's data from planted.yaml. Same seed, same data, every time.

    uv run python demo/store/generate.py

Writes demo/store/workspace/data/*.csv.gz and demo/store/workspace/external/*.csv.
Every number below is a setting for this fictional shop, not a claim about any real business.
"""

from __future__ import annotations

import datetime as dt
import itertools
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

HERE = Path(__file__).parent
OUT = HERE / "workspace"

CHANNELS = {"app": 0.45, "web": 0.30, "marketplace": 0.25}
CATEGORIES = {"bouquet": (0.35, 260), "fruit_basket": (0.25, 120), "plant": (0.20, 150), "gift_box": (0.20, 320)}
REGIONS = {"north": 0.25, "east": 0.30, "south": 0.25, "west": 0.20}
CITIES = {"north": ["Beijing", "Tianjin"], "east": ["Shanghai", "Hangzhou"],
          "south": ["Guangzhou", "Shenzhen"], "west": ["Chengdu", "Chongqing"]}
DELIVERY = {"same_day": 0.5, "scheduled": 0.4, "pickup": 0.1}
CUSTOMERS = {"new": 0.3, "returning": 0.7}
COST_RATIO = {"bouquet": 0.45, "fruit_basket": 0.60, "plant": 0.40, "gift_box": 0.50}
MARKETPLACE_COMMISSION = 0.12
CONVERSION = {"app": 0.06, "web": 0.03, "marketplace": 0.05}
WEEKDAY = [0.90, 0.90, 0.95, 1.00, 1.15, 1.20, 1.05]
BASE_ORDERS_PER_DAY = 300
YEARLY_GROWTH = 1.08
PRICE_SIGMA = 0.20

# The shop's gifting seasons: (name, start, end, {category: multiplier}). Each window ends on (or spans) the
# public holiday; 2026 holiday dates follow the State Council notice of 2025-11-04.
HOLIDAYS = [
    ("spring_festival", "2025-01-28", "2025-02-04", {"gift_box": 1.6, "fruit_basket": 1.6}),
    ("valentines_day", "2025-02-10", "2025-02-14", {"bouquet": 3.0}),
    ("mothers_day", "2025-05-05", "2025-05-11", {"bouquet": 2.5, "plant": 1.5}),
    ("mid_autumn", "2025-09-30", "2025-10-06", {"fruit_basket": 2.0, "gift_box": 2.0}),
    ("national_day", "2025-10-01", "2025-10-08", {"*": 1.2}),
    ("spring_festival", "2026-02-15", "2026-02-23", {"gift_box": 1.6, "fruit_basket": 1.6}),
    ("valentines_day", "2026-02-10", "2026-02-14", {"bouquet": 3.0}),
    ("mothers_day", "2026-05-04", "2026-05-10", {"bouquet": 2.5, "plant": 1.5}),
    ("mid_autumn", "2026-09-19", "2026-09-25", {"fruit_basket": 2.0, "gift_box": 2.0}),
    ("national_day", "2026-10-01", "2026-10-07", {"*": 1.2}),
]
HOLIDAY_LABELS = {
    "spring_festival": ("春节送礼季", "Spring Festival gifting"), "valentines_day": ("情人节", "Valentine's Day"),
    "mothers_day": ("母亲节周", "Mother's Day week"), "mid_autumn": ("中秋送礼周", "Mid-Autumn gifting week"),
    "national_day": ("国庆", "National Day"),
}


def main(seed: int | None = None, out: Path = OUT):
    spec = yaml.safe_load((HERE / "planted.yaml").read_text(encoding="utf-8"))
    rng = np.random.default_rng(spec["seed"] if seed is None else seed)
    days = pd.date_range(spec["start"], spec["end"], freq="D")
    cells = list(itertools.product(CHANNELS, CATEGORIES, REGIONS, DELIVERY, CUSTOMERS))
    cell_df = pd.DataFrame(cells, columns=["channel", "category", "region", "delivery", "customer_type"])
    share = np.array([CHANNELS[a] * CATEGORIES[b][0] * REGIONS[c] * DELIVERY[d] * CUSTOMERS[e]
                      for a, b, c, d, e in cells])

    t = (days - days[0]).days.to_numpy()
    base = BASE_ORDERS_PER_DAY * YEARLY_GROWTH ** (t / 365) * np.array([WEEKDAY[d.weekday()] for d in days])
    lam = base[:, None] * share[None, :]
    price_mult = np.ones_like(lam)

    def mask(where):
        m = np.ones(len(cells), dtype=bool)
        for col, val in (where or {}).items():
            m &= cell_df[col].to_numpy() == val
        return m

    def day_mask(start=None, end=None):
        m = np.ones(len(days), dtype=bool)
        if start:
            m &= days >= pd.Timestamp(start)
        if end:
            m &= days <= pd.Timestamp(end)
        return m

    for _, a, b, mult in HOLIDAYS:
        dm = day_mask(a, b)
        for cat, k in mult.items():
            cm = np.ones(len(cells), dtype=bool) if cat == "*" else mask({"category": cat})
            lam[np.ix_(dm, cm)] *= k

    for eff in spec["effects"]:
        dm = day_mask(eff.get("start"), eff.get("end"))
        if "orders_multiplier" in eff:
            lam[np.ix_(dm, mask(eff["where"]))] *= eff["orders_multiplier"]
        if "price_multiplier" in eff:
            price_mult[np.ix_(dm, mask(eff.get("price_where", eff["where"])))] *= eff["price_multiplier"]

    counts = rng.poisson(lam)
    di, ci = np.nonzero(counts)
    reps = counts[di, ci]
    di, ci = np.repeat(di, reps), np.repeat(ci, reps)
    n = len(di)

    orders = cell_df.iloc[ci].reset_index(drop=True)
    orders.insert(0, "order_date", days[di].strftime("%Y-%m-%d"))
    city_pick = rng.random(n) < 0.6
    orders.insert(4, "city", [CITIES[r][0 if p else 1] for r, p in zip(orders["region"], city_pick)])
    mean_price = orders["category"].map({k: v[1] for k, v in CATEGORIES.items()}).to_numpy()
    price = mean_price * price_mult[di, ci] * rng.lognormal(-PRICE_SIGMA ** 2 / 2, PRICE_SIGMA, n)
    orders["revenue"] = price.round(2)
    orders["cost"] = (orders["revenue"] * orders["category"].map(COST_RATIO)).round(2)
    orders["commission"] = np.where(orders["channel"] == "marketplace",
                                    (orders["revenue"] * MARKETPLACE_COMMISSION).round(2), 0.0)
    orders["gross_profit"] = (orders["revenue"] - orders["cost"] - orders["commission"]).round(2)
    orders = orders.sort_values(["order_date", "channel"], kind="stable").reset_index(drop=True)
    orders.insert(0, "order_id", [f"BB{i:07d}" for i in range(1, n + 1)])

    daily = orders.groupby(["order_date", "channel"]).size().unstack(fill_value=0)
    traffic = []
    for ch, cr in CONVERSION.items():
        visits = daily.get(ch, pd.Series(0, index=daily.index)) / cr * rng.lognormal(0, 0.05, len(daily))
        traffic.append(pd.DataFrame({"date": daily.index, "channel": ch, "visits": visits.round().astype(int)}))
    traffic = pd.concat(traffic).sort_values(["date", "channel"]).reset_index(drop=True)

    weather = []
    for r in REGIONS:
        rain = rng.gamma(0.6, 4.0, len(days))
        weather.append(pd.DataFrame({"date": days.strftime("%Y-%m-%d"), "region": r, "rainfall_mm": rain.round(1)}))
    weather = pd.concat(weather).reset_index(drop=True)
    for eff in spec["effects"]:
        if "rainfall_mm" in eff:
            hit = (weather["region"] == eff["rainfall_mm"]["region"]) & \
                  (weather["date"] >= str(eff["start"])) & (weather["date"] <= str(eff["end"]))
            weather.loc[hit, "rainfall_mm"] = eff["rainfall_mm"]["value"] + rng.normal(0, 8, hit.sum()).round(1)

    market_base = 120_000 * 1.12 ** (t / 365) * np.array([WEEKDAY[d.weekday()] for d in days])
    market = pd.DataFrame({"date": days.strftime("%Y-%m-%d"),
                           "market_sales": (market_base * rng.lognormal(0, 0.03, len(days))).round(0)})

    calendar = pd.DataFrame([{"name": h[0], "label_zh": HOLIDAY_LABELS[h[0]][0], "label_en": HOLIDAY_LABELS[h[0]][1],
                              "start": h[1], "end": h[2]} for h in HOLIDAYS])

    out = Path(out)
    (out / "data").mkdir(parents=True, exist_ok=True)
    (out / "external").mkdir(parents=True, exist_ok=True)
    orders.to_csv(out / "data" / "orders.csv.gz", index=False, compression={"method": "gzip", "mtime": 0})
    traffic.to_csv(out / "data" / "traffic.csv.gz", index=False, compression={"method": "gzip", "mtime": 0})
    weather.to_csv(out / "external" / "weather.csv", index=False)
    market.to_csv(out / "external" / "market.csv", index=False)
    calendar.to_csv(out / "external" / "calendar.csv", index=False)
    print(f"orders {len(orders):,}  traffic {len(traffic):,}  weather {len(weather):,}  market {len(market):,}")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, help="override the seed in planted.yaml (robustness checks)")
    ap.add_argument("--out", default=str(OUT), help="output workspace folder")
    a = ap.parse_args()
    main(a.seed, Path(a.out))
