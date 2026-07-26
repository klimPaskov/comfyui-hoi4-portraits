# Benchmark Report: `agent_remote_runpod`

- Status: **BLOCKED_REMOTE_AUTH**
- Reason: RunPod endpoint credentials and authenticated remote acceptance are unavailable.
- Expected locked model bytes: `20694849246`
- Physical memory bytes: `17179869184`
- Capacity assessment: **MODEL_BYTES_EXCEED_PHYSICAL_MEMORY_RISK_ONLY**

This report contains no successful generation claim. File-size arithmetic is a risk indicator, not an infeasibility measurement.

## Gate status

| Gate | Status |
| --- | --- |
| `approved_source_background` | **BLOCKED** |
| `calibrated_identity_thresholds` | **BLOCKED** |
| `comfyui_runtime_dependency_lock` | **PASS** |
| `custom_node_preflight` | **BLOCKED** |
| `hardware_detection` | **PASS** |
| `immutable_style_lora` | **PASS** |
| `krea_live_compatibility` | **BLOCKED** |
| `license_and_rights_review` | **BLOCKED_PENDING_PROJECT_OWNER_REVIEW** |
| `local_runtime_capability` | **PASS** |
| `model_artifact_preflight` | **BLOCKED** |
| `planning_package_checksums` | **PASS** |
| `preprocessing_and_audit_dependencies` | **BLOCKED** |
| `remote_topology_auth` | **BLOCKED** |
| `repository_preflight` | **PASS** |
| `source_fixture_and_provenance` | **BLOCKED** |

## Measurements

| Measurement | Status |
| --- | --- |
| `workflow_structure` | **PASS** |
| `runtime_health` | **NOT_MEASURED** |
| `workflow_load` | **NOT_MEASURED** |
| `dry_validation_job` | **NOT_MEASURED** |
| `generation` | **NOT_MEASURED** |
| `thermal` | **NOT_MEASURED** |
| `quality` | **NOT_MEASURED** |
| `failure_recovery` | **NOT_MEASURED** |

## Blockers

- The approved HOI4 portrait background registry is unresolved; generation and DDS promotion are blocked.
- No legally usable source portrait fixture and complete provenance record is present for calibration or route execution.
- Required Krea/Qwen model artifacts are not installed and live ComfyUI compatibility has not been verified.
- One or more required custom-node checkouts or class inventories are missing; workflow execution is blocked.
- RunPod endpoint credentials are absent; remote submission/acceptance cannot run.
- No live generic agentic HOI4 target repository was found; only the planning proposal is available.
- Identity/style thresholds are still calibration placeholders; no production candidate may be accepted.
- Krea 2 Turbo compatibility, identity-edit behavior, and the immutable style LoRA matrix have not been measured in the pinned runtime.
- Pinned preprocessing/audit model artifacts are not all installed and checksum-verified; masking, face analysis, and independent audit cannot run.
- License/rights review is not fully approved for Krea redistribution or the unresolved background.

## Required follow-up

- verify the checksum-locked profile runtime inside the target environment without mutation
- resolve image-specific Python and system-package pins before building the RunPod image
- install and import the pinned ComfyUI/custom-node graph
- verify all model revisions, formats, sizes, and SHA-256 values
- provide an approved source fixture, background, and rights record
- run the target profile with independent identity/style/mask/provenance audit
- record peak host memory, peak VRAM, runtime, thermal, cancellation, and repeatability evidence
