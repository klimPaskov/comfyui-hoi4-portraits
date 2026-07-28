# Full-Power GPU Profile

## Goal

Provide the highest practical quality while preserving parity with the local graph and keeping identity as the first gate.

## Hardware classes

| Class | Intended use | Status |
| --- | --- | --- |
| 24 GB NVIDIA | reduced experimental profile, FP8 and one candidate at a time | not full power |
| 32 GB NVIDIA | intermediate qualification, limited 32B VLM use | optional |
| 48 GB NVIDIA | cost-qualified default for production | recommended starting class |
| 80 GB NVIDIA | reference full-power profile and full experiment matrix | preferred reference |
| 94 GB or 141 GB | diagnostics, larger VLM qualification, or controlled concurrency | optional, cost-gated |

GPU memory class does not authorize batch concurrency. Run one portrait job per GPU until profiling proves a safe concurrency plan.

## Image profile

- Working and generation canvas: 1196 by 1610, 1.926 megapixels
- Candidate count: 6
- Batch size: benchmark 1 and 2, choose the stable value
- Krea Turbo: full or official high-quality precision that passes the model comparison
- Identity adapter: full v1.2 default after qualification
- Krea steps: 8, 10, or 12, with 10 as initial normal default
- CFG: 1.0
- Sampler and scheduler baseline: Euler and simple
- `grounding_px`: qualify 768 and 1024
- `ref_boost`: qualified likeness setting around the documented starting point of 4
- Two-pass style denoise: selected from the measured 0.10 to 0.30 sweep

## Autoprompter

The human full-power workflow uses Qwen3-VL 8B first. The model runs before Krea and unloads. Benchmark a 32B model only on 80 GB or larger hardware and only when it improves format compliance or unsupported-claim rejection materially.

## Quality operations

Full power can add:

- higher-quality matting refinement
- larger face and mask audit crops
- more candidates
- full identity adapter
- a complete route comparison experiment
- repeated-seed validation
- expanded 8x comparison sheets

It cannot add:

- face swapping
- a different generated face
- unbounded restoration
- invented clothing or decorations
- a larger style strength that lowers identity acceptance
- a second model base without explicit approval

## Memory plan

Profile and record:

- model weight residency
- CUDA allocation and reservation
- peak activation memory
- host RAM use
- load and unload time
- candidate batch size
- audit model residency

Load the VLM, matting, colorization, Krea, and audit models in stages unless the selected GPU class can hold them without affecting determinism or cost. Staging remains preferred because it gives parity with local operation.

## Acceptance

A full-power profile passes when:

- the full model and identity adapter load from locked files
- all four workflow stages execute without manual repair
- six candidates can be generated within the cost and runtime budget
- at least the calibrated pass-rate target is met on the acceptance set
- no identity stratum falls below its minimum pass rate
- peak VRAM stays under the selected safety limit
- a clean second Pod reproduces the workflow from manifests
- the same workflow commit can run locally with its local overlay
