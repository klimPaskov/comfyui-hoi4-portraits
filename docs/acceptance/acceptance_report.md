# Acceptance Report

- Overall: **BLOCKED**
- Recommended exit code: `15`

## Gate summary

| Gate | Status |
| --- | --- |
| `package_checksums` | **PASS** |
| `hardware_detection` | **PASS** |
| `hardware_runtime` | **BLOCKED** |
| `remote_topology_auth` | **BLOCKED** |
| `immutable_lora` | **PASS** |
| `approved_background` | **BLOCKED** |
| `source_fixture_and_provenance` | **BLOCKED** |
| `dependencies_and_models` | **BLOCKED** |
| `custom_node_preflight` | **BLOCKED** |
| `runtime_dependency_lock` | **PASS** |
| `krea_live_compatibility` | **BLOCKED** |
| `preprocessing_and_audit_dependencies` | **BLOCKED** |
| `calibrated_identity_thresholds` | **BLOCKED** |
| `repository_preflight` | **PASS** |
| `licenses_and_rights` | **BLOCKED_PENDING_PROJECT_OWNER_REVIEW** |
| `workflow_structure` | **PASS** |
| `autoprompter_validator` | **PASS** |
| `dds_gate` | **PASS** |
| `identity_style_experiments` | **BLOCKED_UNTIL_RUNTIME** |
| `benchmark_reports` | **BLOCKED** |
| `identity_style_comparison` | **BLOCKED_NO_REAL_CANDIDATES** |
| `runpod_deployment_surface` | **BLOCKED_UNRESOLVED_IMAGE_LOCK** |
| `schema_validation` | **BLOCKED** |
| `integration_packages` | **BLOCKED** |
| `secret_scan` | **PASS** |

## Blockers

- The required MPS runtime, Python floor, PyTorch capability, or ComfyUI installation is not verified; this profile cannot be claimed executable.
- The approved HOI4 portrait background registry is unresolved; generation and DDS promotion are blocked.
- No legally usable source portrait fixture and complete provenance record is present for calibration or route execution.
- Required Krea/Qwen model artifacts are not installed and live ComfyUI compatibility has not been verified.
- One or more required custom-node checkouts or class inventories are missing; workflow execution is blocked.
- RunPod endpoint credentials are absent; remote submission/acceptance cannot run.
- No live generic agentic HOI4 target repository was found; only the planning proposal is available.
- Identity/style thresholds are still calibration placeholders; no production candidate may be accepted.
- Krea 2 Turbo compatibility, identity-edit behavior, and the immutable style LoRA matrix have not been measured in the pinned runtime.
- Pinned preprocessing/audit model artifacts have no verified checksums; masking, face analysis, and independent audit cannot run.
- License/rights review is not fully approved for Krea redistribution or the unresolved background.

## Additional blocked or skipped surfaces

- `identity_style_experiments`: BLOCKED_UNTIL_RUNTIME
- `benchmark_reports`: human_local_mac_16gb=BLOCKED_RUNTIME_UNAVAILABLE, human_full_power_gpu=BLOCKED_PREFLIGHT, agent_local_mac_16gb=BLOCKED_RUNTIME_UNAVAILABLE, agent_remote_runpod=BLOCKED_REMOTE_AUTH
- `identity_style_comparison`: No comparison sheet or candidate ranking is produced without a legally usable source fixture, live runtime, calibrated thresholds, and independent audit evidence.
- `runpod_deployment_surface`: BLOCKED_UNRESOLVED_RUNTIME_LOCK
- `schema_validation`: normative JSON Schema validator is unavailable: ModuleNotFoundError
- `integration_packages`: BLOCKED

## Runtime claims

```json
{
  "local_mac_execution": "NOT_CLAIMED",
  "remote_runpod_execution": "NOT_CLAIMED",
  "final_png": "NOT_CREATED",
  "final_dds": "NOT_CREATED",
  "mod_wiring": "PARENT_AGENT_ONLY"
}
```
