"""Clean-room check: nothing from the earlier internal project may be in this repository.

    uv run python tools/cleanroom_check.py --denylist PATH [--compare DIR]

--denylist  a text file, one term per line (table names, people, internal links, company names). It is kept
            outside this repository on purpose: a list of internal names inside the repo would itself leak them.
--compare   a folder of the earlier project; every line of 40 characters or more that appears in both is reported.
Exit code 1 if anything is found.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
TEXT = {".py", ".md", ".yaml", ".yml", ".j2", ".html", ".js", ".mjs", ".css", ".sh", ".txt", ".sql", ".toml", ".json", ".csv"}
SKIP_DIRS = {".git", ".venv", "node_modules", "dist", "raw", "__pycache__", ".pytest_cache", "runs", "outputs", "_backup"}
MIN_LEN = 40
# Third-party licence texts must be shipped word for word, so any other project carrying the same licence
# shares their lines. They are still scanned for denylist terms, only left out of the overlap comparison.
LICENCE_TEXTS = {"ofl.txt", "license", "license.txt", "licence", "notice"}


def files(root: Path):
    for p in root.rglob("*"):
        if p.is_file() and p.suffix.lower() in TEXT and not (set(p.relative_to(root).parts) & SKIP_DIRS):
            if p.stat().st_size < 5_000_000:
                yield p


def norm(line: str) -> str:
    return re.sub(r"\s+", " ", line.strip()).lower()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--denylist", required=True)
    ap.add_argument("--compare")
    a = ap.parse_args(argv)
    terms = [t.strip() for t in Path(a.denylist).read_text(encoding="utf-8").splitlines() if t.strip() and not t.startswith("#")]
    pattern = re.compile("|".join(re.escape(t) for t in terms), re.IGNORECASE) if terms else None
    hits, overlap = [], []
    ours = list(files(ROOT))
    for p in ours:
        for i, line in enumerate(p.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
            if pattern and pattern.search(line):
                hits.append(f"{p.relative_to(ROOT)}:{i}: {pattern.search(line).group(0)}")
    if a.compare:
        theirs = set()
        for p in files(Path(a.compare)):
            for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
                n = norm(line)
                if len(n) >= MIN_LEN:
                    theirs.add(n)
        licences = [p for p in ours if p.name.lower() in LICENCE_TEXTS]
        for p in ours:
            if p in licences:
                continue
            for i, line in enumerate(p.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
                n = norm(line)
                if len(n) >= MIN_LEN and n in theirs:
                    overlap.append(f"{p.relative_to(ROOT)}:{i}: {line.strip()[:90]}")
    print(f"scanned {len(ours)} files; {len(terms)} denylist terms")
    print(f"denylist hits: {len(hits)}")
    for h in hits:
        print("  " + h)
    if a.compare:
        if licences:
            print("left out of the overlap comparison (verbatim third-party licence texts): "
                  + ", ".join(str(p.relative_to(ROOT)) for p in licences))
        print(f"lines of {MIN_LEN}+ characters shared with {a.compare}: {len(overlap)}")
        for o in overlap:
            print("  " + o)
    return 1 if hits or overlap else 0


if __name__ == "__main__":
    sys.exit(main())
