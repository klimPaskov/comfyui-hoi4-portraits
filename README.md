# ComfyUI HOI4 Portrait Workflows

Five standalone ComfyUI graphs for turning a portrait source into an auditable Hearts of Iron IV portrait candidate.

The pipeline preserves identity, uses Krea 2 identity editing plus the project’s immutable style LoRA, and stops before DDS/mod wiring unless the independent audit passes identity, geometry, expression, accessories, mask integrity, style, and provenance. There is no face-swapping route.

## Choose a workflow

| Workflow | Use it on | Prompt | Human previews |
| --- | --- | --- | --- |
| [`human_local_mac_16gb`](workflows/human/local_mac_16gb/human_local_mac_16gb.json) | Apple Silicon, 16 GB | Autoprompter | Yes |
| [`human_full_power_gpu`](workflows/human/full_power_gpu/human_full_power_gpu.json) | Local NVIDIA CUDA | Autoprompter | Yes |
| [`agent_local_mac_16gb`](workflows/agent/local_mac_16gb/agent_local_mac_16gb.json) | Apple Silicon, 16 GB | Job contract | No |
| [`agent_full_power_gpu`](workflows/agent/full_power_gpu/agent_full_power_gpu.json) | Local NVIDIA CUDA | Job contract | No |
| [`agent_remote_runpod`](workflows/agent/remote_runpod/agent_remote_runpod.json) | Authenticated remote CUDA | Job contract | No |

Human graphs contain the exact instruction in [`prompts/autoprompter_instruction.txt`](prompts/autoprompter_instruction.txt). Agent graphs contain no autoprompter and accept the prompt only from the job contract.

## Quick start

```bash
git clone https://github.com/klimPaskov/comfyui-hoi4-portraits.git
cd comfyui-hoi4-portraits
```

Read [`docs/getting-started.md`](docs/getting-started.md), install the pinned private runtime, start the loopback services, and drag one workflow JSON onto the ComfyUI canvas at `http://127.0.0.1:8188/`.

Human workflows show four checkpoints: crop/reference, prepared reference, approved background, and the exact image shared by the final preview and `SaveImage`.

## Current qualification status

The pinned graphs are structurally valid and load against the live local ComfyUI node registry. The detected Mac server is healthy and the automated suite is 34/34. The default Apple-MPS Krea paths remain blocked: FP8 hits the measured MPS dtype/memory limits and NVFP4 fails its MPS dequantization capability check. A diagnostic CPU-only NVFP4 fallback did complete the exact human/autoprompter route at 832×1120 for eight Turbo steps in 34:36 and produced a private candidate, but heavy swap, missing two-run benchmarks, unapproved thresholds, and an `UNCERTAIN` independent audit keep production acceptance blocked. No final PNG, DDS, or mod integration output is claimed. See the [acceptance report](docs/acceptance/acceptance_report.md) and [precision qualification](docs/preflight/krea_precision_options_2026-07-28.md).

## Workflow screenshots

Close-up UI captures are indexed in [`docs/screenshots.md`](docs/screenshots.md).

![Compact workflow overview](docs/assets/live_test_2026-07-28/compact_workflow_overview.png)

![Compact input and prompt stages](docs/assets/live_test_2026-07-28/compact_input_prompt.png)

![Compact Krea, preview, and save stages](docs/assets/live_test_2026-07-28/compact_krea_preview_save.png)

## Documentation

- [`docs/getting-started.md`](docs/getting-started.md) — installation and local startup.
- [`docs/workflows.md`](docs/workflows.md) — stage-by-stage workflow guide.
- [`docs/contracts-and-safety.md`](docs/contracts-and-safety.md) — schemas, gates, and exit codes.
- [`docs/screenshots.md`](docs/screenshots.md) — close-up screenshots and captions.
- [`docs/testing-and-evidence.md`](docs/testing-and-evidence.md) — tests and acceptance evidence.
- [`docs/planning/`](docs/planning/) — the numbered planning package and checksum-verified design records.

## Public/private boundary

Source portraits, generated portraits, model weights, caches, secrets, and the private immutable style LoRA are intentionally excluded from Git. Model revisions and checksums are recorded in [`dependencies/models.lock.json`](dependencies/models.lock.json). See [`docs/licensing-and-public-repository.md`](docs/licensing-and-public-repository.md) before installing private artifacts.

Project-owned code is released under [`LICENSE`](LICENSE). That license does not grant rights to Krea 2, ComfyUI, HOI4 assets, private portraits, or the style LoRA.
