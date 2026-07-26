# Initial Preflight Report

- Collected: `2026-07-26T13:16:58.573405+00:00`
- Status: **BLOCKED**
- Installation permitted: **False**
- Recommended exit code: `15`

## Gates

| Gate | Status | Evidence summary |
| --- | --- | --- |
| `hardware_detection` | **PASS** | `{"disk": {"command": ["df", "-h", "/Users/klimpaskov/Documents/Projects/comfyui-hoi4-portraits"], "returncode": 0, "stderr": "", "stdout": "Filesystem      Size    Used   Avail Capacity iused ifree %iused  Mounted on\n/dev/disk3s5   460Gi   144Gi   280Gi    34%    1.6M  2.9G    0%   /System/Volumes/Data"}, "machine": "arm64", "memory": {"arm64": "1", "cpu_count": "10", "memsize_bytes": "17179869184", "swap": {"command": ["/usr/sbin/sysctl", "vm.swapusage"], "returncode": 0, "stderr": "", "stdout` |
| `local_runtime_capability` | **BLOCKED** | `{"comfy_cli": null, "torch": {"error": "No module named 'torch'", "error_type": "ModuleNotFoundError", "installed": false}}` |
| `immutable_style_lora` | **PASS** | `{"actual_sha256": "2ad94552d151d2dedf151cf7356cdd3ea07677607ff289fc0ac61534b34dead1", "expected_sha256": "2ad94552d151d2dedf151cf7356cdd3ea07677607ff289fc0ac61534b34dead1", "immutable": true, "path": "/Users/klimpaskov/Documents/Projects/comfyui-hoi4-portraits/loras/hoi4_portrait_new_style_lora.safetensors", "present": true}` |
| `approved_source_background` | **BLOCKED** | `{"registry": {"backgrounds": [{"approved_by": [], "attribution": null, "height": null, "license_or_rights": null, "reason": "No approved project-owned or installed-game background was resolved during preflight.", "redistribution_rule": "blocked", "registry_id": "UNRESOLVED_BLOCK_EXECUTION", "role_scope": ["country_leader", "commander", "operative"], "runtime_path": null, "sha256": null, "source_class": "unresolved", "source_definition": null, "source_path": null, "status": "BLOCKED_UNTIL_RESOLVE` |
| `planning_package_checksums` | **PASS** | `{}` |
| `model_artifact_preflight` | **BLOCKED** | `{"local_files": [], "locked_models": 7, "unsupported_or_unverified": []}` |
| `remote_topology_auth` | **BLOCKED** | `{"credential_presence": {"GITHUB_TOKEN": false, "HF_TOKEN": false, "PORTRAIT_GATEWAY_TOKEN": false, "RUNPOD_API_KEY": false, "RUNPOD_ENDPOINT_ID": false}, "raw_comfyui_binding": "not configured"}` |
| `repository_preflight` | **PASS** | `{"chaos_redux": {"exists": true, "head": {"returncode": 0, "stderr": "", "stdout": "420cfb326e8ec78ec5641b152f32fce2b2d94db6"}, "is_git": true, "path": "/Users/klimpaskov/Documents/Paradox Interactive/Hearts of Iron IV/mod/Chaos-Redux", "remote": {"returncode": 0, "stderr": "", "stdout": "origin\tgit@github.com:klimPaskov/Chaos-Redux.git (fetch)\norigin\tgit@github.com:klimPaskov/Chaos-Redux.git (push)"}, "status": {"returncode": 0, "stderr": "", "stdout": "## master...origin/master\n?? docs/ass` |
| `calibrated_identity_thresholds` | **BLOCKED** | `{"approved_by": [], "path": "/Users/klimpaskov/Documents/Projects/comfyui-hoi4-portraits/config/identity_thresholds.json", "present": true, "thresholds_id": "UNSET_BLOCK_EXECUTION"}` |
| `krea_live_compatibility` | **BLOCKED** | `{"reason": "ComfyUI and the pinned Krea custom node are not installed; node signatures and a live Turbo execution are unverified."}` |
| `preprocessing_and_audit_dependencies` | **BLOCKED** | `{"missing_checksums": ["BiRefNet", "DDColor", "YuNet", "MediaPipe Face Landmarker", "SFace"], "path": "/Users/klimpaskov/Documents/Projects/comfyui-hoi4-portraits/dependencies/preprocessing_lock.json"}` |
| `license_and_rights_review` | **BLOCKED_PENDING_PROJECT_OWNER_REVIEW** | `{"blocking_reasons": ["Krea Community License applicability and distribution scope need project-owner approval.", "The approved HOI4 background and its rights record are unresolved.", "The existing style LoRA has an owner-controlled provenance/license record only."], "policy": "A source or model license is not inferred from a model card. Preserve the source URL, retrieval date, exact revision, and the applicable license terms before install or redistribution.", "review_date": "2026-07-26", "sche` |

## Blockers

- PyTorch/MPS and ComfyUI are not installed or MPS capability is not verified; local execution cannot be claimed.
- The approved HOI4 portrait background registry is unresolved; generation and DDS promotion are blocked.
- Required Krea/Qwen model artifacts are not installed and live ComfyUI compatibility has not been verified.
- RunPod endpoint credentials are absent; remote submission/acceptance cannot run.
- No live generic agentic HOI4 target repository was found; only the planning proposal is available.
- Identity/style thresholds are still calibration placeholders; no production candidate may be accepted.
- Krea 2 Turbo compatibility, identity-edit behavior, and the immutable style LoRA matrix have not been measured in the pinned runtime.
- Pinned preprocessing/audit model artifacts have no verified checksums; masking, face analysis, and independent audit cannot run.
- License/rights review is not fully approved for Krea redistribution or the unresolved background.

## Installation decision

No model, node, or runtime installation is authorized while a hard preflight blocker remains.
