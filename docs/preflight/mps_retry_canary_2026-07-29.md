# Mac MPS retry canary — 2026-07-29

Status: **INTERRUPTED_LOCAL_MEMORY_PRESSURE_DURING_KREA_MODEL_LOAD**

The exact live `human_local_mac_16gb` user-facing graph was submitted on the
detected 16 GiB Apple Silicon Mac using the private qualification portrait.
The graph submission, source/preprocessing stages, autoprompter, and Qwen text
encoder load passed. Krea 2 model loading then reduced free unified memory to
approximately `1.07 GiB` before the first sampler step. The bounded run was
interrupted and produced no candidate.

The pinned production model remained the official checksum-verified FP8
artifact. This was a `208x280`, one-step canary only; the public workflow was
not changed to a diagnostic model or a smaller production canvas. ComfyUI was
restarted on loopback after the interruption and returned to a healthy state.

Machine-readable evidence: [`mps_retry_canary_2026-07-29.json`](mps_retry_canary_2026-07-29.json).
