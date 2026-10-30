"""Turn the public UCI "Online Retail" file (or its two-year "Online Retail II") into one row per invoice.

    curl -L -o demo/public/raw/online_retail.xlsx "https://archive.ics.uci.edu/ml/machine-learning-databases/00352/Online%20Retail.xlsx"
    uv run python demo/public/prepare.py

Source and licence: see README.md in this folder (CC BY 4.0, attribution required).
Every rule below comes from the dataset's own documentation, cited where it is used.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pandas as pd

HERE = Path(__file__).parent
RAW = HERE / "raw" / "online_retail_II.xlsx"       # UCI 502, Online Retail II (2009-12 .. 2011-12)
RAW_I = HERE / "raw" / "online_retail.xlsx"        # UCI 352, Online Retail (2010-12 .. 2011-12), same company
OUT = HERE / "data" / "invoices.csv.gz"

# Column names as documented on the UCI page, and as they appear in the file's header row.
COLUMNS = {"InvoiceNo": "invoice", "Invoice": "invoice", "StockCode": "stock_code", "Description": "description",
           "Quantity": "quantity", "InvoiceDate": "invoice_date", "UnitPrice": "price", "Price": "price",
           "CustomerID": "customer_id", "Customer ID": "customer_id", "Country": "country"}
TOP_COUNTRIES = 8


def read_lines(path: Path) -> pd.DataFrame:
    sheets = pd.read_excel(path, sheet_name=None, dtype={"Invoice": str, "InvoiceNo": str, "StockCode": str})
    frames = []
    for name, df in sheets.items():
        unknown = [c for c in df.columns if c not in COLUMNS]
        if unknown:
            raise SystemExit(f"sheet {name}: unexpected columns {unknown}; check the UCI variable table before mapping them")
        df = df.rename(columns=COLUMNS)
        df["invoice_date"] = pd.to_datetime(df["invoice_date"])
        frames.append(df)
    # Online Retail II has two sheets that overlap on 2010-12-01..09 (the same rows appear in both).
    # Keep the overlap once, and prove it is identical rather than dropping duplicates blindly:
    # a plain drop_duplicates would also remove lines that genuinely repeat within one invoice.
    out = frames[0]
    for nxt in frames[1:]:
        last = out["invoice_date"].dt.normalize().max()
        overlap = nxt[nxt["invoice_date"].dt.normalize() <= last]
        mine = out[out["invoice_date"].dt.normalize() >= overlap["invoice_date"].dt.normalize().min()] if len(overlap) else overlap
        key = lambda d: d.astype(str).sort_values(list(d.columns)).reset_index(drop=True)  # noqa: E731
        if len(overlap) and not key(overlap[COLS]).equals(key(mine[COLS])):
            raise SystemExit("the sheets overlap but the overlapping rows differ; inspect before merging")
        print(f"sheet overlap: {len(overlap):,} rows on or before {last.date()}, identical in both sheets; kept once")
        out = pd.concat([out, nxt[nxt["invoice_date"].dt.normalize() > last]], ignore_index=True)
    return out


COLS = ["invoice", "stock_code", "description", "quantity", "invoice_date", "price", "customer_id", "country"]

# Citations as given on each dataset's UCI page (checked 2026-10-30); both CC BY 4.0, same creator and company.
SOURCES = {
    RAW.name: {"title": "Online Retail II", "uci_id": 502, "citation": "Chen, D. (2012). Online Retail II [Dataset]. UCI Machine Learning Repository.",
               "doi": "https://doi.org/10.24432/C5CG6D", "licence": "CC BY 4.0", "page": "https://archive.ics.uci.edu/dataset/502/online+retail+ii"},
    RAW_I.name: {"title": "Online Retail", "uci_id": 352, "citation": "Chen, D. (2015). Online Retail [Dataset]. UCI Machine Learning Repository.",
                 "doi": "https://doi.org/10.24432/C5BW33", "licence": "CC BY 4.0", "page": "https://archive.ics.uci.edu/dataset/352/online+retail"},
}


def main():
    raw = None
    for p in (RAW, RAW_I):
        if p.exists() and not zipfile.is_zipfile(p):
            print(f"skipping {p.name}: not a complete xlsx (an interrupted download?)")
        elif p.exists():
            raw = p
            break
    if raw is None:
        raise SystemExit(f"put {RAW.name} (or {RAW_I.name}) in {RAW.parent}; see README.md")
    lines = read_lines(raw)
    n_all = len(lines)

    # UCI: "If this code starts with the letter 'c', it indicates a cancellation."
    lines = lines[~lines["invoice"].str.upper().str.startswith("C")]
    # Sales only: non-positive quantities or prices are adjustments, not sales.
    lines = lines[(lines["quantity"] > 0) & (lines["price"] > 0)]
    lines["revenue"] = lines["quantity"] * lines["price"]

    inv = lines.groupby("invoice").agg(
        invoice_date=("invoice_date", "min"), country=("country", "first"), customer_id=("customer_id", "first"),
        revenue=("revenue", "sum"), items=("quantity", "sum"), lines=("stock_code", "count")).reset_index()
    inv["invoice_date"] = inv["invoice_date"].dt.strftime("%Y-%m-%d")
    inv["revenue"] = inv["revenue"].round(2)

    # UCI: "a UK-based and registered non-store online retail" company.
    inv["market"] = inv["country"].map(lambda c: "domestic" if c == "United Kingdom" else "international")
    top = inv.groupby("country")["revenue"].sum().nlargest(TOP_COUNTRIES).index
    inv["country_group"] = inv["country"].where(inv["country"].isin(top), "Other")
    # First invoice of a customer inside this data; customers who bought before December 2009 cannot be told apart.
    first = inv.dropna(subset=["customer_id"]).sort_values(["invoice_date", "invoice"]).groupby("customer_id")["invoice"].first()
    inv["customer_status"] = "returning"
    inv.loc[inv["invoice"].isin(first.values), "customer_status"] = "first_seen"
    inv.loc[inv["customer_id"].isna(), "customer_status"] = "guest"
    inv["customer_id"] = inv["customer_id"].astype("Int64")

    OUT.parent.mkdir(exist_ok=True, parents=True)
    inv.sort_values(["invoice_date", "invoice"]).to_csv(OUT, index=False, compression={"method": "gzip", "mtime": 0})
    meta = {**SOURCES[raw.name], "raw_file": raw.name, "raw_lines": n_all, "sales_lines": len(lines), "invoices": len(inv),
            "first_day": inv["invoice_date"].min(), "last_day": inv["invoice_date"].max()}
    (OUT.parent / "source.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{raw.name}: lines {n_all:,}; sales lines kept {len(lines):,}; invoices {len(inv):,}; "
          f"{inv['invoice_date'].min()} .. {inv['invoice_date'].max()} -> {OUT}")


if __name__ == "__main__":
    main()
