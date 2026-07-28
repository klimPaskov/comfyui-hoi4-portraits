# Acceptance Report

- Overall: **BLOCKED**
- Recommended exit code: `15`

## Gate summary

| Gate | Status |
| --- | --- |
| `package_checksums` | **PASS** |
| `hardware_detection` | **PASS** |
| `hardware_runtime` | **PASS** |
| `remote_topology_auth` | **BLOCKED** |
| `immutable_lora` | **PASS** |
| `approved_background` | **BLOCKED** |
| `source_fixture_and_provenance` | **PASS** |
| `dependencies_and_models` | **PASS** |
| `custom_node_preflight` | **PASS** |
| `runtime_dependency_lock` | **PASS** |
| `krea_live_compatibility` | **PASS** |
| `autoprompter_runtime` | **PASS_LOCAL_AND_FULL_POWER_FORMAT_ONLY** |
| `preprocessing_and_audit_dependencies` | **PASS** |
| `calibrated_identity_thresholds` | **BLOCKED** |
| `repository_preflight` | **PASS** |
| `licenses_and_rights` | **BLOCKED_PENDING_PROJECT_OWNER_REVIEW** |
| `workflow_structure` | **PASS** |
| `autoprompter_validator` | **PASS** |
| `dds_gate` | **PASS** |
| `identity_style_experiments` | **PLANNED_BLOCKED_UNTIL_APPROVED_FIXTURE_BACKGROUND_THRESHOLDS** |
| `benchmark_reports` | **BLOCKED** |
| `identity_style_comparison` | **BLOCKED_NO_REAL_CANDIDATES** |
| `runpod_deployment_surface` | **BLOCKED_UNRESOLVED_IMAGE_LOCK** |
| `schema_validation` | **PASS** |
| `integration_packages` | **BLOCKED** |
| `secret_scan` | **PASS** |

## Blockers

- The approved HOI4 portrait background registry is unresolved; generation and DDS promotion are blocked.
- RunPod endpoint credentials are absent; remote submission/acceptance cannot run.
- No live generic agentic HOI4 target repository was found; only the planning proposal is available.
- Identity/style thresholds are still calibration placeholders; no production candidate may be accepted.
- Krea 2 source-specific model loading, the eight-step Turbo execution, and the immutable style-LoRA experiment matrix remain unmeasured until an approved fixture, background, and calibrated audit thresholds are available.
- License/rights review is not fully approved for Krea redistribution or the unresolved background.

## Additional blocked or skipped surfaces

- `identity_style_experiments`: The matrix is recorded but execution is fail-closed until an approved source fixture, background, calibrated thresholds, and source-specific runtime evidence exist.
- `benchmark_reports`: human_local_mac_16gb=BLOCKED_PREFLIGHT, human_full_power_gpu=BLOCKED_PREFLIGHT, agent_local_mac_16gb=BLOCKED_PREFLIGHT, agent_remote_runpod=BLOCKED_REMOTE_AUTH
- `identity_style_comparison`: No comparison sheet or candidate ranking is produced without a production-authorized source fixture, live generation runtime, calibrated thresholds, and independent audit evidence.
- `runpod_deployment_surface`: BLOCKED_UNRESOLVED_RUNTIME_LOCK
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
