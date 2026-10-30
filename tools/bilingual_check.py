"""Every document exists in Chinese and English, section for section.

    uv run python tools/bilingual_check.py

Pairs: X.md with X.zh.md, and X.en.md with X.zh.md. For each pair the sequence of heading levels must be the
same, and each file must link to the other. Exit code 1 on any mismatch or missing partner.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
SKIP = {".git", ".venv", "node_modules", "dist", "raw", "runs", "docs_generated", ".pytest_cache", "__pycache__"}
SINGLE_LANGUAGE_OK = {"skills/analyst-in-a-box/scripts/requirements.txt"}


def headings(text: str) -> list[int]:
    out, fence = [], False
    for line in text.splitlines():
        if line.startswith("```"):
            fence = not fence
        elif not fence:
            m = re.match(r"^(#{1,6}) ", line)
            if m:
                out.append(len(m.group(1)))
    return out


def pairs():
    seen = set()
    for zh in ROOT.rglob("*.zh.md"):
        if set(zh.relative_to(ROOT).parts) & SKIP:
            continue
        stem = zh.name[: -len(".zh.md")]
        en = next((p for p in (zh.with_name(stem + ".md"), zh.with_name(stem + ".en.md")) if p.exists()), None)
        seen.add(zh)
        if en:
            seen.add(en)
        yield zh, en
    for md in ROOT.rglob("*.md"):
        rel = md.relative_to(ROOT)
        if md in seen or set(rel.parts) & SKIP or md.name.endswith(".zh.md"):
            continue
        if "workspace" in rel.parts and "docs" in rel.parts:
            continue
        yield None, md


def main():
    problems, ok = [], 0
    for zh, en in pairs():
        if zh is None:
            problems.append(f"no Chinese version: {en.relative_to(ROOT)}")
            continue
        if en is None:
            problems.append(f"no English version: {zh.relative_to(ROOT)}")
            continue
        a, b = zh.read_text(encoding="utf-8"), en.read_text(encoding="utf-8")
        if headings(a) != headings(b):
            problems.append(f"sections differ: {zh.relative_to(ROOT)} {headings(a)} vs {en.relative_to(ROOT)} {headings(b)}")
        if en.name not in a:
            problems.append(f"{zh.relative_to(ROOT)} does not link to {en.name}")
        if zh.name not in b:
            problems.append(f"{en.relative_to(ROOT)} does not link to {zh.name}")
        ok += 1
    print(f"{ok} pairs checked; {len(problems)} problems")
    for p in problems:
        print("  " + p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
