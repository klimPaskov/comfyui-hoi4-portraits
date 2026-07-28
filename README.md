# ComfyUI HOI4 Portraits

Fail-closed, auditable ComfyUI workflows for turning an attributed portrait source into a Hearts of Iron IV portrait.

The project separates image generation from acceptance. ComfyUI owns the model graph; the project-owned controller validates the job, records provenance, checks masks and geometry, runs an independent identity/style audit, and refuses DDS or mod promotion unless every hard gate passes.

## Current status

The four workflow files are present and live-schema loadable in the pinned ComfyUI checkout. The local Mac runtime, preprocessing sidecar, autoprompter validation, model locks, and workflow contracts are installed and verified.

Production generation is intentionally still gated. The current acceptance report is **BLOCKED (exit code 15)** because the available source is qualification-only (not production-authorized), the background rights record is unresolved, production thresholds are uncalibrated, RunPod credentials/image qualification are unavailable, and applicable model/source licenses still need owner review. A schema/UI test and local preprocessing qualification are safe; a production portrait claim is not.

## Start here

1. [Getting started](docs/getting-started.md) — install the pinned private qualification runtime and open ComfyUI.
2. [Workflow guide](docs/workflows.md) — choose the correct human or agent route.
3. [Contracts and safety](docs/contracts-and-safety.md) — job schemas, audit gates, and exit codes.
4. [Testing and evidence](docs/testing-and-evidence.md) — reproduce the checks and understand the current blockers.
5. [Licensing and public-repository policy](docs/licensing-and-public-repository.md).
6. [Screenshots](docs/screenshots.md) — sanitized workflow, input-contract, and blocked-output examples.

## The four workflows

| Workflow | Prompt source | Intended runtime | File |
| --- | --- | --- | --- |
| `human_local_mac_16gb` | Exact autoprompter instruction | Apple Silicon MPS / 16 GB Mac | [`human_local_mac_16gb.json`](workflows/human/local_mac_16gb/human_local_mac_16gb.json) |
| `human_full_power_gpu` | Exact autoprompter instruction | CUDA full-power GPU | [`human_full_power_gpu.json`](workflows/human/full_power_gpu/human_full_power_gpu.json) |
| `agent_local_mac_16gb` | Job contract | Apple Silicon MPS / 16 GB Mac | [`agent_local_mac_16gb.json`](workflows/agent/local_mac_16gb/agent_local_mac_16gb.json) |
| `agent_remote_runpod` | Job contract | Authenticated remote gateway / RunPod | [`agent_remote_runpod.json`](workflows/agent/remote_runpod/agent_remote_runpod.json) |

The human graphs contain [`prompts/autoprompter_instruction.txt`](prompts/autoprompter_instruction.txt). The agent graphs contain no autoprompter node and accept the prompt only through the normative job contract.

Human graphs also include four read-only `PreviewImage` checkpoints so a reviewer can inspect the crop/reference, prepared reference, approved background, and final candidate directly in ComfyUI. These previews do not bypass any safety or promotion gate.

## Public-repository boundary

This repository contains code, workflow graphs, schemas, locks, documentation, and redacted evidence. It does not contain source portraits, generated portraits, model weights, caches, secrets, or the private immutable style LoRA. The `.gitignore` policy is deliberately conservative; do not force-add private artifacts.

Krea 2 and third-party artifacts remain subject to their original licenses and terms. Read [the licensing guide](docs/licensing-and-public-repository.md) before downloading or redistributing anything.

## Pinned implementation

- ComfyUI commit: `2a610155821d670a2d8047e654e5fce96b790eb5`
- `comfyui-krea2edit` commit: `cae442e11b59bcba04ed82f4c01ffe3752531fe1`
- Project dependency closure: [`dependencies/project_requirements.lock.txt`](dependencies/project_requirements.lock.txt)
- Model revisions and SHA-256 values: [`dependencies/models.lock.json`](dependencies/models.lock.json)
- Workflow manifest: [`manifests/workflow_manifest.json`](manifests/workflow_manifest.json)

## Safety boundary

There is no face-swapping route. Identity is selected before style ranking. Final PNG/DDS/mod integration is prohibited unless a separate read-only auditor returns PASS for identity, geometry, expression, accessories, foreground/mask integrity, style, and provenance.

## License

Project-owned source is released under the license in [`LICENSE`](LICENSE). That license does not grant rights to bundled third-party models, the private LoRA, source portraits, HOI4 assets, or Krea 2. See [licensing and public-repository policy](docs/licensing-and-public-repository.md).
