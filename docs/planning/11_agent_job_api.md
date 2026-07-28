# Agent Job API

## Job root

Every request creates or reuses:

`jobs/<job_id>/`

The job id must match `^[a-z0-9][a-z0-9_-]{2,63}$`. The directory is created atomically. Reusing a job id with different normalized input returns `JOB_ID_CONFLICT`.

## Input schema

The normative schema is `schemas/portrait_job_input.schema.json`.

Important rules:

- `prompt` begins exactly `hoi4_portrait,`.
- A person's record name can exist in `subject_identity.record_name` and integration metadata.
- The name cannot appear in `prompt`.
- A real person requires `grounded_real_person` and attributed or user-provided source evidence.
- `approved_background.sha256` must match the registry.
- `candidate_count` and `retry_limit` must fit the profile ceiling.
- Optional mod paths do not grant the portrait pipeline permission to wire gameplay. They describe the parent handoff.

## Output schema

The normative schema is `schemas/portrait_job_output.schema.json`.

On success, `selected_candidate`, `final_png`, `final_dds`, `final_checksums`, `manifest_path`, and `comparison_sheet_path` are non-null. On any identity, style, mask, provenance, or DDS failure, final PNG and DDS remain null.

## Exit codes

| Code | Symbol | Meaning |
| ---: | --- | --- |
| 0 | `SUCCESS` | all mandatory gates passed |
| 10 | `INPUT_SCHEMA_INVALID` | job JSON failed schema or policy |
| 11 | `SOURCE_INVALID` | source missing, corrupt, unsafe, or unsupported |
| 12 | `AMBIGUOUS_SUBJECT` | more than one plausible subject and no deterministic selector |
| 13 | `FACE_NOT_FOUND_OR_UNUSABLE` | selected person has no auditable face |
| 14 | `PROVENANCE_MISSING` | source attribution, rights, or authorization incomplete |
| 15 | `BACKGROUND_UNRESOLVED` | approved background unavailable or checksum mismatch |
| 20 | `DEPENDENCY_MISSING` | required package or binary absent |
| 21 | `MODEL_CHECKSUM_MISMATCH` | model, LoRA, or reference hash mismatch |
| 22 | `NODE_MISSING` | workflow node class missing or schema mismatch |
| 23 | `WORKFLOW_INVALID` | graph policy or load validation failed |
| 30 | `OUT_OF_MEMORY` | local or remote memory recovery exhausted |
| 31 | `GENERATION_FAILED` | ComfyUI execution failed after bounded retry |
| 32 | `CANCELED` | caller or system canceled the job |
| 40 | `IDENTITY_NO_PASSING_CANDIDATE` | every candidate failed or was uncertain on identity |
| 41 | `STYLE_NO_PASSING_CANDIDATE` | identity passed but required HOI4 style failed |
| 42 | `MASK_AUDIT_FAILED` | foreground, alpha, boundary, or composite gate failed |
| 43 | `AUDIT_UNCERTAIN` | independent auditor could not approve |
| 50 | `DDS_VALIDATION_FAILED` | DDS write or validation failed |
| 51 | `INTEGRATION_BLOCKED` | accepted portrait exists but parent integration preflight failed |
| 60 | `REMOTE_AUTH_OR_TRANSPORT_FAILED` | authenticated remote operation failed |
| 70 | `INTERNAL_ERROR` | unclassified controller error with protected trace |

## Seed policy

- `fixed`: caller supplies a seed.
- `derived`: seed is derived from source checksum, prompt checksum, candidate index, workflow version, and a versioned derivation label.
- `random_recorded`: cryptographic random seed is generated and recorded before queueing.

Every candidate has its own seed. A retry does not reuse the same seed unless the experiment specifically changes one parameter for an A/B comparison.

## Idempotency

Normalize job JSON, remove fields explicitly marked non-semantic, and hash it with source SHA-256 and workflow checksum. Repeated identical submissions return the same job. A completed job can be reused only when all final files still match their recorded hashes and the caller is authorized.

## Status payload

Status includes:

- job id
- state
- shared stage
- attempt number
- candidate count completed
- progress value and source
- prompt id when active
- last update time
- warnings
- blockers
- terminal exit code when present

## Output retrieval

Return descriptors, not raw paths alone:

```json
{
  "artifact_id": "final_dds",
  "relative_path": "final/leader_example.dds",
  "mime_type": "image/vnd-ms.dds",
  "size_bytes": 131168,
  "sha256": "..."
}
```

For remote use, descriptors include a short-lived authorized download route.

## Agent execution example

1. Call `portrait_health`.
2. Call `portrait_inventory`.
3. Call `portrait_validate_workflow` for `agent_local_mac_16gb` or `agent_remote_runpod`.
4. Call `portrait_upload_source`.
5. Build input JSON and call `portrait_submit_job`.
6. Use `portrait_watch_job` or bounded `portrait_job_status` polling.
7. On success, call `portrait_fetch_outputs`.
8. Verify returned checksums before copying the DDS into a mod.
9. Parent agent performs character, GFX, path, and live-consumer wiring.
