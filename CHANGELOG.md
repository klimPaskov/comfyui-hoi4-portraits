# Changelog

All notable project changes are recorded here.

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
- Recorded the validated, person-only Qwen autoprompter description used for
  every source example.
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
