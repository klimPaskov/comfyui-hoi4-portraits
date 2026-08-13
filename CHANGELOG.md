# Package manifest

This repository contains one current, internally consistent package.

## Release identity

- Version: `1.0.0`
- Public workflows: exactly four
- Model family: distilled FLUX.2 Klein 9B only, in full, FP8, and GGUF forms
- Style adapter: the project's HOI4 style LoRA
- Default style sampler: Euler, simple, four steps, CFG 1, guidance 1, denoise 1
- Style seeds: fixed for controlled comparisons until the final HOI4 LoRA checkpoint is selected
- Restoration: complete Adonis Base → Post graph with one red enable/bypass control
- Restoration seed: fixed so unchanged restoration inputs remain cacheable across new style generations
- Restoration prompts: detailed source-neutral archival wording covers JPEG and compression artifacts, descreening, repeating noise, scratches, dust, scan defects, deblurring, and natural full-scene detail recovery while preserving identity, composition, historical character, and monochrome, sepia, or colour treatment
- Shared LoRAs: HOI4 style checkpoints 1750, 2000, 2250, 2500, 2750, and 3000 plus Adonis Base, Adonis Refine, and Adonis Post

## Workflow contract

- Source portrait: three style candidates and a five-card comparison row
- Text to image: one sampler and one final portrait
- Batch: per-queue folder rescan, deterministic case-insensitive list input, one sampler, and sequential per-source execution
- Processing only: RealESRGAN plus Adonis Base → Post, without the style LoRA
- Automatic saving: path-validated master PNG, game PNG, and DDS terminal outputs follow the selected portrait output link on current ComfyUI versions and use non-overwriting numbered filenames
- Output names: source, processing-only, and batch saves preserve each input image stem; source candidates add `_1`, `_2`, and `_3`
- Layout: four fully visible, compact, colour-coded canvases with portrait-ratio previews
- Frontend compatibility: connected widget sockets and saved widget values follow ComfyUI frontend 1.45.19, preventing the crop dimensions and KSampler CFG, sampler, and scheduler values from shifting when a workflow opens
- Batch layout: the hand-arranged canvas is grid-aligned and split into symmetric create and save groups, with three centered comparison previews and consistent group colours
- Output: 1024×1365 PNG, centered 156×210 PNG, and HOI4-ready DDS under the selected portrait output folder
- Downloads: high-performance Xet is enabled, independent repositories run in parallel, files from each repository transfer concurrently through one shared Xet token, short rate-limit retries recover before resumable HTTPS fallback, and integrity checks protect every installed file
- Linked folders: the batch restoration cache and automatic savers validate and follow only the installer-managed input and output links, avoiding current ComfyUI's external-symlink rejection without allowing arbitrary paths

## Installation contract

- GGUF for 8–16 GB VRAM, with selectable Q4_K_M/Q5_K_M/Q6_K/Q8_0 quants
- FP8 for 16–20 GB VRAM
- Full distilled weights above 20 GB VRAM
- RunPod defaults to FP8 distilled; full BF16 remains an explicit option
- RunPod uses `/workspace/hoi4-portrait-runpod/input` and `/workspace/hoi4-portrait-runpod/output`; the input folder includes three Ireland example sources
- RunPod storage: a 25 GB volume is enough for the default FP8 installation
- Windows detects the GPU, offers the official ComfyUI portable install when ComfyUI is missing, selects the ROCm-enabled package for AMD, always preselects FP8, keeps GGUF and full BF16 available as explicit options, supports multi-variant installs, offers default, ComfyUI, and custom batch input and portrait output paths, installs pinned node packs, and downloads the selected model set

Pinned commits, model revisions, sizes, hashes, and licenses are in [`models.json`](models.json), [`scripts/install_custom_node_packs.py`](scripts/install_custom_node_packs.py), and [`THIRD_PARTY_LICENSES.md`](THIRD_PARTY_LICENSES.md).
