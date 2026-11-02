# Contributing

[中文](CONTRIBUTING.zh.md)

Thanks for looking at analyst-in-a-box. The most useful contribution right now is **a report from trying it on your
own data**: follow the [trial guide](docs/trial.en.md) and open an issue with what it got right, what it got wrong and
what you had to correct.

## Code and documents

- Run the tests with `uv run --frozen pytest -q`. `--frozen` keeps `uv.lock` untouched.
- Every document exists in English and Chinese, section for section: `uv run --frozen python tools/bilingual_check.py`.
- Every number the engine reports must come from a script, and every breakdown must add up to the total change. A new
  method needs a hand-computed test next to it.
- Business knowledge (a cause, a mechanism, an owner) is written with a source and a status. Do not add a record
  without one; the workspace validator refuses it.
- Changes to the demo site: build with `uv run --frozen python site/build.py`, then `node tools/browser-check/check.mjs`
  and `node tools/design-check/run.mjs` must pass.

## Before you open a pull request

State what question the change answers, what you ran, and what you did not check. Small, separate changes are easier
to review than one large one.
