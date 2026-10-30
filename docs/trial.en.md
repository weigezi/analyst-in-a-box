# Trial guide

[中文](trial.zh.md)

Thank you for trying analyst-in-a-box on your own business. The project has only been tested on its own demo
data, so your verdict is the real test. It takes about an hour on the first day and a few minutes each time after.

## 1. What you need

- An AI tool that loads Agent Skills (a folder with a `SKILL.md`), with a terminal it can use.
- Python 3.10 or later; the tool will install `pandas`, `pyyaml` and `openpyxl` if they are missing.
- One table of your own: orders, invoices or daily totals, with a date column and at least one money column.
  CSV, Excel, SQLite or DuckDB. It never leaves your computer.
- A question you already know the answer to is ideal: a past week whose cause you know.

## 2. First session

1. Copy `skills/analyst-in-a-box/` into your tool's skills folder.
2. Ask it, in your own words, something like: "Here is our order table (path). Why did revenue fall last week?"
3. It will ask what each column is. Answer honestly; say "not a metric" for anything that is not.
4. Read the first report it gives you.

## 3. How to judge the first answer

| Question | Yes / no |
|---|---|
| Are the numbers right? (Check one or two against your own dashboard.) | |
| Does it tell you at least one thing you did not already know? | |
| Where it says "spread, no single point", is that fair? | |
| Where it says "reason waiting for you", is that really something only you know? | |

## 4. The following week

Use it on real questions. Whenever it is wrong, or misses something you know, tell it plainly, as you would tell a
new analyst. It will record what you said. After a few corrections, judge again:

| Question | Yes / no |
|---|---|
| Has it repeated a mistake you already corrected? | |
| Are its answers now close to what your own analysts would write? | |
| Did it ever state a guess as a fact? | |

## 5. What to send back

Your two tables above, and anything that surprised you. If you are willing, also the files
`corrections.jsonl` and `runs/*/record.json` from your workspace folder: they hold your corrections and what each
run computed, **not your data**. Check them first, and leave out anything you would not share.

## 6. If something goes wrong

- It asks about a column again after you answered: that is a bug; please note the column.
- A report says "pre-delivery checks failed": it found its own numbers inconsistent and refused to answer.
  Send the `record.json` of that run.
- It guesses what a column means without asking: that breaks its first rule; please tell us exactly what it said.
