#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from portrait_pipeline.experiments import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main(ROOT))

