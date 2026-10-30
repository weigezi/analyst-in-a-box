"""Entry point that works from any folder: python scripts/aib_cli.py <command> ..."""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from aib.cli import main  # noqa: E402

sys.exit(main())
