# Package manifest

This repository documents one current, internally consistent package.

## Release identity

- Version: `3.1.0`
- Public workflows: exactly four
- Model family: distilled FLUX.2 Klein 9B only
- Style checkpoint: step 2500 only
- Default sampler: Euler, simple, four steps, CFG 1, guidance 1, denoise 1

## Workflow contract

- Source reference: three live style candidates and a five-card comparison row
- Text to image: one live sampler and one final portrait
- Processing only: RealESRGAN plus exact Adonis Base → Refine, no style LoRA
- Batch: list input, one sampler, sequential per-source execution
- Output: 1024×1365 PNG, centered 156×210 PNG, 156×210 DXT5 DDS with no mipmaps

## Installation contract

- GGUF for 8–16 GB VRAM, with selectable Q4_K_M/Q5_K_M/Q6_K/Q8_0 quants
- FP8 for 16–20 GB VRAM
- Full distilled weights above 20 GB VRAM
- RunPod defaults to full distilled
- Windows detects NVIDIA VRAM, preselects the matching variant, supports
  multi-variant installs, finds ComfyUI, installs pinned node packs, and
  downloads the selected model set

## Exact dependencies

- `calcuis/gguf` for `ClipLoaderGGUF`
- `city96/ComfyUI-GGUF` for GGUF diffusion weights
- `ClownsharkBatwing/RES4LYF` for live Adonis sampling
- `BigStationW/ComfyUi-Scale-Image-to-Total-Pixels-Advanced` for exact Adonis preprocessing

Pinned commits, model revisions, sizes, hashes, and licenses are in
[`models.json`](models.json), [`scripts/install_custom_node_packs.py`](scripts/install_custom_node_packs.py),
and [`THIRD_PARTY_LICENSES.md`](THIRD_PARTY_LICENSES.md).
