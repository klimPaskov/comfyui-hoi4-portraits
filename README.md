# HOI4 Portrait Workflows

Open ComfyUI workflows for creating identity-preserving Hearts of Iron IV portrait candidates with Krea 2 Turbo and the project’s style LoRA. The graphs stop before DDS/mod wiring until the independent audit passes.

## Workflows

| Workflow | Runtime | Prompt | Previews |
| --- | --- | --- | --- |
| [`human_local_mac_16gb`](workflows/human/local_mac_16gb/human_local_mac_16gb.json) | Apple Silicon, 16 GB | Built-in autoprompter | Yes |
| [`human_local_nvidia_16gb`](workflows/human/local_nvidia_16gb/human_local_nvidia_16gb.json) | Local NVIDIA, 16 GB | Built-in autoprompter | Yes |
| [`human_full_power_gpu`](workflows/human/full_power_gpu/human_full_power_gpu.json) | ComfyUI Cloud | Built-in autoprompter | Yes |
| [`agent_local_mac_16gb`](workflows/agent/local_mac_16gb/agent_local_mac_16gb.json) | Apple Silicon, 16 GB | Job contract | No |
| [`agent_local_nvidia_16gb`](workflows/agent/local_nvidia_16gb/agent_local_nvidia_16gb.json) | Local NVIDIA, 16 GB | Job contract | No |
| [`agent_full_power_gpu`](workflows/agent/full_power_gpu/agent_full_power_gpu.json) | ComfyUI Cloud | Job contract | No |

Full-power profiles use ComfyUI Cloud; no separate remote deployment is included. Human graphs contain the exact text in [`prompts/autoprompter_instruction.txt`](prompts/autoprompter_instruction.txt); agent graphs contain no autoprompter and read the prompt from the validated job contract.

## Quick start

```bash
git clone https://github.com/klimPaskov/comfyui-hoi4-portraits.git
cd comfyui-hoi4-portraits
```

Follow [`docs/getting-started.md`](docs/getting-started.md), then load a UI JSON into a loopback ComfyUI server at `http://127.0.0.1:8188/`. The 16 GB graphs include visible, disconnected notes for possible 12 GB and 8 GB GGUF routes. They are not enabled until an official model, loader, checksum, license, and live capability qualification exists.

The style LoRA is not stored in Git. Authorized users authenticate to its [private Hugging Face repository](https://huggingface.co/Hoops-McCann/hoi4-portrait-new-style-lora); bootstrap restores the exact pinned revision and verifies its checksum before ComfyUI can load it.

For an existing ComfyUI installation, download the latest Windows `.exe`,
macOS `.dmg`, or portable `.zip` from [Releases](https://github.com/klimPaskov/comfyui-hoi4-portraits/releases).
The packages include [`SETUP_WITH_CODING_AGENT.md`](SETUP_WITH_CODING_AGENT.md)
and a ready-to-copy [agent setup prompt](prompts/install_into_existing_comfyui_agent_prompt.md).
They do not bundle or download ComfyUI.

Full-power profiles are the remote ComfyUI Cloud route. The authenticated Cloud UI now contains all six saved workflows, but execution is **blocked by Cloud node/model parity**: the project custom nodes and required LoRAs are not available there. No run was spent. See [`docs/cloud/comfy_cloud.md`](docs/cloud/comfy_cloud.md) and the [live Cloud probe](docs/preflight/comfy_cloud_ui_probe_2026-07-29.md).

## Safety and scope

- Identity is selected first; face swapping is not used.
- ControlNet is intentionally not included: Krea Edit already supplies image-conditioned identity and geometry guidance, and no approved live experiment shows that an additional ControlNet improves identity-first selection.
- Preview and `SaveImage` in human workflows consume the same evidence-export image.
- No final DDS or mod integration is produced without an independent all-gates PASS.
- `workflows/` and `loras/` are top-level project paths; model weights, source portraits, caches, secrets, and binary artifacts remain excluded from Git. Revisions and checksums are recorded in [`dependencies/models.lock.json`](dependencies/models.lock.json) and [`loras/README.md`](loras/README.md).

## Documentation

- [`docs/workflows.md`](docs/workflows.md) — workflow stages and profile selection.
- [`docs/getting-started.md`](docs/getting-started.md) — local setup and loading.
- [`docs/cloud/comfy_cloud.md`](docs/cloud/comfy_cloud.md) — Cloud authentication, import status, and current blocker.
- [`docs/contracts-and-safety.md`](docs/contracts-and-safety.md) — schemas, gates, and exit codes.
- [`docs/testing-and-evidence.md`](docs/testing-and-evidence.md) — verification and acceptance status.
- [`docs/screenshots.md`](docs/screenshots.md) — close-up UI examples.

![Workflow overview](docs/assets/live_test_2026-07-28/compact_workflow_overview.png)

![Input and prompt stages](docs/assets/live_test_2026-07-28/compact_input_prompt.png)

![Krea, preview, and save stages](docs/assets/live_test_2026-07-28/compact_krea_preview_save.png)

Project-owned code is released under [`LICENSE`](LICENSE). This does not grant rights to third-party models, HOI4 assets, source portraits, or the style LoRA.
