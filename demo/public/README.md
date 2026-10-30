# Public dataset: UCI Online Retail

[中文](README.zh.md)

The fictional shop proves the skill finds causes that are known. This dataset proves something different:
real data, never seen by the project, loads through the getting-started flow and produces a checked report.
It has no answer key, so it cannot prove the answer is right.

## Source and licence

Used here (`data/source.json` records which file the derived data came from):

Chen, D. (2015). Online Retail [Dataset]. UCI Machine Learning Repository. https://doi.org/10.24432/C5BW33

Licence: Creative Commons Attribution 4.0 International (CC BY 4.0), checked on the
[dataset page](https://archive.ics.uci.edu/dataset/352/online+retail) on 2026-10-30. It allows sharing and
adapting with attribution; this file is the attribution, and the changes are listed below.

The data: 541,909 transaction lines of a UK-based online retailer selling mainly gift-ware, many of whose
customers are wholesalers, from 2010-12-01 to 2011-12-09. After the steps below: 19,960 invoices.

The same company's two-year version, [Online Retail II](https://archive.ics.uci.edu/dataset/502/online+retail+ii)
(Chen, D. (2012), https://doi.org/10.24432/C5CG6D, also CC BY 4.0, 2009-12-01 to 2011-12-09), works with the
same script and would allow year-on-year comparison. It was not used because its 45 MB download from UCI broke
off at about 26 MB on each of three attempts on 2026-10-30, and the server does not resume. With one year of
data, the first run compares a week with the week before, not with the same week a year earlier.

The derived file `data/invoices.csv.gz` (277 KB) is kept in this repository, so the tests and the demo site run
without downloading anything; the raw file is not (`raw/` is ignored).

## What was changed

`prepare.py` turns the original file into one row per invoice (`data/invoices.csv.gz`):

| Step | Rule | Where the rule comes from |
|---|---|---|
| merge the two sheets (Online Retail II only) | the sheets overlap on 2010-12-01..09; those days are kept once, after checking the rows are identical in both sheets (the script stops if they are not) | [Datapopcorn](https://datapopcorn.ai/blog/total-sales-four-answers) reports 22,523 rows in both sheets, so 1,067,371 on the dataset page counts them twice; `prepare.py` prints the overlap it actually finds |
| drop cancellations | invoice numbers starting with "C" | the dataset's variable description |
| keep sales only | quantity and unit price both above zero | non-positive rows are adjustments, not sales |
| line revenue | quantity × unit price | the variable description |
| one row per invoice | revenue, items and lines summed | — |
| `market` | `domestic` if the country is the United Kingdom, else `international` | "a UK-based and registered non-store online retail" company |
| `country_group` | the 8 countries with the most revenue, the rest as `Other` | presentation only |
| `customer_status` | `first_seen` for a customer's first invoice in the data, `returning` after, `guest` without a customer id | the data; customers who bought before the data's first day cannot be told apart |

To rebuild from the raw file:

```bash
curl -L -o demo/public/raw/online_retail.xlsx "https://archive.ics.uci.edu/ml/machine-learning-databases/00352/Online%20Retail.xlsx"
stat -f %z demo/public/raw/online_retail.xlsx       # 23715344 when complete (Linux: stat -c %s)
uv run python demo/public/prepare.py
```

For the two-year version, download `00502/online_retail_II.xlsx` from the same server into `raw/` instead
(45,622,278 bytes when complete); `prepare.py` prefers it when it is there and complete. The server does not
resume interrupted transfers; if the size is short, download again.

## How the skill is run on it

`answers.yaml` holds the answers to the getting-started questions, as a user would give them; the meaning of
each column comes from the dataset's variable description, not from its name. `tests/test_public.py` and the
demo site run `init` → `confirm` → the first run, exactly as a new user would.
