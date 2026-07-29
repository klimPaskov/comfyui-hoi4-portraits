# Mac CPU fallback canary — 2026-07-29

Status: **INTERRUPTED_LOCAL_MEMORY_PRESSURE_BEFORE_FIRST_SAMPLER_STEP**

The same human graph was run on an isolated loopback ComfyUI CPU server with
the correct subject, mask, and autoprompter endpoints. The diagnostic-only
override used the checksum-verified NVFP4 Krea 2 artifact at `208x280` for one
sampler step. Source intake, subject selection, crop/reference preparation,
mask/background validation, the exact autoprompter instruction, text-encoder
loading, and Krea model loading all passed.

Before the first sampler step completed, the host reached approximately
11.2 GiB of 12 GiB swap use. The canary was interrupted and the isolated CPU
server was stopped to protect the Mac. No candidate was produced by this run.

This does not change the public `human_local_mac_16gb` graph: it remains pinned
to the FP8 Krea route and fail-closed on Apple MPS. The earlier 832x1120 CPU
NVFP4 portrait remains execution-only diagnostic evidence, not production
approval or final mod output.

Machine-readable evidence: [`cpu_canary_2026-07-29.json`](cpu_canary_2026-07-29.json).
