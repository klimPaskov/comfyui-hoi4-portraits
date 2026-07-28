# Workflow guide

All four graphs are standalone ComfyUI files generated from the versioned graph specification. Their UI JSON files are for loading into ComfyUI; the `.api.json` files are API-format payloads for the controller and tests.

## Route comparison

| Workflow | Prompt contract | Accelerator | Human controls | Remote auth |
| --- | --- | --- | --- | --- |
| `human_local_mac_16gb` | Exact autoprompter instruction | MPS | Yes | No |
| `human_full_power_gpu` | Exact autoprompter instruction | CUDA | Yes | No |
| `agent_local_mac_16gb` | `portrait_job_input.prompt` | MPS | No | No |
| `agent_remote_runpod` | `portrait_job_input.prompt` | Remote CUDA | No | Yes |

## Shared stages

1. Job and source validation.
2. Deterministic subject selection and head-and-shoulders crop.
3. Conservative preprocessing and foreground-mask preparation.
4. Approved-background and provenance guard.
5. Prompt validation.
6. Krea 2 identity edit and HOI4 style-LoRA route.
7. Bounded candidate generation.
8. Evidence export for independent auditing.

The workflow graph does not silently substitute a missing background, invent provenance, rewrite a rejected prompt, or approve its own output.

## Human workflows

The human profiles call the project autoprompter with the exact instruction in [`prompts/autoprompter_instruction.txt`](../prompts/autoprompter_instruction.txt). The local Mac uses the pinned 4B GGUF sidecar; the full-power route uses the pinned Qwen3-VL 8B BF16 Transformers format and requires CUDA.

Both human graphs now include four read-only `PreviewImage` checkpoints in the final stage panel: crop/reference, prepared reference, approved background, and final candidate. They are there to make human review visible inside ComfyUI; they do not bypass provenance, audit, DDS, or integration gates.

## Agent workflows

The agent profiles contain no autoprompter. The prompt must be present in the validated job contract. A missing or invalid prompt is an input-contract failure, not an invitation to infer one.

## Selection and promotion

Candidates are selected by identity first. Style is evaluated only among identity-eligible candidates. Face swapping is not part of any graph. DDS conversion and mod integration require a separate read-only auditor PASS; a producer cannot create or rank its own approval.
