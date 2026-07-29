# Benchmark Report: `agent_local_mac_16gb`

- Status: **BLOCKED_PRODUCTION_GATES_CPU_FALLBACK**
- Reason: A private CPU fallback candidate was produced, but local production acceptance remains blocked by accelerator, memory, calibration, and audit gates.
- Expected locked model bytes: `7553118462`
- Physical memory bytes: `17179869184`
- Capacity assessment: **MODEL_BYTES_WITHIN_PHYSICAL_MEMORY_NOT_EXECUTION_PROOF**

This report contains no production acceptance claim. Any CPU diagnostic execution evidence is explicitly quarantined from promotion. File-size arithmetic is a risk indicator, not an infeasibility measurement.

## Gate status

| Gate | Status |
| --- | --- |
| `approved_source_background` | **PASS** |
| `autoprompter_runtime` | **NOT_APPLICABLE** |
| `calibrated_identity_thresholds` | **BLOCKED** |
| `comfyui_runtime_dependency_lock` | **PASS** |
| `custom_node_preflight` | **PASS** |
| `hardware_detection` | **PASS** |
| `immutable_style_lora` | **PASS** |
| `krea_live_compatibility` | **PASS** |
| `license_and_rights_review` | **APPROVED** |
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
| `dry_validation_job` | **PASS_PREPROCESSING_ONLY_PRODUCTION_GATES_BLOCKED** |
| `generation` | **PASS_EXECUTION_ONLY_PRODUCTION_BLOCKED** |
| `thermal` | **NOT_MEASURED** |
| `quality` | **UNCERTAIN_AUDIT** |
| `failure_recovery` | **NOT_MEASURED** |

## Blockers

- Calibration evidence exists but does not yet demonstrate the required approved identity/style threshold set; no production candidate may be accepted.
- Krea 2 source-specific production acceptance and the immutable style-LoRA experiment matrix remain blocked: the default MPS route fails, the CPU fallback has one completed heavily-swapping run plus a newer interrupted canary, and calibrated audit thresholds plus independent audit evidence are still required.

## Required follow-up

- run the target profile inside its target accelerator environment without mutation
- resolve image-specific Python and system-package pins before building the RunPod image
- complete live source-specific model loading and the eight-step Turbo execution
- verify all model revisions, formats, sizes, and SHA-256 values in the target environment
- run the target profile with independent identity/style/mask/provenance audit
- record peak host memory, peak VRAM, runtime, thermal, cancellation, and repeatability evidence
