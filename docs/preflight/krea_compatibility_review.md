# Krea 2 Compatibility Review

Status: **BLOCKED_EXECUTION_NOT_MEASURED**.

The live pinned runtime now verifies the Krea 2 core and node contract. ComfyUI
revision `2a610155821d670a2d8047e654e5fce96b790eb5` exposes `CLIPLoader` with
the `krea2` type required by the primary `comfyui-krea2edit` checkout at
`cae442e11b59bcba04ed82f4c01ffe3752531fe1`. The loopback server imported both
the Krea nodes and the project nodes, and all four API workflows matched the
live `/object_info` input registry. The Krea patch receives the VAE and source
image for `fit` mode; grounded encoding is locked to the documented 768-pixel
baseline; and the human/agent prompt split remains intact.

The machine-readable live evidence is
`docs/preflight/live_comfy_compatibility.json`. It records the loopback binding,
core revision, ComfyUI/PyTorch versions, node presence, live input schemas, and
all four workflow checks. The model artifact preflight separately records the
required local model files and SHA-256 values.

This is a schema/import qualification result, not a production generation
claim. No approved source fixture, approved background, calibrated identity
thresholds, or independent auditor evidence is available. Consequently model
loading and the required eight-step Turbo identity-edit execution were not
attempted, the experiment matrix remains blocked, and no PNG/DDS/mod output is
permitted.
