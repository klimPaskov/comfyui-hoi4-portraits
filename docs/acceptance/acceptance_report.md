# Acceptance Report

- Overall: **BLOCKED**
- Recommended exit code: `15`

## Gate summary

| Gate | Status |
| --- | --- |
| `package_checksums` | **PASS** |
| `hardware_detection` | **PASS** |
| `hardware_runtime` | **BLOCKED** |
| `immutable_lora` | **PASS** |
| `approved_background` | **BLOCKED** |
| `dependencies_and_models` | **BLOCKED** |
| `runtime_dependency_lock` | **BLOCKED** |
| `krea_live_compatibility` | **BLOCKED** |
| `licenses_and_rights` | **BLOCKED_PENDING_PROJECT_OWNER_REVIEW** |
| `workflow_structure` | **PASS** |
| `autoprompter_validator` | **PASS** |
| `dds_gate` | **PASS** |
| `identity_style_experiments` | **BLOCKED_UNTIL_RUNTIME** |
| `integration_packages` | **PASS** |
| `secret_scan` | **PASS** |

## Blockers

- PyTorch/MPS and ComfyUI are not installed or MPS capability is not verified; local execution cannot be claimed.
- The approved HOI4 portrait background registry is unresolved; generation and DDS promotion are blocked.
- No legally usable source portrait fixture and complete provenance record is present for calibration or route execution.
- Required Krea/Qwen model artifacts are not installed and live ComfyUI compatibility has not been verified.
- The pinned ComfyUI runtime dependency lock still contains unresolved platform versions or artifact checksums.
- RunPod endpoint credentials are absent; remote submission/acceptance cannot run.
- No live generic agentic HOI4 target repository was found; only the planning proposal is available.
- Identity/style thresholds are still calibration placeholders; no production candidate may be accepted.
- Krea 2 Turbo compatibility, identity-edit behavior, and the immutable style LoRA matrix have not been measured in the pinned runtime.
- Pinned preprocessing/audit model artifacts have no verified checksums; masking, face analysis, and independent audit cannot run.
- License/rights review is not fully approved for Krea redistribution or the unresolved background.

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
