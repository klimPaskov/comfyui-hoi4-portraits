# Workflow guide

## Shared design

Every current workflow is a flat graph made from core ComfyUI nodes. Groups
are visual organization only; no subgraph or custom Python node is required.

The shared model stack is:

1. `UNETLoader` — FLUX.2 Klein base 9B FP8.
2. `CLIPLoader` — Qwen 3 8B FP8 mixed with type `flux2`.
3. `VAELoader` — FLUX.2 VAE.
4. `LoraLoaderModelOnly` — the HOI4 adapter at strength `1.0`.
5. `CFGGuider`, Euler, `Flux2Scheduler`, 20 steps, CFG 5.

## Full power

Groups run left to right:

1. **Source and ESRGAN** loads the portrait, applies RealESRGAN x2, then fits the result to 832 × 1120.
2. **FLUX.2 Klein 9B models** loads the base model, encoder, VAE, and LoRA.
3. **Optional FLUX.2 restoration** uses the ESRGAN result as a reference latent for a conservative restoration pass.
4. The restoration `ComfySwitchNode` chooses the FLUX result when on and the direct ESRGAN result when off. It is a lazy switch, so the disabled FLUX branch is not evaluated.
5. **HOI4 LoRA styling** uses the switch output as the sole portrait reference and the LoRA-patched model as the sampler model.
6. **Optional background** receives the decoded styled image, creates its foreground mask with BiRefNet, and composites over the selected background.
7. A second lazy switch keeps the styled image unchanged by default or selects the composite when enabled.
8. **Preview and save** writes the 832 × 1120 master and a 156 × 210 PNG.

To use ESRGAN only inside the full graph, set **Toggle FLUX restoration** to
`false`. No links should be deleted or reconnected.

## ESRGAN only

This graph removes the entire FLUX restoration group. RealESRGAN output feeds
the HOI4 reference-latent stage directly. Styling still uses FLUX.2 Klein 9B
and the same project LoRA.

## Text to image

This graph has no source, VAE reference encode, RealESRGAN, or restoration
pass. The positive prompt must begin with `hoi4_portrait`. It produces the
same master and game-size outputs and uses the same final-only background
branch.

## Background replacement invariant

The background branch is deliberately downstream of `VAEDecode` for the HOI4
LoRA sampler. In the API graphs:

- node `63` masks the final styled image;
- node `65` composites that same image over the chosen background using node
  `63`'s foreground mask directly;
- node `66` selects either the unchanged final image or the composite;
- no background node is an ancestor of the LoRA-styled `VAEDecode`.

The validator enforces this dependency order. A workflow fails validation if
background processing is connected before generation.

`RemoveBackground` returns a foreground mask. Do not insert `InvertMask`
between nodes `63` and `65`, or the foreground/background regions will swap.

## Editing safely

- Change prompts, seeds, LoRA strength, and boolean switches freely.
- Keep the exact model family and encoder type together.
- Keep 832 and 1120 divisible by 16 if you change the work canvas.
- Do not connect a background composite into a reference-latent encode.
- Re-run `python scripts/validate_workflows.py` after structural edits.
- Edit [`scripts/build_workflows.py`](../scripts/build_workflows.py), then regenerate, instead of hand-editing six JSON files independently.
