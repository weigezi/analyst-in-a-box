# Intake: from several tables and documents to a workspace

[中文](intake.zh.md)

`init <folder or files> --workspace W` reads every table, proposes what each one is and how they fit, and writes
`draft.json` with the questions. `confirm` turns only the answered questions into the workspace. Code:
`scripts/aib/intake.py`.

## 1. What is inferred, and from what

Only from the shape of the data, never from a column's name:

| Inference | Shape it is read from | Becomes |
|---|---|---|
| main table | has a date, numbers, and the most rows | the measures (after the user names each number's meaning) |
| lookup table | no date; a column with one row per value (text or whole numbers) | attributes joined to the main table by that key; they can be dimensions, and "belongs to" is found as for one table |
| link | every value of a column is found among another column's values | asked with the matching rows and the coverage |
| event records | two dates per row, the first never after the second, plus words or groups | one world event per row: source "system record", status "to confirm" |
| holiday calendar | the same shape, with no column that names a group in the data | the calendar outside source (`name`, `start`, `end`) |
| daily series | one row per date, or per date and one group | outside data (weather, a market index) or more business data (visits); grouped whole counts that link to the main table are suggested as business data, measurements as outside data |

Coverage is the share of the left column's rows whose value is found on the right. A pair below 50% is not
asked about. Between 50% and 95% it is asked with the suggested answer "no", and from 95% with "yes". Nothing is
joined without an explicit "yes": an unanswered link is not a link.

## 2. The questions

Every inference is one question with its suggested answer and the evidence (row counts, coverage, which
column is never after which). Ask them as multiple choice, a few at a time; show the suggestion as a suggestion.

| Question id | Asks |
|---|---|
| `main_table` | which table is the one to analyse |
| `kind:<table>` | lookup / business / events / calendar / series / market / ignore |
| `link:<table>.<col>><table>.<col>` | are these the same thing (with coverage) |
| `event_text:<table>`, `event_kind:<table>` | which column says what happened; internal or external |
| `role:<table>.<col>` | what a number in a second table is (`visits` makes conversion = orders / visits) |
| `market_compares:<table>` | which main-table number a market index compares with |
| the single-table questions | date column, roles, order id, dimensions, belongs to, closing days, single-point share |

Questions about a joined attribute (a list price, a product name) appear because the suggested links were
assumed. If the user says "no" to a link, those questions no longer matter; `confirm` ignores them.

## 3. Documents

The script does not read prose: a rule that pulls causes out of sentences would be guessing. You (the AI tool)
read the document and propose candidates:

```yaml
doc: docs/weekly_report.md
items:
  - type: event                       # or mechanism
    quote: "<the sentence, copied exactly>"
    entry: {kind: internal, start: 2026-10-12, entities: ["channel:marketplace"],
            what: {zh: "...", en: "..."}}
```

`propose --workspace W --file proposals.yaml` (or `--doc D --type event --quote Q --json E` for one). Each
candidate is refused when:

- the quote is not in the document. Whitespace, line breaks and Markdown emphasis are ignored; every other
  character must match.
- the quote is shorter than 8 characters, which proves nothing about where a claim came from;
- an entity is unknown, or an event has no start date, or a mechanism has no claim.

Accepted ones are stored with `source: {kind: document, ref, quote}` and `status: proposed`, and logged in
`proposals.jsonl`. A proposed record that fits the change makes a slot a hypothesis: "possible cause, from a
document, to confirm", with the sentence. It is not counted as explained until the user confirms it
(`correct` with `confirm`).

## 4. Where everything came from

`formation --workspace W` lists every part of the workspace under four headings: from the data (and confirmed
in a question), the user's answers, from documents (to confirm), and what only a person can add. That last
heading covers mechanisms beyond the documents, actions and owners, a confirmed cut order, comparisons,
price-volume-mix, and readable names for codes. `demo/intake/` runs the whole intake on the demo shop's tables
and compares the result with the hand-written workspace.
