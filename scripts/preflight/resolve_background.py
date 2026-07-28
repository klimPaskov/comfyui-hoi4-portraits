"""Resolve the locally installed Chaos Redux portrait background privately.

This is a resolver, not an approval step.  It copies/decode-converts only the
locally available source into the ignored private background area and emits a
candidate record.  ``config/background_registry.json`` remains unchanged
until the project owner supplies an explicit rights decision.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

from portrait_pipeline.util import atomic_json_write, project_root, sha256_file


EXPECTED_SOURCE_SHA256 = "4c9f9ab945fda0d74912684d0ce17a777b0b08838528cdba53afd901134bc8d6"
EXPECTED_SIZE = (156, 210)
OUTPUT_RELATIVE = Path("backgrounds/private/chaos_redux_portrait_leader_background.png")


def _default_source() -> Path:
    return Path.home() / "Documents" / "Paradox Interactive" / "Hearts of Iron IV" / "mod" / "Chaos-Redux" / "gfx" / "leaders" / "portrait_leader_background.psd"


def resolve(root: Path, source: Path) -> dict[str, object]:
    output = root / OUTPUT_RELATIVE
    output.parent.mkdir(parents=True, exist_ok=True)
    checks: dict[str, object] = {
        "source_present": source.is_file(),
        "source_path": "<external-repository>/gfx/leaders/portrait_leader_background.psd",
        "source_sha256": None,
        "source_sha256_match": False,
        "decoded_dimensions": None,
        "decoded_format": None,
        "runtime_path": str(OUTPUT_RELATIVE),
        "runtime_sha256": None,
        "runtime_ready": False,
    }
    if not source.is_file():
        report = {
            "schema_version": "1.0.0",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "BLOCKED_SOURCE_NOT_FOUND",
            "checks": checks,
            "approval": {"status": "NOT_REQUESTED", "approved_by": []},
        }
        atomic_json_write(root / "docs" / "preflight" / "background_runtime_candidate.json", report)
        return report

    checks["source_sha256"] = sha256_file(source)
    checks["source_sha256_match"] = checks["source_sha256"] == EXPECTED_SOURCE_SHA256
    if not checks["source_sha256_match"]:
        report = {
            "schema_version": "1.0.0",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "BLOCKED_SOURCE_CHECKSUM_MISMATCH",
            "checks": checks,
            "approval": {"status": "NOT_REQUESTED", "approved_by": []},
        }
        atomic_json_write(root / "docs" / "preflight" / "background_runtime_candidate.json", report)
        return report

    with Image.open(source) as image:
        checks["decoded_dimensions"] = list(image.size)
        checks["decoded_format"] = image.format
        if image.size != EXPECTED_SIZE:
            report = {
                "schema_version": "1.0.0",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "status": "BLOCKED_SOURCE_DIMENSIONS",
                "checks": checks,
                "approval": {"status": "NOT_REQUESTED", "approved_by": []},
            }
            atomic_json_write(root / "docs" / "preflight" / "background_runtime_candidate.json", report)
            return report
        image.convert("RGBA").save(output, format="PNG", optimize=False)

    checks["runtime_sha256"] = sha256_file(output)
    checks["runtime_ready"] = True
    report = {
        "schema_version": "1.0.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "CANDIDATE_RUNTIME_READY_OWNER_APPROVAL_REQUIRED",
        "checks": checks,
        "rights": {
            "source_class": "installed_project_repository",
            "source_repository": "Chaos Redux live checkout",
            "source_license_record": "not found in live repository root",
            "redistribution_rule": "local_copy_only_until_owner_approval",
            "attribution": "owner must provide or confirm",
        },
        "approval": {
            "status": "PENDING_PROJECT_OWNER_REVIEW",
            "approved_by": [],
            "registry_update_permitted": False,
        },
        "production_policy": {
            "config_registry_modified": False,
            "generation_permitted": False,
            "dds_promotion_permitted": False,
        },
    }
    atomic_json_write(root / "docs" / "preflight" / "background_runtime_candidate.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Resolve a private local HOI4 background candidate without approving it.")
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument("--source", type=Path, default=None)
    args = parser.parse_args()
    root = project_root(args.root)
    report = resolve(root, (args.source or _default_source()).expanduser().resolve())
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["status"] == "CANDIDATE_RUNTIME_READY_OWNER_APPROVAL_REQUIRED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
