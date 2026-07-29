# Local Krea 2 capability report

Status: `MPS_PRODUCTION_BLOCKED_CPU_EXECUTION_ONLY`

This report records the measured result on the detected Apple Silicon Mac with
16 GiB unified memory. It does not relabel the CPU fallback as a successful
16 GB Mac production route.

## Host and locked runtime

- macOS 26.5.2, arm64, 10 cores, 16 GiB unified memory
- PyTorch 2.11.0 with MPS available
- ComfyUI `2a610155821d670a2d8047e654e5fce96b790eb5`
- `comfyui-krea2edit` `cae442e11b59bcba04ed82f4c01ffe3752531fe`
- required canvas: 832×1120, eight Turbo steps, CFG 1.0, Euler/simple
- production workflow remains locked to the official FP8 model

## Tested approved model routes

| Route | Result | Evidence |
| --- | --- | --- |
| Official Krea 2 Turbo FP8 on native MPS | blocked | Float8 MPS failure at the sampler path |
| Official Krea 2 Turbo FP8 with the documented local dtype workaround | blocked | full-size and reduced diagnostic runs exhausted practical memory/offload headroom before the first sampler step |
| Official Krea 2 Turbo NVFP4 on native MPS | blocked | live loader reached KSampler, then failed with `Undefined type Float8_e4m3fn`; NVFP4 requires the approved NVIDIA capability path |
| Official NVFP4 on CPU, diagnostic substitution only | execution pass | one complete 832×1120 human route, eight steps, 34:36, heavy swap observed |

The graph now includes a project-owned `HOI4KreaModelLoadBarrier` that releases
CPU-resident Qwen conditioning models before Krea sampling. The live barrier
canary passed node/schema loading and reached Krea model loading, but still
blocked before the first sampler step at approximately 1.02 GiB free RAM and
263.81 MB free swap on a bounded 208×280 canary. See the
[`staged-load barrier evidence`](../preflight/mps_barrier_canary_2026-07-29.md).

The official artifacts were checksum-verified before testing. No repacked or
unapproved model format was substituted into the production graph.

## Current official-source check — 2026-07-29

The current `main` revision of [Krea AI's official Krea 2 inference
repository](https://github.com/krea-ai/krea-2/tree/db3984fbc6e13b34c0064990fc2d95ac64d00058)
builds the 12B pipeline with a CUDA device default and moves the DiT, VAE, and
Qwen encoder to that device. The [official Krea 2 Turbo model
card](https://huggingface.co/krea/Krea-2-Turbo) contains a generic library
snippet mentioning MPS, but it does not provide a verified Apple route for the
ComfyUI Krea 2 Identity Edit nodes, staged offload, or the required style-LoRA
workflow. That note therefore does not override the measured ComfyUI/MPS
failure above.

## Conclusion

The approved Krea 2 production route is not currently feasible on this Mac's
MPS backend at the locked canvas. The CPU route can execute the graph, but its
runtime and swap behavior do not meet the local production acceptance gates:
two consecutive full jobs, memory/swap limits, and an all-PASS independent
identity/style audit are still missing. The generated CPU candidate remains a
private diagnostic artifact and cannot be promoted to final PNG, DDS, or mod
integration output.

The following local capabilities remain usable:

- loopback ComfyUI UI and API on `127.0.0.1`
- human and agent workflow graph loading and schema validation
- source intake, preprocessing, prompting, validation, auditing, and evidence export
- CPU execution for diagnostic qualification with the pinned official artifact

Re-test this report only after a primary source verifies an Apple-compatible
Krea format/loader or the host's available memory changes materially.
