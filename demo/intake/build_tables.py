"""Split the demo shop's data into the tables a real shop's systems would export.

    uv run python demo/intake/build_tables.py

Reads demo/store/workspace (never writes there) and writes demo/intake/tables/:
  orders.csv.gz       one row per order; no category or region, only the product code and the city
  products.csv        product code -> category, name, list price
  cities.csv          city -> region
  traffic.csv.gz      visits per day and channel
  promotions.csv      the campaign calendar (start, end, what, who it targets)
  price_changes.csv   the price-change log
  holidays.csv        the gifting calendar
  weather.csv         rainfall per day and region
  market.csv          the online-gifting market index

The shop and every number are the same fictional "Bloom & Basket"; only the shape of the data changes, so the
skill has to put the tables back together itself. Same input, same output, every time.
"""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import pandas as pd

HERE = Path(__file__).parent
STORE = HERE.parent / "store" / "workspace"
OUT = HERE / "tables"

# Three products per category; which product an order was is fixed by its order id, so it never changes.
PRODUCTS = {
    "bouquet": ["BQ-ROSE", "BQ-LILY", "BQ-MIX"],
    "fruit_basket": ["FB-SMALL", "FB-FAMILY", "FB-DELUXE"],
    "plant": ["PL-SUCC", "PL-MONST", "PL-ORCH"],
    "gift_box": ["GB-TEA", "GB-SWEET", "GB-PREM"],
}
NAMES = {"BQ-ROSE": "红玫瑰花束", "BQ-LILY": "百合花束", "BQ-MIX": "混搭花束", "FB-SMALL": "小果篮", "FB-FAMILY": "家庭果篮",
         "FB-DELUXE": "精选果篮", "PL-SUCC": "多肉组合", "PL-MONST": "龟背竹", "PL-ORCH": "蝴蝶兰", "GB-TEA": "茶礼盒",
         "GB-SWEET": "糕点礼盒", "GB-PREM": "臻选礼盒"}


def _pick(order_id: str, options: list) -> str:
    return options[int(hashlib.sha256(order_id.encode()).hexdigest(), 16) % len(options)]


def main(out: Path = OUT):
    out.mkdir(parents=True, exist_ok=True)
    o = pd.read_csv(STORE / "data" / "orders.csv.gz")
    o["sku"] = [_pick(i, PRODUCTS[c]) for i, c in zip(o["order_id"], o["category"])]
    orders = o[["order_id", "order_date", "sku", "channel", "city", "delivery", "customer_type", "revenue", "gross_profit"]]
    orders.to_csv(out / "orders.csv.gz", index=False, compression={"method": "gzip", "mtime": 0})

    base = o[o["order_date"] < "2026-01-01"].groupby("sku")["revenue"].mean().round(0)
    products = pd.DataFrame([{"sku": s, "category": c, "name": NAMES[s], "list_price": float(base[s])}
                             for c, skus in PRODUCTS.items() for s in skus])
    products.to_csv(out / "products.csv", index=False)
    o[["city", "region"]].drop_duplicates().sort_values("city").to_csv(out / "cities.csv", index=False)

    t = pd.read_csv(STORE / "data" / "traffic.csv.gz")
    t.to_csv(out / "traffic.csv.gz", index=False, compression={"method": "gzip", "mtime": 0})

    # The campaign calendar holds what marketing ran. The October card offer is what changed new customers' mix;
    # the Valentine's push is the bouquet surge the shop plans every year.
    pd.DataFrame([
        {"start": "2026-02-07", "end": "2026-02-14", "campaign": "情人节花束主推", "category": "bouquet", "customer_type": ""},
        {"start": "2026-10-01", "end": "2026-10-31", "campaign": "新客买果篮送贺卡", "category": "fruit_basket", "customer_type": "new"},
    ]).to_csv(out / "promotions.csv", index=False)
    pd.DataFrame([
        {"start": "2026-06-01", "end": "2026-06-30", "category": "gift_box", "change": 0.15, "reason": "供应商涨价，礼盒售价上调 15%"},
    ]).to_csv(out / "price_changes.csv", index=False)

    for name, target in (("calendar.csv", "holidays.csv"), ("weather.csv", "weather.csv"), ("market.csv", "market.csv")):
        shutil.copyfile(STORE / "external" / name, out / target)
    print(f"orders {len(orders):,}  products {len(products)}  tables written to {out}")


if __name__ == "__main__":
    main()
