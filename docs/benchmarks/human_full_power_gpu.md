# Benchmark Report: `human_full_power_gpu`

- Status: **BLOCKED_REMOTE_AUTH**
- Reason: Comfy Cloud subscription/API-key access and authenticated remote acceptance are unavailable.
- Expected locked model bytes: `38229188758`
- Physical memory bytes: `17179869184`
- Capacity assessment: **MODEL_BYTES_EXCEED_PHYSICAL_MEMORY_RISK_ONLY**

This report contains no production acceptance claim. Any CPU diagnostic execution evidence is explicitly quarantined from promotion. File-size arithmetic is a risk indicator, not an infeasibility measurement.

## Gate status

| Gate | Status |
| --- | --- |
| `approved_source_background` | **PASS** |
| `autoprompter_runtime` | **PASS_FORMAT_ONLY_CLOUD_EXECUTION_UNVERIFIED** |
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
| `remote_topology_auth` | **BLOCKED** |
| `repository_preflight` | **PASS** |
| `source_fixture_and_provenance` | **PASS** |
| `visual_audit_runtime` | **PASS_FORMAT_ONLY_EXECUTION_UNVERIFIED** |

## Measurements

| Measurement | Status |
| --- | --- |
| `workflow_structure` | **PASS** |
| `runtime_health` | **PASS_SCHEMA_ONLY** |
| `workflow_load` | **PASS_SCHEMA_ONLY** |
| `dry_validation_job` | **PASS_PREPROCESSING_ONLY_PRODUCTION_GATES_BLOCKED** |
| `generation` | **BLOCKED_NOT_ATTEMPTED** |
| `thermal` | **NOT_MEASURED** |
| `quality` | **NOT_MEASURED** |
| `failure_recovery` | **NOT_MEASURED** |

## Blockers

- The authenticated Cloud UI probe saved all six workflows but found unsupported project custom nodes and missing required LoRAs; the project API-key route remains unavailable and Cloud execution is blocked by node/model parity.
- Calibration evidence exists but does not yet demonstrate the required approved identity/style threshold set; no production candidate may be accepted.
- Krea 2 source-specific production acceptance and the immutable style-LoRA experiment matrix remain blocked: the default MPS route fails, the CPU fallback has one completed heavily-swapping run plus a newer interrupted canary, and calibrated audit thresholds plus independent audit evidence are still required.
- The full-power human autoprompter format is pinned and processor-verified, but Comfy Cloud execution and node parity are not yet verified.

## Required follow-up

- run the target profile inside its target accelerator environment without mutation
- verify Comfy Cloud subscription, API authentication, custom-node parity, model availability, and source upload behavior
- complete live source-specific model loading and the eight-step Turbo execution
- verify all model revisions, formats, sizes, and SHA-256 values in the target environment
- run the target profile with independent identity/style/mask/provenance audit
- record peak host memory, peak VRAM, runtime, thermal, cancellation, and repeatability evidence
