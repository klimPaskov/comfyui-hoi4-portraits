# Benchmark Report: `agent_local_mac_16gb`

- Status: **BLOCKED_PREFLIGHT**
- Reason: One or more mandatory preflight gates remain blocked.
- Expected locked model bytes: `20694849246`
- Physical memory bytes: `17179869184`
- Capacity assessment: **MODEL_BYTES_EXCEED_PHYSICAL_MEMORY_RISK_ONLY**

This report contains no successful generation claim. File-size arithmetic is a risk indicator, not an infeasibility measurement.

## Gate status

| Gate | Status |
| --- | --- |
| `approved_source_background` | **BLOCKED** |
| `autoprompter_runtime` | **NOT_APPLICABLE** |
| `calibrated_identity_thresholds` | **BLOCKED** |
| `comfyui_runtime_dependency_lock` | **PASS** |
| `custom_node_preflight` | **PASS** |
| `hardware_detection` | **PASS** |
| `immutable_style_lora` | **PASS** |
| `krea_live_compatibility` | **PASS** |
| `license_and_rights_review` | **BLOCKED_PENDING_PROJECT_OWNER_REVIEW** |
| `local_runtime_capability` | **PASS** |
| `model_artifact_preflight` | **PASS** |
| `planning_package_checksums` | **PASS** |
| `preprocessing_and_audit_dependencies` | **PASS** |
| `remote_topology_auth` | **NOT_APPLICABLE** |
| `repository_preflight` | **PASS** |
| `source_fixture_and_provenance` | **PASS** |

## Measurements

| Measurement | Status |
| --- | --- |
| `workflow_structure` | **PASS** |
| `runtime_health` | **PASS_SCHEMA_ONLY** |
| `workflow_load` | **PASS_SCHEMA_ONLY** |
| `dry_validation_job` | **BLOCKED_NO_APPROVED_FIXTURE_OR_BACKGROUND** |
| `generation` | **BLOCKED_NOT_ATTEMPTED** |
| `thermal` | **NOT_MEASURED** |
| `quality` | **NOT_MEASURED** |
| `failure_recovery` | **NOT_MEASURED** |

## Blockers

- The approved HOI4 portrait background registry is unresolved; generation and DDS promotion are blocked.
- No live generic agentic HOI4 target repository was found; only the planning proposal is available.
- Identity/style thresholds are still calibration placeholders; no production candidate may be accepted.
- Krea 2 source-specific model loading, the eight-step Turbo execution, and the immutable style-LoRA experiment matrix remain unmeasured until an approved fixture, background, and calibrated audit thresholds are available.
- License/rights review is not fully approved for Krea redistribution or the unresolved background.

## Required follow-up

- run the target profile inside its target accelerator environment without mutation
- resolve image-specific Python and system-package pins before building the RunPod image
- complete live source-specific model loading and the eight-step Turbo execution
- verify all model revisions, formats, sizes, and SHA-256 values in the target environment
- provide an approved source fixture, background, and rights record
- run the target profile with independent identity/style/mask/provenance audit
- record peak host memory, peak VRAM, runtime, thermal, cancellation, and repeatability evidence
