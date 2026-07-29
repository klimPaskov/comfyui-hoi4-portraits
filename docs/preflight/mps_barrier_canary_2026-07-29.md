# Mac MPS staged-load barrier canary — 2026-07-29

Status: **BLOCKED_LOCAL_MEMORY_PRESSURE_BEFORE_FIRST_SAMPLER_STEP**

The exact `human_local_mac_16gb` graph was re-tested after adding the
project-owned `HOI4KreaModelLoadBarrier`. The barrier waits for both grounded
Qwen conditioning branches and uses ComfyUI's device-agnostic release path so
CPU-resident text-encoder models are unloaded before Krea sampling.

The live node registry contained the barrier and the run reached the pinned
official Krea 2 FP8 model-load stage. Even at a bounded `208x280` one-step
canary, the Mac fell to about `1.02 GiB` free RAM and `263.81 MB` free swap
before the first sampler step. The run was interrupted at the safety boundary;
it produced no candidate and no final output.

This is a measured local capacity result, not a missing-node or schema result.
The barrier remains in all workflow variants because it correctly implements
the planning package's staged load/unload order. It does not make the FP8 MPS
route production-capable, and the earlier CPU fallback remains diagnostic-only.

Machine-readable evidence: [`mps_barrier_canary_2026-07-29.json`](mps_barrier_canary_2026-07-29.json).
