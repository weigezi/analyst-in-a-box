# Purpose and design: read this before changing anything

[中文](AGENTS.zh.md)

This page is for anyone working on this repository, human or AI. It states what the project is for and how it is built. It is short on purpose. Fixing one module is easy to do while forgetting why the module exists; check your change against this page first.

## The promise

**Turn the few tables you have into an AI analyst that answers questions, in one go.** It works like hiring an experienced business analyst: you hand over your tables, answer a few multiple-choice questions, and get an explanation of why a number moved and who should do what next.

The question it answers: **"Why did this number move, and who should do what next?"** Business performance analysis only. A/B tests are out of scope.

## How we know it works

A stranger, someone who took no part in building it, can:

1. install it and import their own tables;
2. answer a few questions;
3. get a breakdown whose parts add up to the total change;
4. learn one thing they did not know;
5. correct it a few times and see the same kind of mistake stop coming back.

A senior analyst reading the result would nod, and the public site is worth looking at. If a change does not move one of these, ask why you are making it.

## Who does what

- **Scripts** compute every number. They read the shape of each table (dates, keys, amounts, how tables point at each other), never what a column is called.
- **The AI** explains, and proposes. It never makes up a number, a cause, or a column's meaning.
- **The person** only confirms: is what it recognised right? Is this cause real? Everything else runs in one go.

Every claim carries its source and a trust level: a fact (a person said it, a system recorded it, the data shows it), something to confirm (read from a document), or an AI inference. An AI inference is a draft until a person confirms it.

## Seven pillars of value

| # | Pillar | In one line |
|---|---|---|
| 1 | North-star breakdown | A metric tree: the headline number splits into the pieces it is made of |
| 2 | Across and down | Across: split by formula (revenue = orders x average order value). Down: cut by dimensions, scored to decide which to cut first |
| 3 | Contribution by script | Standard algorithms (additive, multiplicative, ratio, mix and rate); tests check the parts add up to the total |
| 4 | Business knowledge graph | Two parts: the **metric tree**, and the **business world description** (entities, relations, mechanisms, events, actions and owners) |
| 5 | Showing the graph | A readable, moving page where each node shows its source and how far to trust it |
| 6 | Easy data entry | A few raw tables and documents, a few multiple-choice questions, a workspace |
| 7 | Self-improvement | A correction is recorded with its source and becomes a regression check |

Public names: "business knowledge graph", with two parts, "metric tree" and "business world description".

## Rules that keep the numbers honest

1. First ask what one row of each table is. Count distinct keys, never rows.
2. Never add up a rate, a price, an age or a stock. Amounts add; averages are computed from amounts.
3. A join must not change the row count. A ratio across two tables is computed by summing each side to a shared grain, then dividing.
4. A distinct count cannot be added across segments.
5. A cause is a sourced record, not a restated result. "Where it moved" and "why it moved" are two separate layers.
6. Rules that guess from shape (thresholds, row counts) are suggestions the user confirms, and each threshold is a named parameter with its reason.
7. When a check fails, say so in plain words. A wrong number delivered quietly is worse than no answer.

## Working here

- Run tests with `uv run --frozen`. Plain `uv run` can rewrite `uv.lock`.
- Every document exists in Chinese and English, section for section: `uv run --frozen python tools/bilingual_check.py`.
- The repository is clean-room: no data, names or code from any employer. `tools/cleanroom_check.py` enforces it.
- Test data are public datasets and are never copied into the repository.
- Commit only the paths you changed. Record what you decided, and why, in [the decision log](docs/decisions.en.md).
