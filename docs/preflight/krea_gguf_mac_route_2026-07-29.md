# Krea GGUF Mac route review

Status: **BLOCKED — no approved Krea GGUF route in the current production contract.**

The request was to try a smaller, roughly 12 GB GGUF so the human Mac workflow could run with less memory pressure. The live ComfyUI 0.25.0 registry currently exposes the pinned Krea safetensors models only:

- `krea2_turbo_fp8_scaled.safetensors`
- `krea2_turbo_nvfp4.safetensors`
- `qwen3vl_4b_fp8_scaled.safetensors` as the Krea text encoder

The official Comfy-Org Krea 2 repository also lists safetensors diffusion files rather than a Krea diffusion GGUF. Its official INT8 and MXFP8 Turbo artifacts are about 13.5 GB; its 7.67 GB NVFP4 artifact is already checksum-verified but fails Apple-MPS dequantization in the live workflow. The existing evidence remains in [`krea_precision_options_2026-07-28.json`](krea_precision_options_2026-07-28.json) and [`mps_retry_canary_2026-07-29.json`](mps_retry_canary_2026-07-29.json).

A community repository does publish smaller Krea GGUF quantizations. Those files require a separate GGUF loader surface and the repository's example is a generic text-to-image graph. It is not the pinned Krea2 identity-edit graph used by this project, and it has not been downloaded, checksum-verified, or live-qualified here. The planning package explicitly treats an unverified Krea GGUF/NF4 as forbidden, so it was not installed and the four production workflows were not changed.

This is a deliberate fail-closed result. The current Mac ComfyUI remains running on loopback, and the existing CPU NVFP4 candidate remains diagnostic-only; no final portrait, DDS, or mod integration is authorized. A community-GGUF experiment would need an explicit, separately labeled scope change and could not be called the production workflow without a new identity/style qualification matrix and independent audit.

Machine-readable evidence: [`krea_gguf_mac_route_2026-07-29.json`](krea_gguf_mac_route_2026-07-29.json).
