# Krea 2 Compatibility Review

Status: **BLOCKED_EXECUTION_LOCAL_16GB_MEMORY_INFEASIBLE**.

The live pinned runtime now verifies the Krea 2 core and node contract. The
official ComfyUI Krea 2 documentation describes Turbo as an eight-step
distilled checkpoint and recommends the ComfyUI-optimized FP8 diffusion model,
Qwen3-VL 4B text encoder, and Qwen image VAE. The generated graph uses eight
steps, CFG 1, and an `832x1120` work canvas (`0.93 MP`), which is below the
documented 2 MP ceiling. ComfyUI
revision `2a610155821d670a2d8047e654e5fce96b790eb5` exposes `CLIPLoader` with
the `krea2` type required by the primary `comfyui-krea2edit` checkout at
`cae442e11b59bcba04ed82f4c01ffe3752531fe1`. The loopback server imported both
the Krea nodes and the project nodes, and all five configured API workflows matched the
live `/object_info` input registry. The Krea patch receives the VAE and source
image for `fit` mode; grounded encoding is locked to the documented 768-pixel
baseline; and the human/agent prompt split remains intact. The primary node
documentation also identifies `fit` as the v1.2 geometry path and `ref_boost`
as the reference-fidelity control; both are locked in the graph.

The machine-readable live evidence is
`docs/preflight/live_comfy_compatibility.json`. It records the loopback binding,
core revision, ComfyUI/PyTorch versions, node presence, live input schemas, and
all five workflow checks. The model artifact preflight separately records the
required local model files and SHA-256 values.

This is a schema/import and local-capability qualification result, not a
production generation claim. The private user fixture, approved local-copy-only
background, and preprocessing route passed. The first MPS attempt exposed the
FP8 dtype limitation. The project-owned reversible workaround in
`scripts/runtime/apply_mps_fp8_workaround.py` passed that exception site, but
the full-resolution and reduced diagnostic runs exhausted practical unified
memory/offload headroom on the 16 GB Mac before the first sampler step
completed. The experiment matrix, calibrated identity thresholds, and
independent auditor remain blocked, and no PNG/DDS/mod output is permitted.
