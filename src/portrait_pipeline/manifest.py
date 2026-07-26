from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .constants import DEPENDENCY_LOCK_VERSION, WORKFLOW_VERSION
from .util import atomic_json_write, canonical_hash, sha256_file


def build_job_manifest(*, job: dict[str, Any], job_root: str | Path, workflow: dict[str, Any], source_records: list[dict[str, Any]], preprocessing: list[dict[str, Any]], candidates: list[dict[str, Any]], audits: list[dict[str, Any]], selection: dict[str, Any], finals: dict[str, Any] | None = None) -> dict[str, Any]:
    root = Path(job_root)
    manifest: dict[str, Any] = {
        "schema_version": "1.0.0",
        "manifest_type": "hoi4_portrait_job",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "job_id": job.get("job_id"),
        "execution_profile": job.get("execution_profile"),
        "workflow_version": WORKFLOW_VERSION,
        "workflow": workflow,
        "dependency_lock_version": DEPENDENCY_LOCK_VERSION,
        "source": source_records,
        "preprocessing": preprocessing,
        "prompt": {"sha256": canonical_hash(job.get("prompt", "")), "source": "job_contract" if str(job.get("execution_profile", "")).startswith("agent_") else "autoprompter", "value_excluded_from_public_manifest": True},
        "candidates": candidates,
        "audits": [{"candidate_id": audit.get("candidate_id"), "verdict": audit.get("verdict"), "digest": canonical_hash(audit), "path": audit.get("evidence", {}).get("manifest")} for audit in audits],
        "selection": selection,
        "finals": finals,
        "private_artifact_policy": "source, generated images, model weights, and caches remain under the private job root and are never committed",
    }
    manifest["manifest_sha256"] = canonical_hash(manifest)
    return manifest


def write_job_manifest(path: str | Path, manifest: dict[str, Any]) -> dict[str, Any]:
    atomic_json_write(path, manifest)
    return manifest

