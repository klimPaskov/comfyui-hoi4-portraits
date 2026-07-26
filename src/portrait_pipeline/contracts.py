from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .constants import (
    DEPENDENCY_LOCK_VERSION,
    ExitCode,
    ExecutionProfile,
    JobStatus,
    PROFILE_LIMITS,
    WORKFLOW_VERSION,
)
from .util import is_sha256, project_root, sha256_file


@dataclass(frozen=True)
class ValidationIssue:
    path: str
    message: str
    code: ExitCode = ExitCode.INPUT_SCHEMA_INVALID

    def as_dict(self) -> dict[str, str | int]:
        return {"path": self.path, "message": self.message, "code": int(self.code)}


def _type_matches(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "null":
        return value is None
    return True


def _path_join(path: str, part: object) -> str:
    return f"{path}.{part}" if path else str(part)


def _fallback_validate(value: Any, schema: dict[str, Any], path: str = "") -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    expected = schema.get("type")
    if expected is not None:
        choices = expected if isinstance(expected, list) else [expected]
        if not any(_type_matches(value, choice) for choice in choices):
            return [ValidationIssue(path or "$", f"expected type {expected!r}")]

    if "const" in schema and value != schema["const"]:
        issues.append(ValidationIssue(path or "$", f"must equal {schema['const']!r}"))
    if "enum" in schema and value not in schema["enum"]:
        issues.append(ValidationIssue(path or "$", f"must be one of {schema['enum']!r}"))

    if isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            issues.append(ValidationIssue(path or "$", "is shorter than minLength"))
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            issues.append(ValidationIssue(path or "$", "is longer than maxLength"))
        if "pattern" in schema and re.search(schema["pattern"], value) is None:
            issues.append(ValidationIssue(path or "$", f"does not match {schema['pattern']!r}"))

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            issues.append(ValidationIssue(path or "$", "is below minimum"))
        if "maximum" in schema and value > schema["maximum"]:
            issues.append(ValidationIssue(path or "$", "is above maximum"))

    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            issues.append(ValidationIssue(path or "$", "has too few items"))
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            issues.append(ValidationIssue(path or "$", "has too many items"))
        if schema.get("uniqueItems"):
            encoded = [json.dumps(item, sort_keys=True, default=str) for item in value]
            if len(encoded) != len(set(encoded)):
                issues.append(ValidationIssue(path or "$", "items must be unique"))
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value):
                issues.extend(_fallback_validate(item, item_schema, _path_join(path, index)))

    if isinstance(value, dict):
        required = schema.get("required", [])
        for key in required:
            if key not in value:
                issues.append(ValidationIssue(_path_join(path, key), "is required"))
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for key in value:
                if key not in properties:
                    issues.append(ValidationIssue(_path_join(path, key), "is not allowed"))
        for key, child_schema in properties.items():
            if key in value and isinstance(child_schema, dict):
                issues.extend(_fallback_validate(value[key], child_schema, _path_join(path, key)))

    if "oneOf" in schema:
        matches = []
        for option in schema["oneOf"]:
            option_issues = _fallback_validate(value, option, path)
            if not option_issues:
                matches.append(option)
        if len(matches) != 1:
            issues.append(ValidationIssue(path or "$", "must match exactly one oneOf branch"))
    return issues


def validate_schema(value: Any, schema_path: str | Path) -> list[ValidationIssue]:
    """Validate with Draft 2020-12 when available, otherwise use a strict fallback.

    The repository keeps the normative schemas as data. The fallback exists so
    preflight and contract checks remain useful on a clean system before Python
    dependencies are installed.
    """

    schema = json.loads(Path(schema_path).read_text(encoding="utf-8"))
    try:
        import jsonschema  # type: ignore

        validator = jsonschema.Draft202012Validator(schema)
        return [
            ValidationIssue(
                ".".join(str(part) for part in error.absolute_path) or "$",
                error.message,
            )
            for error in sorted(validator.iter_errors(value), key=lambda item: list(item.absolute_path))
        ]
    except ImportError:
        return _fallback_validate(value, schema)


def validate_job_policy(job: dict[str, Any], root: str | Path | None = None) -> list[ValidationIssue]:
    root_path = project_root(root)
    issues: list[ValidationIssue] = []
    profile = job.get("execution_profile")
    if profile in PROFILE_LIMITS:
        limits = PROFILE_LIMITS[profile]
        if job.get("candidate_count", 0) > limits["candidate_max"]:
            issues.append(
                ValidationIssue(
                    "candidate_count",
                    f"exceeds profile ceiling {limits['candidate_max']}",
                )
            )
        if job.get("retry_limit", 0) > limits["retry_max"]:
            issues.append(ValidationIssue("retry_limit", f"exceeds profile ceiling {limits['retry_max']}"))

    prompt = job.get("prompt")
    if isinstance(prompt, str):
        if not prompt.startswith("hoi4_portrait,"):
            issues.append(ValidationIssue("prompt", "must begin exactly with hoi4_portrait,"))
        record_name = job.get("subject_identity", {}).get("record_name")
        if isinstance(record_name, str) and record_name.casefold() in prompt.casefold():
            issues.append(ValidationIssue("prompt", "contains the subject record name", ExitCode.INPUT_SCHEMA_INVALID))
    subject = job.get("subject_identity", {})
    provenance = job.get("source_provenance", {})
    if subject.get("real_person") is True and subject.get("identity_classification") != "grounded_real_person":
        issues.append(ValidationIssue("subject_identity", "real_person requires grounded_real_person"))
    if subject.get("real_person") is True:
        if provenance.get("source_class") not in {"user_provided", "attributed_public_source", "repository_source"}:
            issues.append(ValidationIssue("source_provenance.source_class", "real person source requires provenance", ExitCode.PROVENANCE_MISSING))
        for key in ("attribution", "rights_notes"):
            if not provenance.get(key):
                issues.append(ValidationIssue(f"source_provenance.{key}", "required for a real person", ExitCode.PROVENANCE_MISSING))

    background = job.get("approved_background")
    if isinstance(background, dict):
        if background.get("registry_id") == "UNRESOLVED_BLOCK_EXECUTION" or background.get("sha256") == "RESOLVE":
            issues.append(ValidationIssue("approved_background", "approved background registry is unresolved", ExitCode.BACKGROUND_UNRESOLVED))
        elif not is_sha256(background.get("sha256")):
            issues.append(ValidationIssue("approved_background.sha256", "must be a lowercase SHA-256", ExitCode.BACKGROUND_UNRESOLVED))
        else:
            registry_path = root_path / "config" / "background_registry.json"
            if registry_path.is_file():
                registry = json.loads(registry_path.read_text(encoding="utf-8"))
                entries = [item for item in registry.get("backgrounds", []) if item.get("registry_id") == background.get("registry_id")]
                if not entries or entries[0].get("sha256") != background.get("sha256"):
                    issues.append(ValidationIssue("approved_background", "does not match the approved registry", ExitCode.BACKGROUND_UNRESOLVED))
    source_path = job.get("source_image_path")
    if isinstance(source_path, str) and not Path(source_path).is_absolute():
        source_path = root_path / source_path
    if source_path and not Path(source_path).is_file():
        issues.append(ValidationIssue("source_image_path", "source image is missing", ExitCode.SOURCE_INVALID))
    return issues


def validate_job(job: dict[str, Any], root: str | Path | None = None) -> list[ValidationIssue]:
    root_path = project_root(root)
    issues = validate_schema(job, root_path / "schemas" / "portrait_job_input.schema.json")
    if not issues:
        issues.extend(validate_job_policy(job, root_path))
    return issues


def validate_audit(audit: dict[str, Any], root: str | Path | None = None) -> list[ValidationIssue]:
    root_path = project_root(root)
    issues = validate_schema(audit, root_path / "schemas" / "portrait_audit.schema.json")
    if audit.get("auditor", {}).get("independent_from_producer") is not True:
        issues.append(ValidationIssue("auditor.independent_from_producer", "must be true"))
    gates = audit.get("hard_gates", {})
    if audit.get("verdict") == "PASS" and any(gates.get(name) != "PASS" for name in gates):
        issues.append(ValidationIssue("verdict", "PASS requires every hard gate to be PASS"))
    return issues


def build_blocked_output(
    job: dict[str, Any] | None,
    exit_code: ExitCode,
    message: str,
    *,
    warnings: list[str] | None = None,
    blockers: list[str] | None = None,
    root: str | Path | None = None,
) -> dict[str, Any]:
    root_path = project_root(root)
    source_path = (job or {}).get("source_image_path")
    source_sha = "0" * 64
    if source_path:
        candidate = Path(source_path)
        if not candidate.is_absolute():
            candidate = root_path / candidate
        if candidate.is_file():
            source_sha = sha256_file(candidate)
    profile = (job or {}).get("execution_profile", "unknown")
    return {
        "schema_version": "1.0.0",
        "job_id": (job or {}).get("job_id", "invalid-job"),
        "status": JobStatus.BLOCKED.value if exit_code not in {ExitCode.CANCELED} else JobStatus.CANCELED.value,
        "exit_code": int(exit_code),
        "error_code": exit_code.name,
        "error_message": message,
        "execution_profile": profile,
        "workflow_version": WORKFLOW_VERSION,
        "dependency_lock_version": DEPENDENCY_LOCK_VERSION,
        "source_sha256": source_sha,
        "prompt": (job or {}).get("prompt", ""),
        "seeds": [],
        "dependencies": [],
        "candidate_paths": [],
        "selected_candidate": None,
        "audits": {"identity": None, "style": None, "mask": None, "provenance": None},
        "final_png": None,
        "final_dds": None,
        "final_checksums": None,
        "manifest_path": None,
        "comparison_sheet_path": None,
        "warnings": warnings or [],
        "blockers": blockers or [message],
        "timing": {"created_at": datetime.now(timezone.utc).isoformat()},
        "peak_memory": None,
    }


def main_validate_job() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Validate one portrait job input against the normative schema and policy.")
    parser.add_argument("job_json", type=Path)
    args = parser.parse_args()
    root = project_root(args.job_json.parent)
    job = json.loads(args.job_json.read_text(encoding="utf-8"))
    issues = validate_job(job, root)
    print(json.dumps({"valid": not issues, "issues": [issue.as_dict() for issue in issues]}, indent=2))
    return 0 if not issues else int(ExitCode.INPUT_SCHEMA_INVALID)

