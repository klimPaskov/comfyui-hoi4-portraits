#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from portrait_pipeline.independent_auditor import audit_candidate  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the read-only independent HOI4 portrait candidate auditor.")
    parser.add_argument("--job-root", type=Path, required=True)
    parser.add_argument("--candidate-id", required=True)
    parser.add_argument("--source-master", type=Path, required=True)
    parser.add_argument("--processed-reference", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--mask", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--producer-process-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    audit = audit_candidate(job_root=args.job_root, candidate_id=args.candidate_id, source_master=args.source_master, processed_reference=args.processed_reference, candidate=args.candidate, mask=args.mask, manifest=args.manifest, producer_process_id=args.producer_process_id, root=ROOT, output_path=args.output)
    print(json.dumps(audit, indent=2, ensure_ascii=False))
    return 0 if audit.get("verdict") in {"PASS", "FAIL"} else 43


if __name__ == "__main__":
    raise SystemExit(main())
