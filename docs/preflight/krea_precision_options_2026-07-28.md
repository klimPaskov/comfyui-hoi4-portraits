# Krea precision qualification — 2026-07-28

The detected machine is an arm64 Mac with 16 GiB unified memory and Apple MPS. Both the official ComfyUI Krea 2 FP8 and lower-storage NVFP4 artifacts were checksum-verified before testing.

## Results

- FP8 loaded and reached the sampler only after the reversible `scripts/runtime/apply_mps_fp8_workaround.py` fallback removed the original Float8-to-MPS exception. Full-resolution and reduced diagnostic runs then stopped under practical memory/offload pressure before the first sampler step completed.
- NVFP4 loaded through `UNETLoader` and reached `KSampler`, but the live MPS run failed at NVFP4 dequantization with `Undefined type Float8_e4m3fn`. The official hardware policy for this artifact requires NVIDIA Blackwell SM>=10; it is not a supported Apple-MPS fallback.
- Preprocessing, approved-background resolution, prompt validation, identity-edit conditioning, and the immutable LoRA checks passed for the private qualification fixture.

The measured result is `BLOCKED_LOCAL_16GB_MPS_KREA_EXECUTION`. No generated after portrait was produced, so no candidate audit, DDS, or mod integration was created.

Machine-readable evidence is in [`krea_precision_options_2026-07-28.json`](krea_precision_options_2026-07-28.json). The official artifacts and compatibility references are the [Comfy-Org Krea 2 repository](https://huggingface.co/Comfy-Org/Krea-2), [Krea 2 model card](https://huggingface.co/krea/Krea-2), and [Krea inference code](https://github.com/krea-ai/krea-2).
