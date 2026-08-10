# Package manifest

This repository documents one current, internally consistent package.

## Release identity

- Version: `3.1.0`
- Public workflows: exactly four
- Model family: distilled FLUX.2 Klein 9B only
- Style checkpoint: step 2500 only
- Default sampler: Euler, simple, four steps, CFG 1, guidance 1, denoise 1
- Sampling UI: standard ComfyUI `KSampler`; the retired project sampler is not registered
- Setup UI: one narrow dark-brown card with a folder tree and 16 clickable downloads
- Restoration: current upstream Adonis Base → Post graph, with both official
  prompt branches and one red true/false control for the complete restoration
- Shared LoRAs: HOI4 step 2500 plus Adonis Base, Refine, and Post

## Workflow contract

- Source reference: three style candidates and a five-card comparison row
- Source upload: shown once in the loader, with no duplicate preview card
- Text to image: one sampler and one final portrait
- Processing only: RealESRGAN plus complete current Adonis Base → Post, no style LoRA
- Batch: per-queue folder rescan, deterministic case-insensitive list input,
  one sampler, and sequential per-source execution
- Automatic saving: master PNG, game PNG, and DDS branches are terminal
  outputs with non-overwriting numbered filenames
- Layout: compact 40 px node gutters, 80 px group gutters, aligned top-stage
  heights, and tightly packed model/restoration/style sections
- Output: 1024×1365 PNG, centered 156×210 PNG, 156×210 A8R8G8B8 DDS with no mipmaps

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
- `ClownsharkBatwing/RES4LYF` for Adonis Base → Post sampling
- `BigStationW/ComfyUi-Scale-Image-to-Total-Pixels-Advanced` for exact Adonis preprocessing

Pinned commits, model revisions, sizes, hashes, and licenses are in
[`models.json`](models.json), [`scripts/install_custom_node_packs.py`](scripts/install_custom_node_packs.py),
and [`THIRD_PARTY_LICENSES.md`](THIRD_PARTY_LICENSES.md).
