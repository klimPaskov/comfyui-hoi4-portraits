# Acceptance Report

- Overall: **BLOCKED**
- Recommended exit code: `20`

## Gate summary

| Gate | Status |
| --- | --- |
| `package_checksums` | **PASS** |
| `hardware_detection` | **PASS** |
| `hardware_runtime` | **PASS** |
| `remote_topology_auth` | **BLOCKED** |
| `immutable_lora` | **PASS** |
| `approved_background` | **PASS** |
| `source_fixture_and_provenance` | **PASS** |
| `dependencies_and_models` | **PASS** |
| `custom_node_preflight` | **BLOCKED** |
| `runtime_dependency_lock` | **PASS** |
| `krea_live_compatibility` | **PASS** |
| `autoprompter_runtime` | **PASS_LOCAL_AND_FULL_POWER_FORMAT_ONLY** |
| `visual_audit_runtime` | **PASS_FORMAT_ONLY_EXECUTION_UNVERIFIED** |
| `preprocessing_and_audit_dependencies` | **PASS** |
| `calibrated_identity_thresholds` | **BLOCKED** |
| `repository_preflight` | **PASS** |
| `licenses_and_rights` | **APPROVED** |
| `workflow_structure` | **PASS** |
| `autoprompter_validator` | **PASS** |
| `dds_gate` | **PASS** |
| `identity_style_experiments` | **PLANNED_BLOCKED_UNTIL_APPROVED_FIXTURE_BACKGROUND_THRESHOLDS** |
| `benchmark_reports` | **BLOCKED** |
| `identity_style_comparison` | **BLOCKED_DIAGNOSTIC_CANDIDATES_NOT_PRODUCTION_AUTHORIZED** |
| `comfy_cloud_execution` | **BLOCKED_CLOUD_NODE_MODEL_PARITY** |
| `schema_validation` | **PASS** |
| `integration_packages` | **BLOCKED** |
| `secret_scan` | **PASS** |

## Blockers

- One or more required custom-node checkouts or class inventories are missing; workflow execution is blocked.
- The authenticated Cloud UI probe saved all six workflows but found unsupported project custom nodes and missing required LoRAs; the project API-key route remains unavailable and Cloud execution is blocked by node/model parity.
- Calibration evidence exists but does not yet demonstrate the required approved identity/style threshold set; no production candidate may be accepted.
- Krea 2 source-specific production acceptance and the immutable style-LoRA experiment matrix remain blocked: the default MPS route fails, the CPU fallback has one completed heavily-swapping run plus a newer interrupted canary, and calibrated audit thresholds plus independent audit evidence are still required.

## Additional blocked or skipped surfaces

- `visual_audit_runtime`: PASS_FORMAT_ONLY_EXECUTION_UNVERIFIED
- `identity_style_experiments`: The matrix execution report is fail-closed: no candidate was queued because mandatory preflight and independent-audit prerequisites remain unresolved.
- `benchmark_reports`: human_local_mac_16gb=BLOCKED_PRODUCTION_GATES_CPU_FALLBACK, human_local_nvidia_16gb=BLOCKED_RUNTIME_UNAVAILABLE, human_full_power_gpu=BLOCKED_REMOTE_AUTH, agent_local_mac_16gb=BLOCKED_PRODUCTION_GATES_CPU_FALLBACK, agent_local_nvidia_16gb=BLOCKED_RUNTIME_UNAVAILABLE, agent_full_power_gpu=BLOCKED_REMOTE_AUTH
- `identity_style_comparison`: Diagnostic candidates were observed, but no comparison ranking or production winner is produced until calibrated thresholds and independent all-PASS audits authorize them.
- `comfy_cloud_execution`: BLOCKED_CLOUD_NODE_MODEL_PARITY
- `integration_packages`: BLOCKED

## Runtime claims

```json
{
  "local_mac_execution": "CPU_FALLBACK_CANDIDATE_PRODUCED_PRODUCTION_GATES_BLOCKED",
  "comfy_cloud_execution": "NOT_CLAIMED",
  "final_png": "NOT_CREATED",
  "final_dds": "NOT_CREATED",
  "mod_wiring": "PARENT_AGENT_ONLY"
}
```
