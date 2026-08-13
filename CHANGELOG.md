# Package manifest

This repository contains one current, internally consistent package.

## Release identity

- Version: `1.0.0`
- Public workflows: exactly four
- Model family: distilled FLUX.2 Klein 9B only, in full, FP8, and GGUF forms
- Style adapter: the project's HOI4 style LoRA
- Default style sampler: Euler, simple, four steps, CFG 1, guidance 1, denoise 1
- Restoration: complete Adonis Base → Post graph with one red enable/bypass control
- Shared LoRAs: HOI4 style, Adonis Base, Adonis Refine, and Adonis Post

## Workflow contract

- Source portrait: three style candidates and a five-card comparison row
- Text to image: one sampler and one final portrait
- Batch: per-queue folder rescan, deterministic case-insensitive list input, one sampler, and sequential per-source execution
- Processing only: RealESRGAN plus Adonis Base → Post, without the style LoRA
- Automatic saving: master PNG, game PNG, and DDS branches are terminal outputs with non-overwriting numbered filenames
- Output names: source, processing-only, and batch saves preserve each input image stem; source candidates add `_1`, `_2`, and `_3`
- Layout: four fully visible, compact, colour-coded canvases with portrait-ratio previews
- Output: 1024×1365 PNG, centered 156×210 PNG, and HOI4-ready DDS
- Downloads: independent repositories transfer in parallel at full Xet speed, files from the same repository run sequentially, incomplete Hub downloads resume, and HTTP 429/temporary server failures retry with backoff

## Installation contract

- GGUF for 8–16 GB VRAM, with selectable Q4_K_M/Q5_K_M/Q6_K/Q8_0 quants
- FP8 for 16–20 GB VRAM
- Full distilled weights above 20 GB VRAM
- RunPod defaults to full distilled
- Windows detects NVIDIA VRAM, preselects the matching distilled variant, supports multi-variant installs, finds ComfyUI, installs pinned node packs, and downloads the selected model set

Pinned commits, model revisions, sizes, hashes, and licenses are in [`models.json`](models.json), [`scripts/install_custom_node_packs.py`](scripts/install_custom_node_packs.py), and [`THIRD_PARTY_LICENSES.md`](THIRD_PARTY_LICENSES.md).
