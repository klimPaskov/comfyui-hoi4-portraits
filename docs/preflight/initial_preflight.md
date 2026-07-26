# Initial Preflight Report

- Collected: `2026-07-26T15:22:15.524278+00:00`
- Status: **BLOCKED**
- Installation permitted: **False**
- Recommended exit code: `15`

## Gates

| Gate | Status | Evidence summary |
| --- | --- | --- |
| `hardware_detection` | **PASS** | `{"available_tools": {"brew": {"command": "brew", "path": "/opt/homebrew/bin/brew", "present": true, "probe": {"command": ["/opt/homebrew/bin/brew", "--version"], "returncode": 0, "stderr": "", "stdout": "Homebrew 6.0.2"}}, "docker": {"command": "docker", "path": "/usr/local/bin/docker", "present": true, "probe": {"command": ["/usr/local/bin/docker", "--version"], "returncode": 0, "stderr": "", "stdout": "Docker version 29.4.1, build 055a478"}}, "uv": {"command": "uv", "path": "/Users/klimpaskov/` |
| `local_runtime_capability` | **BLOCKED** | `{"accelerator_ok": false, "comfy_cli": null, "comfy_runtime_present": false, "profile": null, "python_floor": ">=3.10", "python_floor_ok": false, "python_version": "3.9.6", "required_accelerator": "MPS", "torch": {"error": "No module named 'torch'", "error_type": "ModuleNotFoundError", "installed": false}}` |
| `immutable_style_lora` | **PASS** | `{"actual_sha256": "2ad94552d151d2dedf151cf7356cdd3ea07677607ff289fc0ac61534b34dead1", "expected_sha256": "2ad94552d151d2dedf151cf7356cdd3ea07677607ff289fc0ac61534b34dead1", "immutable": true, "path": "/Users/klimpaskov/Documents/Projects/comfyui-hoi4-portraits/loras/hoi4_portrait_new_style_lora.safetensors", "present": true}` |
| `approved_source_background` | **BLOCKED** | `{"candidate_evidence": [{"blocking_findings": ["The live repository has no discovered LICENSE or COPYING record covering this asset.", "descriptor.mod identifies the mod but does not establish background rights or redistribution permission.", "The candidate is a PSD source, not the exact approved runtime background format/path required by the pipeline.", "No project-owner approval or attribution record authorizes use in this standalone pipeline."], "candidate_id": "chaos-redux-portrait-leader-ba` |
| `source_fixture_and_provenance` | **BLOCKED** | `{"fixture_files": [], "manifest_template": "/Users/klimpaskov/Documents/Projects/comfyui-hoi4-portraits/tests/fixture_manifest.template.json"}` |
| `planning_package_checksums` | **PASS** | `{}` |
| `model_artifact_preflight` | **BLOCKED** | `{"checks": [{"expected_sha256": "eb4dd8c612cfd10f64f25b057e6e6bbcb5737c94a7372177e456dbf7579502f1", "expected_size_bytes": 13141730784, "format": ".safetensors", "format_supported": true, "name": "krea2_turbo_fp8_scaled.safetensors", "path": "models/diffusion_models/krea2_turbo_fp8_scaled.safetensors", "present": false, "sha256": null, "size_bytes": null, "status": "BLOCKED"}, {"expected_sha256": "54bd5144df0bbc25dd6ccadfcb826b521445a1b06ae5a42570bdd2974ca87094", "expected_size_bytes": 524246796` |
| `custom_node_preflight` | **BLOCKED** | `{"checks": [{"actual_revision": null, "class_matches": {"Krea2EditGroundedEncode": false, "Krea2EditModelPatch": false}, "expected_classes": ["Krea2EditGroundedEncode", "Krea2EditModelPatch"], "name": "comfyui-krea2edit", "path": "/Users/klimpaskov/Documents/Projects/comfyui-hoi4-portraits/comfyui/custom_nodes/comfyui-krea2edit", "present": false, "revision": "cae442e11b59bcba04ed82f4c01ffe3752531fe1", "revision_match": false, "signature_files": [], "signature_match": false, "status": "BLOCKED"}` |
| `comfyui_runtime_dependency_lock` | **PASS** | `{"checks": [{"actual_sha256": "4e45be103d6cf17b882e2824a45cc3a818296ae5ead6b88b622030ba615cfc0b", "content_ok": true, "expected_sha256": "4e45be103d6cf17b882e2824a45cc3a818296ae5ead6b88b622030ba615cfc0b", "invalid_packages": [], "path": "dependencies/runtime_profiles/linux_amd64_cuda128.lock.txt", "profile_lock": "linux_amd64_cuda128", "status": "PASS"}, {"actual_sha256": "5d9aec55d311dc6f7dc2ca8ab8ab219e11fd101600e7664796c4bdfc43a225b5", "content_ok": true, "expected_sha256": "5d9aec55d311dc6f7` |
| `remote_topology_auth` | **BLOCKED** | `{"credential_presence": {"GITHUB_TOKEN": false, "HF_TOKEN": false, "PORTRAIT_GATEWAY_TOKEN": false, "RUNPOD_API_KEY": false, "RUNPOD_ENDPOINT_ID": false}, "profile": null, "raw_comfyui_binding": "not configured", "remote_gateway": "authenticated_only"}` |
| `repository_preflight` | **PASS** | `{"chaos_redux": {"exists": true, "head": {"returncode": 0, "stderr": "", "stdout": "420cfb326e8ec78ec5641b152f32fce2b2d94db6"}, "is_git": true, "path": "/Users/klimpaskov/Documents/Paradox Interactive/Hearts of Iron IV/mod/Chaos-Redux", "remote": {"returncode": 0, "stderr": "", "stdout": "origin\tgit@github.com:klimPaskov/Chaos-Redux.git (fetch)\norigin\tgit@github.com:klimPaskov/Chaos-Redux.git (push)"}, "status": {"returncode": 0, "stderr": "", "stdout": "## master...origin/master\n?? docs/ass` |
| `calibrated_identity_thresholds` | **BLOCKED** | `{"approved_by": [], "path": "/Users/klimpaskov/Documents/Projects/comfyui-hoi4-portraits/config/identity_thresholds.json", "present": true, "thresholds_id": "UNSET_BLOCK_EXECUTION"}` |
| `krea_live_compatibility` | **BLOCKED** | `{"compatibility_review": {"conclusion": "The workflows are structurally delivered but Krea live compatibility is not proven. Installation and generation remain fail-closed until a verified compatible ComfyUI revision/node signature is installed and exercised.", "findings": [{"finding": "The primary Krea2EditModelPatch contract exposes VAE and source_image inputs for fit mode; the generated graph supplies both from the approved composite and Krea VAE.", "id": "krea2edit_fit_inputs", "status": "PA` |
| `preprocessing_and_audit_dependencies` | **BLOCKED** | `{"missing_checksums": ["BiRefNet", "DDColor", "YuNet", "MediaPipe Face Landmarker", "SFace"], "path": "/Users/klimpaskov/Documents/Projects/comfyui-hoi4-portraits/dependencies/preprocessing_lock.json"}` |
| `license_and_rights_review` | **BLOCKED_PENDING_PROJECT_OWNER_REVIEW** | `{"blocking_reasons": ["Krea Community License applicability and distribution scope need project-owner approval.", "The approved HOI4 background and its rights record are unresolved.", "The existing style LoRA has an owner-controlled provenance/license record only."], "policy": "A source or model license is not inferred from a model card. Preserve the source URL, retrieval date, exact revision, and the applicable license terms before install or redistribution.", "review_date": "2026-07-26", "sche` |

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

## Installation decision

No model, node, or runtime installation is authorized while a hard preflight blocker remains.
