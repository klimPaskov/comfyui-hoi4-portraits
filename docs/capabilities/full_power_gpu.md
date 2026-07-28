# Initial Preflight Report

- Collected: `2026-07-28T13:16:41.672063+00:00`
- Status: **BLOCKED**
- Installation permitted: **False**
- Recommended exit code: `15`

## Gates

| Gate | Status | Evidence summary |
| --- | --- | --- |
| `hardware_detection` | **PASS** | `{"available_tools": {"brew": {"command": "brew", "path": "/opt/homebrew/bin/brew", "present": true, "probe": {"command": ["/opt/homebrew/bin/brew", "--version"], "returncode": 0, "stderr": "", "stdout": "Homebrew 6.0.2"}}, "docker": {"command": "docker", "path": "/usr/local/bin/docker", "present": true, "probe": {"command": ["/usr/local/bin/docker", "--version"], "returncode": 0, "stderr": "", "stdout": "Docker version 29.4.1, build 055a478"}}, "uv": {"command": "uv", "path": "<home>/` |
| `local_runtime_capability` | **BLOCKED** | `{"accelerator_ok": false, "comfy_cli": null, "comfy_runtime_present": true, "host_python_version": "3.12.13", "profile": "human_full_power_gpu", "python_executable": "<project-root>/.venv/bin/python", "python_floor": ">=3.10", "python_floor_ok": true, "python_version": "3.12.13 (main, Apr 14 2026, 14:33:40) [Clang 22.1.3 ]", "required_accelerator": "CUDA", "runtime_probe": {"pydantic": {"installed": true, "version": "2.13.4"}, "pydantic_settings": {"i` |
| `immutable_style_lora` | **PASS** | `{"actual_sha256": "2ad94552d151d2dedf151cf7356cdd3ea07677607ff289fc0ac61534b34dead1", "expected_sha256": "2ad94552d151d2dedf151cf7356cdd3ea07677607ff289fc0ac61534b34dead1", "immutable": true, "path": "<project-root>/loras/hoi4_portrait_new_style_lora.safetensors", "present": true}` |
| `approved_source_background` | **BLOCKED** | `{"candidate_evidence": [{"blocking_findings": ["The local checkout and current primary repository root have no discovered LICENSE, COPYING, or NOTICE record covering this asset.", "descriptor.mod identifies the mod but does not establish background rights or redistribution permission.", "The candidate is a PSD source, not the exact approved runtime background format/path required by the pipeline.", "No project-owner approval or attribution record authorizes use in this standalone pipeline."], "c` |
| `source_fixture_and_provenance` | **BLOCKED** | `{"fixture_files": [], "manifest_template": "<project-root>/tests/fixture_manifest.template.json"}` |
| `planning_package_checksums` | **PASS** | `{}` |
| `model_artifact_preflight` | **PASS** | `{"checks": [{"expected_sha256": "eb4dd8c612cfd10f64f25b057e6e6bbcb5737c94a7372177e456dbf7579502f1", "expected_size_bytes": 13141730784, "format": ".safetensors", "format_supported": true, "name": "krea2_turbo_fp8_scaled.safetensors", "path": "models/diffusion_models/krea2_turbo_fp8_scaled.safetensors", "present": true, "sha256": "eb4dd8c612cfd10f64f25b057e6e6bbcb5737c94a7372177e456dbf7579502f1", "size_bytes": 13141730784, "status": "PASS"}, {"expected_sha256": "54bd5144df0bbc25dd6ccadfcb826b5214` |
| `custom_node_preflight` | **PASS** | `{"checks": [{"actual_revision": "cae442e11b59bcba04ed82f4c01ffe3752531fe1", "class_matches": {"Krea2EditGroundedEncode": true, "Krea2EditModelPatch": true}, "expected_classes": ["Krea2EditGroundedEncode", "Krea2EditModelPatch"], "name": "comfyui-krea2edit", "path": "<project-root>/comfyui/custom_nodes/comfyui-krea2edit", "present": true, "revision": "cae442e11b59bcba04ed82f4c01ffe3752531fe1", "revision_match": true, "signature_files": ["__init__.py", ` |
| `comfyui_runtime_dependency_lock` | **PASS** | `{"checks": [{"actual_sha256": "31c8fe0bd331a681b7d4b291b254869a8cc9ebe12dd3665d621e6001c69fcbd5", "content_ok": true, "expected_sha256": "31c8fe0bd331a681b7d4b291b254869a8cc9ebe12dd3665d621e6001c69fcbd5", "invalid_packages": [], "path": "dependencies/runtime_profiles/linux_amd64_cuda128.lock.txt", "profile_lock": "linux_amd64_cuda128", "status": "PASS"}], "lock_status": "RESOLVED_PROFILE_LOCKS_LIVE_COMPATIBILITY_UNVERIFIED", "mode": "profile_locks", "path": "<home>/Documents/Projects/` |
| `remote_topology_auth` | **NOT_APPLICABLE** | `{"credential_presence": {"GITHUB_TOKEN": false, "HF_TOKEN": false, "PORTRAIT_GATEWAY_TOKEN": false, "RUNPOD_API_KEY": false, "RUNPOD_ENDPOINT_ID": false}, "profile": "human_full_power_gpu", "raw_comfyui_binding": "not configured", "remote_gateway": "authenticated_only"}` |
| `repository_preflight` | **PASS** | `{"chaos_redux": {"exists": true, "head": {"returncode": 0, "stderr": "", "stdout": "420cfb326e8ec78ec5641b152f32fce2b2d94db6"}, "is_git": true, "path": "<external-repository>", "remote": {"returncode": 0, "stderr": "", "stdout": "origin\tgit@github.com:klimPaskov/Chaos-Redux.git (fetch)\norigin\tgit@github.com:klimPaskov/Chaos-Redux.git (push)"}, "status": {"returncode": 0, "stderr": "", "stdout": "## master...origin/master\n?? docs/ass` |
| `calibrated_identity_thresholds` | **BLOCKED** | `{"approved_by": [], "path": "<project-root>/config/identity_thresholds.json", "present": true, "thresholds_id": "UNSET_BLOCK_EXECUTION"}` |
| `krea_live_compatibility` | **PASS** | `{"compatibility_review": {"conclusion": "Krea live core/node/schema compatibility is verified in the pinned loopback runtime and all four workflows are live-schema loadable. This does not establish source-specific model execution or production suitability: the required eight-step run, identity/style experiment matrix, calibrated thresholds, and independent audit remain blocked by missing approved source/background and rights evidence.", "findings": [{"finding": "The primary Krea2EditModelPatch c` |
| `autoprompter_runtime` | **PASS_FORMAT_ONLY_EXECUTION_BLOCKED** | `{"full_power_format_status": "PASS", "instruction_sha256": "01d90630b4e604d43feeb16fe40465c4aa14dec837933a81e5cff4232033c3c8", "local_sidecar_status": "PASS", "lock_path": "dependencies/autoprompter_runtime.lock.json", "lock_status": "PINNED_LOCAL_AND_FULL_POWER_RUNTIME_EXECUTION_UNVERIFIED", "positive_generation_status": "BLOCKED_NO_LEGAL_SOURCE_FIXTURE", "production_prompt_claim": "NOT_CLAIMED", "profile": "human_full_power_gpu", "report_path": "docs/preflight/autoprompter_runtime_test.json", ` |
| `preprocessing_and_audit_dependencies` | **PASS** | `{"checks": [{"artifact_revision": "e2bf8e4460fc8fa32bba5ea4d94b3233d367b0e4", "artifact_url": "https://huggingface.co/ZhengPeng7/BiRefNet/resolve/e2bf8e4460fc8fa32bba5ea4d94b3233d367b0e4/model.safetensors", "expected_sha256": "9ab37426bf4de0567af6b5d21b16151357149139362e6e8992021b8ce356a154", "expected_size_bytes": 444473596, "format": ".safetensors", "format_expected": "safetensors", "format_supported": true, "name": "BiRefNet", "path": "models/preprocessing/birefnet/model.safetensors", "presen` |
| `license_and_rights_review` | **BLOCKED_PENDING_PROJECT_OWNER_REVIEW** | `{"blocking_reasons": ["Krea Community License applicability and distribution scope need project-owner approval.", "The approved HOI4 background and its rights record are unresolved.", "The existing style LoRA has an owner-controlled provenance/license record only."], "policy": "A source or model license is not inferred from a model card. Preserve the source URL, retrieval date, exact revision, and the applicable license terms before install or redistribution.", "review_date": "2026-07-26", "sche` |

## Blockers

- The required CUDA runtime, Python floor, PyTorch capability, or ComfyUI installation is not verified; this profile cannot be claimed executable.
- The approved HOI4 portrait background registry is unresolved; generation and DDS promotion are blocked.
- No legally usable source portrait fixture and complete provenance record is present for calibration or route execution.
- No live generic agentic HOI4 target repository was found; only the planning proposal is available.
- Identity/style thresholds are still calibration placeholders; no production candidate may be accepted.
- Krea 2 source-specific model loading, the eight-step Turbo execution, and the immutable style-LoRA experiment matrix remain unmeasured until an approved fixture, background, and calibrated audit thresholds are available.
- The full-power human autoprompter format is pinned and processor-verified, but target CUDA execution is unavailable on the detected host.
- License/rights review is not fully approved for Krea redistribution or the unresolved background.

## Installation decision

No model, node, or runtime installation is authorized while a hard preflight blocker remains.
