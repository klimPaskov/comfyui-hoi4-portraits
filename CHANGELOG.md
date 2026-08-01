# Changelog

All notable project changes are recorded here.

## 2.0.0 — 2026-08-01

- Rebuilt every default workflow around FLUX.2 Klein base 9B and the new
  `hoi4_portrait` LoRA.
- Added full-power, ESRGAN-only, and text-to-image workflows in editor and API
  formats.
- Made full-power restoration run RealESRGAN first, followed by a lazy,
  switchable FLUX.2 restoration pass.
- Moved optional background removal/compositing after the final LoRA-styled
  decode.
- Removed the repository custom-node pack and sidecar services; current graphs
  use ComfyUI built-in nodes and are Comfy Cloud compatible.
- Published the LoRA and model card on Hugging Face.
- Added deterministic workflow generation, structural/layout checks, pinned
  model checksums, installers, tests, and Comfy Cloud guidance.
- Moved the Krea-based workflows out of the default experience; they remain
  available only through the archived v1.0.0 release.

## 1.0.0 — 2026-07-31

- Initial public Krea/Qwen-based workflow release.
