# Changelog

All notable project changes are recorded here.

## 2.4.8 — 2026-08-05

- Reorganized the editor workflows into compact native stage cards with
  separate source candidates and collision-checked internal layouts.
- Made RunPod installation and restart use the same detected ComfyUI Python,
  with checks for the crop node and pinned RES4LYF sampler sources.
- Added an Apple MPS precision guard for the RES sampler extension; CUDA keeps
  its upstream precision behavior.
- Replaced the workflow screenshots and expanded live-editor validation.

## 2.4.7 — 2026-08-05

- Set the three source candidates to Euler/6 steps, `res_2s`/4 steps, and
  `res_2m`/8 steps.
- Added the pinned RES4LYF sampler extension to the RunPod and Windows
  installers.

## 2.4.6 — 2026-08-04

- Set restoration and LoRA styling to denoise 1.00, six steps, CFG 1, and FLUX
  guidance 1.
- Set the visible LoRA strength default to 1.00.

## 2.4.5 — 2026-08-04

- Added all seven retrained LoRA checkpoints to the RunPod and local model
  installer for controlled checkpoint comparison.
- Selected the 1500-step retrained checkpoint as the initial workflow LoRA.

## 2.4.4 — 2026-08-04

- Set all three source styling passes to full denoise `1.00`, matching the
  sampling schedule used for the accepted gallery examples.

## 2.4.3 — 2026-08-04

- Added a visible LoRA strength control with a `0.70` starting value.
- Set source styling denoise to `0.80` for stronger identity preservation without starving the eight-step style pass.
- Kept color restoration in the optional pre-styling restoration pass.

## 2.4.2 — 2026-08-04

- Corrected every image-edit sampler to use the active denoise sigma schedule.
- Added parallel, resumable Hugging Face/Xet model transfers to the installers.

## 2.4.1 — 2026-08-04

- Set source LoRA strength and editable denoise controls to `1.00`.
- Added three independent candidate prompts with the concise identity default;
  editing one prompt affects only its own candidate branch.

## 2.4.0 — 2026-08-04

- Added automatic face detection with a one-click manual crop override for
  blurry, distant, and multi-person source images.
- Added the pinned MediaPipe detector to the model installer and RunPod paths.
- Replaced generated source descriptions with a fixed identity-preservation
  instruction; text-to-image keeps concise manual prompting guidance.
- Made FLUX restoration and background replacement controls red and kept both
  disabled by default.
- Regenerated the workflow diagrams and extended structural and crop tests.

## 2.3.0 — 2026-08-03

- Published the three-workflow set as source, text-to-image, and
  `hoi4_portrait_processing_only`; the processing-only graph is last in the
  README table and does not load the LoRA.
- Updated the RunPod, Windows PowerShell, and Windows self-extractor paths to
  install the current workflows and pinned model files without custom nodes.
- Added a model-free ZIP, Windows x64 executable, and checksums to the release
  package.
- Refreshed release metadata and documentation for the current filenames,
  model defaults, and portable core-node graph design.

## 2.2.0 — 2026-08-02

- Added an adjustable, built-in head-and-shoulders crop before RealESRGAN in
  both source workflows, with a preview checkpoint before FLUX runs.
- Changed image-to-image sampling to start from the encoded processed source
  instead of an empty latent, substantially reducing pose and framing drift.
- Set the selected defaults to LoRA strength `0.7`, Euler, six steps, and CFG 5;
  added fixed-seed 6/8/10/20-step comparison evidence.
- Replaced the prior gallery with three full-restoration triptychs, three
  ESRGAN-only triptychs, and three no-input portraits made from the latest
  supplied sources.
- Extended structural tests for crop order, source-latent ancestry, defaults,
  prompt policy, and non-overlapping workflow layout.
- Restored the canonical MIT license text so GitHub can identify the repository
  license; third-party and base-model restrictions remain documented separately.

## 2.1.0 — 2026-08-01

- Changed every default LoRA strength to `0.8`, with `0.7` documented as the
  lighter identity-preserving option.
- Replaced style/game/background/rendering prompt examples with a strict
  person-only positive-prompt contract after the `hoi4_portrait,` trigger.
- Added validator and unit-test regressions for LoRA strength and forbidden
  positive-prompt language.
- Completed actual local inference with the project LoRA: five full-
  restoration portraits, five ESRGAN-only portraits, five no-input portraits,
  seven controlled setting variants, and a post-final background run.
- Added ten three-stage comparison boards, a five-portrait text-to-image board,
  a settings matrix, and documented reduced-resource test conditions.
- Confirmed Euler / 20 steps / CFG 5 matches ComfyUI's native FLUX.2 Klein 9B
  Base workflow; DPM++ 2M and Heun brought no gain in the reduced local pilot.

## 2.0.1 — 2026-08-01

- Fixed optional background compositing to consume the foreground mask from
  `RemoveBackground` directly. The previous inversion swapped the subject and
  background regions.
- Added a regression check that rejects inverted or indirect foreground-mask
  wiring.
- Recorded successful Comfy Cloud GPU execution of all three workflow shapes
  with a zero-strength catalog LoRA used as a mechanical substitute.

## 2.0.0 — 2026-08-01

- Rebuilt every default workflow around FLUX.2 Klein base 9B and the new
  `hoi4_portrait` LoRA.
- Added full-power, ESRGAN-only, and text-to-image workflows in editor and API
  formats.
- Made full-power restoration run RealESRGAN first, followed by a lazy,
  switchable FLUX.2 restoration pass.
- Moved optional background removal/compositing after the final LoRA-styled
  decode.
- Removed the repository node extension pack and sidecar services; the graphs
  remain portable across supported ComfyUI environments.
- Published the LoRA and model card on Hugging Face.
- Added deterministic workflow generation, structural/layout checks, pinned
  model checksums, installers, tests, and Comfy Cloud guidance.
- Moved the Krea-based workflows out of the default experience; they remain
  available only through the archived v1.0.0 release.

## 1.0.0 — 2026-07-31

- Initial public Krea/Qwen-based workflow release.
