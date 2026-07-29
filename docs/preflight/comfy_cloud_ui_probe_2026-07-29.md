# ComfyUI Cloud live UI probe — 2026-07-29

Status: **BLOCKED_CLOUD_NODE_MODEL_PARITY**

The authenticated Cloud workspace showed `5 / 5 runs left`. OAuth was configured for `https://cloud.comfy.org/mcp`, but this already-running Codex task did not expose a callable Comfy Cloud MCP tool, so the signed-in Cloud UI was used for the read-only import/parity probe.

All six profile workflows were imported and saved under their profile IDs. No Cloud run was submitted and no run credit was spent.

The human full-power graph immediately reported three errors. Cloud identified one unsupported custom-node pack containing the project-owned `HOI4*` nodes and `Krea2Edit*` nodes, plus two missing LoRA models:

- `hoi4_portrait_new_style_lora.safetensors` — the immutable project LoRA.
- `krea2_identity_edit_v1_2.safetensors` — the pinned identity-edit adapter.

Cloud did resolve its installed Krea/Qwen base assets, but that does not satisfy project node/model parity. The agent full-power graph also reported three errors and was not submitted. Source upload, job-contract delivery, output download, identity/style experiments, auditing, DDS export, and mod wiring were therefore not attempted.

The Cloud Model Library import action returned **“This feature is only available with Creator or Pro plans.”** The official Cloud import documentation also limits model import to supported Civitai/Hugging Face links and states that local-drive upload is not currently supported. The project LoRA remains local and immutable; it is not copied into Git or uploaded through an unverified route.

Evidence is machine-readable in [`comfy_cloud_ui_probe_2026-07-29.json`](comfy_cloud_ui_probe_2026-07-29.json). The next valid attempt requires a Cloud-supported installation path for the project node pack, approved access to both pinned LoRAs, and a fresh MCP/API-capable task or verified Cloud API credentials. Do not spend a run until those checks pass.
