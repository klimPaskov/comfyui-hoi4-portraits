# Workflow guide

## Shared design

Each workflow is arranged in clearly labeled groups that run from left to
right. The groups are visual organization and do not change execution order.

The source and text-to-image model stack is:

1. `UNETLoader` — FLUX.2 Klein base 9B FP8.
2. `CLIPLoader` — Qwen 3 8B FP8 mixed with type `flux2`.
3. `VAELoader` — FLUX.2 VAE.
4. `LoraLoaderModelOnly` — the HOI4 adapter at strength `0.7`.
5. `CFGGuider`, Euler, `Flux2Scheduler`, eight steps, CFG 5.

The processing workflow loads the base model, text encoder, and VAE for its
optional restoration pass. It does not load the LoRA or run a style pass.

Use Euler with eight steps by default. The local step comparison covers 6, 8,
10, 12, 20, and 35 steps; higher counts add runtime without a useful gain in
the controlled source comparison.

## Source workflow

The main README includes a [complete visual walkthrough](../README.md#what-the-source-workflow-does)
with one full-graph screenshot and a readable close-up of every group.

Groups run left to right:

1. **Source and ESRGAN** loads the portrait, applies the adjustable built-in head-and-shoulders crop, previews it, runs RealESRGAN x2, then fits the result to 832 × 1120.
2. **FLUX.2 Klein 9B models** loads the base model, encoder, VAE, and LoRA.
3. **Optional FLUX.2 restoration** encodes the ESRGAN result as both its reference and starting latent for a conservative restoration pass. This keeps framing and pose anchored.
4. The restoration switch is off by default and sends the direct ESRGAN result
   onward. Turn it on to select the FLUX result. The disabled restoration pass
   does not run.
5. **HOI4 LoRA styling** encodes the selected processed image as both the reference and starting latent, then samples with the LoRA-patched model. This avoids the pose drift caused by starting image-to-image work from an empty latent.
6. **Optional background** receives the decoded styled image, creates its foreground mask with BiRefNet, and composites over the selected background.
7. A second switch keeps the styled image unchanged by default or selects the
   composite when enabled.
8. **Preview and save** writes the 832 × 1120 master and a 156 × 210 PNG.

The source graph opens with **Toggle FLUX restoration** set to `false`. Turn it
on for the additional restoration pass. Keep the supplied connections intact.

## Processing workflow

This graph ends after source processing. It contains the adjustable crop,
RealESRGAN, and optional FLUX.2 restoration pass, with the restoration switch
off by default. It saves the processed 832 × 1120 image and the 156 × 210
game-size image. It does not load or apply the project LoRA.

## Text to image

This graph has no source, VAE reference encode, RealESRGAN, or restoration
pass. The positive prompt must begin with `hoi4_portrait`. It produces the
master and game-size outputs and uses the same final-only background branch.

## Positive prompt invariant

After the `hoi4_portrait,` trigger, positive prompts describe only the person.
They should describe only supported ethnicity, approximate age, broad hair or
facial-hair cues, and general clothing classification. Expression, pose, gaze, and facing direction should be left to the
source reference. They must not request a game/style, background, lighting, palette, rendering,
restoration, transformation, or preservation behavior. The validator rejects
common violations in every generated API graph.

## Background replacement invariant

The background branch is deliberately downstream of `VAEDecode` for the HOI4
LoRA sampler. In the API graphs:

- node `63` masks the final styled image;
- node `65` composites that same image over the chosen background using node
  `63`'s foreground mask directly;
- node `66` selects either the unchanged final image or the composite;
- no background node is an ancestor of the LoRA-styled `VAEDecode`.

The project checks this dependency order. Background processing belongs after
portrait generation.

`RemoveBackground` returns a foreground mask. Do not insert `InvertMask`
between nodes `63` and `65`, or the foreground/background regions will swap.

## Editing safely

- Change prompts, seeds, LoRA strength, and boolean switches freely.
- Set the crop bounding box around the head and shoulders and confirm node
  `10`'s preview before queueing the expensive FLUX stages.
- Keep the exact model family and encoder type together.
- Keep 832 and 1120 divisible by 16 if you change the work canvas.
- Do not connect a background composite into a reference-latent encode.
- Re-run `python scripts/validate_workflows.py` after structural edits.
- Edit [`scripts/build_workflows.py`](../scripts/build_workflows.py), then regenerate, instead of hand-editing six JSON files independently.
