# Mac 16 GB Execution Profile

## Position

This profile is an implementation hypothesis that must be measured on the actual Mac. It does not claim that the complete Krea 2 stack already fits in 16 GB unified memory.

The observed model-file budget is already difficult:

- Krea 2 Turbo FP8 model: about 13.1 GB
- Krea Qwen encoder FP8: about 5.24 GB
- Qwen image VAE: about 0.254 GB
- identity edit r64: about 0.46 GB, or r128 at about 0.91 GB
- HOI4 style LoRA: unknown until inspected
- activations, temporary tensors, masks, image buffers, Python, ComfyUI, macOS, and audit models: additional memory

Fully resident FP8 weights exceed 19 GB before the style LoRA and activations. Local success therefore depends on verified staged loading, offload, compatible reduced formats, and memory-efficient execution. It may fail objectively.

## Hardware preflight

The bootstrap agent records:

- exact Mac model identifier
- Apple chip family and GPU core count
- macOS version and build
- total and currently available unified memory
- free disk space on the project and cache volumes
- APFS free and purgeable space
- thermal state and power mode
- Python and Git availability
- MPS availability through PyTorch
- swap baseline before launch

Write the result to `docs/capability_reports/mac_preflight.json` and `.md`.

## Installation profile

Use a dedicated project environment. Preferred order:

1. Install or pin a supported Python through the project bootstrap method.
2. Install a pinned `comfy-cli` or clone a pinned ComfyUI commit into `repos/comfyui`.
3. Create a dedicated ComfyUI workspace inside the project.
4. Enable current Manager with the supported flag for inventory and human maintenance.
5. Install the project custom-node pack from the local source tree.
6. Clone `comfyui-krea2edit` at the selected commit.
7. Install only dependency-lock entries.
8. Restore models from the model lock into exact directories.
9. Start ComfyUI on `127.0.0.1` with no public listener.

Do not require the user to click through installation. Desktop may be installed as an optional launcher after the headless workspace passes.

## Model-format qualification order

Test only formats that have a primary source and a live ComfyUI loader:

1. Official Krea 2 Turbo FP8 scaled on MPS with staged loading.
2. Official INT8 convrot only when ComfyUI and MPS report support.
3. Official NVFP4 only when the loader and MPS kernels report support.
4. Any future official Mac-targeted Krea model only after source, license, checksum, and quality verification.

Do not assume NVFP4, MXFP8, GGUF, or NF4 runs on Apple Silicon because a weight file exists. Do not obtain a repack from a mirror.

For the identity edit adapter, test full v1.2, r128, and r64. A reduced adapter is accepted only when its identity metrics and independent audit pass rate are non-inferior within the locked tolerance.

## Image profile

- Crop ratio: 26:35
- Working canvas: 832 by 1120
- Generation canvas: 832 by 1120
- Candidate count: 2
- Candidate batch size: 1 unless measured memory proves batch 2 is stable
- Krea steps: 8 or 10 normal, 12 only after benchmark
- CFG: 1.0
- Sampler: Euler baseline
- Scheduler: simple baseline
- `grounding_px`: test 512 and 768 first, then 1024 only when memory and quality permit
- `ref_boost`: use the experiment-selected identity-safe value, with 4 as the documented starting point
- Upscale: deterministic Lanczos to working resolution, optional qualified tiled Real-ESRGAN only before generation
- Final resize: deterministic to 156 by 210

## Load and unload order

1. Decode, face analysis, crop, and deterministic measurements.
2. Load colorization only for a `MONOCHROME` source, save output, unload, force garbage collection, and record memory release.
3. Load matting model, save masks, unload, and record memory release.
4. Launch the Qwen3-VL 4B GGUF sidecar, create the autoprompt for human jobs, stop the sidecar, and verify its process exited.
5. Load Krea Qwen encoder and VAE.
6. Load Krea Turbo, identity adapter, and style LoRA through the qualified order.
7. Generate one candidate at a time.
8. Save and unload the Krea stack.
9. Run audit models and final comparisons.

The controller refuses to start the next stage when the previous stage has not released enough memory under the calibrated safety margin.

## Attention and offload

Use ComfyUI and PyTorch attention implementations that are verified on the pinned MPS build. Record the actual implementation. Do not claim xFormers, FlashAttention, CUDA attention, or pinned-memory features on Mac unless the live stack supports them.

Offload can use CPU and unified memory only through verified ComfyUI options. Record model load and unload events and process resident memory. Avoid keeping the autoprompter and Krea stacks resident together.

## Memory and runtime acceptance

The pre-implementation engineering estimate is high memory pressure, likely near the physical 16 GB limit with possible swap. It is not a measured promise.

Local generation PASS requires:

- no process crash or kernel panic
- no unhandled MPS out-of-memory error
- no sustained memory-pressure state that makes the machine unusable
- swap growth within the benchmark limit chosen after preflight
- two consecutive fixture runs without manual restart
- output quality that passes the same identity and style gates as remote
- complete model unload between jobs

Record peak resident memory, system memory pressure, swap delta, stage timings, thermal state, and power source. Expected runtime must come from the benchmark report, not this plan.

## OOM recovery ladder

For one job, apply at most these steps in order:

1. free ComfyUI models through the verified server route
2. terminate the VLM sidecar and optional model processes
3. restart the ComfyUI process once
4. lower candidate batch to one
5. use the qualified reduced identity adapter
6. lower working canvas to the next tested 26:35 size, with 780 by 1050 as the minimum qualification candidate
7. disable optional ML upscale and use Lanczos
8. stop and return exit code 30

Do not loop endlessly or silently submit remotely.

## Local infeasibility report

If all approved local variants fail, create `docs/capability_reports/local_krea_infeasible.md` with:

- hardware and software inventory
- every tested model format
- exact failure stage and error
- peak memory and swap
- working resolutions
- output quality if a partial run completed
- why no remaining approved format can be tested
- preserved local capabilities
- remote fallback instructions

The local workflow stays in the repository as an unpassed experimental profile. Completion reporting must say that local generation did not pass.
