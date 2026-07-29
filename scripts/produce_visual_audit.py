#!/usr/bin/env python3
"""Produce private visual-audit evidence in a separate process."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from portrait_pipeline.visual_audit_service import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
