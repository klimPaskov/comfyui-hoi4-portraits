"""Resolve a local Chaos Redux portrait background into repository assets.

This is a resolver, not an approval step. It copies/decode-converts only the
locally available source into the project background area and emits a
candidate record. If an exact owner-approved registry entry already exists,
re-resolution preserves that approval; it never creates or broadens approval.
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
OUTPUT_RELATIVE = Path("backgrounds/chaos_redux_portrait_leader_background.png")


def _default_source() -> Path:
    return Path.home() / "Documents" / "Paradox Interactive" / "Hearts of Iron IV" / "mod" / "Chaos-Redux" / "gfx" / "leaders" / "portrait_leader_background.psd"


def _existing_approval(root: Path, runtime_sha256: str) -> dict[str, object] | None:
    """Return an exact prior approval, if the registry already contains one."""

    registry_path = root / "config" / "background_registry.json"
    if not registry_path.is_file():
        return None
    try:
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if registry.get("registry_status") != "RESOLVED":
        return None
    for entry in registry.get("backgrounds", []):
        if (
            isinstance(entry, dict)
            and entry.get("status") == "APPROVED"
            and entry.get("runtime_path") == str(OUTPUT_RELATIVE)
            and entry.get("sha256") == runtime_sha256
            and entry.get("approved_by")
            and entry.get("approval_attestation")
        ):
            return entry
    return None


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
    approved_entry = _existing_approval(root, str(checks["runtime_sha256"]))
    if approved_entry is not None:
        report = {
            "schema_version": "1.0.0",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "APPROVED_LOCAL_COPY_ONLY",
            "checks": checks,
            "rights": {
                "source_class": "project_asset_candidate",
                "source_repository": "Chaos Redux live checkout",
                "source_license_record": "not found in live repository root",
                "redistribution_rule": "local_copy_only",
                "attribution": approved_entry.get("attribution"),
            },
            "approval": {
                "status": "APPROVED",
                "approved_by": approved_entry.get("approved_by", []),
                "attestation": approved_entry.get("approval_attestation"),
                "registry_update_permitted": True,
            },
            "production_policy": {
                "config_registry_modified": True,
                "generation_permitted": True,
                "dds_promotion_permitted": False,
            },
        }
    else:
        report = {
        "schema_version": "1.0.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "CANDIDATE_RUNTIME_READY_OWNER_APPROVAL_REQUIRED",
        "checks": checks,
            "rights": {
                "source_class": "project_asset_candidate",
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
    parser = argparse.ArgumentParser(description="Resolve a local HOI4 background candidate without approving it.")
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument("--source", type=Path, default=None)
    args = parser.parse_args()
    root = project_root(args.root)
    report = resolve(root, (args.source or _default_source()).expanduser().resolve())
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["status"] == "CANDIDATE_RUNTIME_READY_OWNER_APPROVAL_REQUIRED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
