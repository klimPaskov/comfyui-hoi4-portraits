# Workflow guide

The required four graphs plus the local-NVIDIA agent convenience graph are standalone ComfyUI files generated from the versioned graph specification. Their UI JSON files are for loading into ComfyUI; the `.api.json` files are API-format payloads for the controller and tests.

## Route comparison

| Workflow | Prompt contract | Accelerator | Human controls | Remote auth |
| --- | --- | --- | --- | --- |
| `human_local_mac_16gb` | Exact autoprompter instruction | MPS | Yes | No |
| `human_full_power_gpu` | Exact autoprompter instruction | CUDA | Yes | No |
| `agent_local_mac_16gb` | `portrait_job_input.prompt` | MPS | No | No |
| `agent_full_power_gpu` | `portrait_job_input.prompt` | Local CUDA | No | No |
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

The workflow graph does not silently substitute a missing background, invent provenance, rewrite a rejected prompt, or approve its own output. On the detected 16 GB Mac, the live qualification run measured the locked FP8 checkpoint's MPS dtype failure, then measured the remaining memory/offload infeasibility after the reversible CPU-dequantization workaround. The Mac profile remains blocked for practical generation; the NVIDIA profiles require a CUDA host.

## Human workflows

The human profiles call the project autoprompter with the exact instruction in [`prompts/autoprompter_instruction.txt`](../prompts/autoprompter_instruction.txt). The local Mac uses the pinned 4B GGUF sidecar; the full-power route uses the pinned Qwen3-VL 8B BF16 Transformers format and requires CUDA.

Both human graphs now include four read-only `PreviewImage` checkpoints in the final stage panel: crop/reference, prepared reference, approved background, and final candidate. The final checkpoint is wired to the same evidence-export image as `SaveImage`, so the visible preview is exactly the image being saved. They do not bypass provenance, audit, DDS, or integration gates.

## Agent workflows

The agent profiles contain no autoprompter. The prompt must be present in the validated job contract. A missing or invalid prompt is an input-contract failure, not an invitation to infer one.

## Selection and promotion

When an approved private role-specific visual reference manifest is available, run the separate auditor with `--visual-reference-manifest <private-job-root>/references/manifest.json`. The auditor starts the pinned loopback Qwen rubric runtime, verifies every reference checksum, terminates that model process, and then recomputes the full audit. Missing or unapproved reference sets leave the visual gates `UNCERTAIN`; they never authorize thresholds or promotion.

For a verified CUDA host, add `--visual-runtime-profile full_power_gpu`; that route uses the pinned Qwen3-VL-8B Transformers/BF16 lock and fails closed when CUDA is unavailable.

```text
.venv/bin/python scripts/audit_candidate.py \
  --job-root <private-job-root> \
  --candidate-id candidate-000 \
  --source-master <private-job-root>/evidence/source/master.png \
  --processed-reference <private-job-root>/evidence/reference/processed.png \
  --candidate <private-job-root>/candidates/candidate-000.png \
  --mask <private-job-root>/evidence/mask/candidate-000.png \
  --manifest <private-job-root>/manifest.json \
  --producer-process-id <producer-process-id> \
  --output <private-job-root>/audit/candidate-000.json \
  --visual-reference-manifest <private-job-root>/references/manifest.json
```

Candidates are selected by identity first. Style is evaluated only among identity-eligible candidates. Face swapping is not part of any graph. DDS conversion and mod integration require a separate read-only auditor PASS; a producer cannot create or rank its own approval.
