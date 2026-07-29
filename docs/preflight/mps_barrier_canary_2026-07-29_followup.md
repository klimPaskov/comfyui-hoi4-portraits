# Mac model-release barrier follow-up — 2026-07-29

Status: **BLOCKED_LOCAL_MEMORY_PRESSURE_DURING_KREA_MODEL_LOAD**

The project-owned `HOI4KreaModelLoadBarrier` was corrected to call
ComfyUI's device-aware `unload_all_models()` path. The exact user-facing
`human_local_mac_16gb` graph was restarted and submitted on loopback with a
private qualification portrait. A bounded diagnostic override used `208x280`
and one Turbo step; the checked-in production workflow remained unchanged at
`832x1120`, eight steps, and the official FP8 artifact.

The retry reached the Qwen text-encoder load and the Krea model-load request,
but Krea materialization remained in heavy system swap and never reached the
first sampler step. The host monitor observed a minimum available-memory
sample of approximately `0.90 GiB` and a peak swap-used sample of
approximately `22.4 GiB` during the bounded attempt. The global ComfyUI
interrupt was received, but the blocking model load did not return promptly;
ComfyUI was terminated and restarted to restore a healthy loopback service.

No candidate, DDS, or mod integration artifact was created or promoted. This
fix improves staged release correctness but does not establish a practical
16 GiB Mac Krea route.

Machine-readable evidence: [`mps_barrier_canary_2026-07-29_followup.json`](mps_barrier_canary_2026-07-29_followup.json).
