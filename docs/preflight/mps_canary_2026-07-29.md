# Mac MPS canary — 2026-07-29

Status: **BLOCKED_LOCAL_MEMORY_PRESSURE_BEFORE_FIRST_SAMPLER_STEP**

The live `human_local_mac_16gb` graph was run against the loopback ComfyUI
server after correcting the service launch environment. The preprocessing
sidecar was healthy, the human autoprompter stage was reached, the pinned FP8
Krea model was requested, and the run was interrupted before the first sampler
step when the 16 GB unified-memory host reached approximately 10% free memory
with substantial swap activity.

This was a bounded one-step canary at `208x280`; it was not a production
generation run and produced no candidate. The full `832x1120` workflow was not
started after the canary reproduced the known memory/offload failure mode.

The UI/server was restarted once with both preprocessing endpoints configured
on loopback and is left available at `http://127.0.0.1:8188`. The existing CPU
NVFP4 portrait is retained as execution-only diagnostic evidence; it is not
treated as MPS success, production approval, or a final mod asset.

Machine-readable evidence: [`mps_canary_2026-07-29.json`](mps_canary_2026-07-29.json).
