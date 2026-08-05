# Workflow guide

## Shared design

Each workflow opens as a small set of native ComfyUI stage cards. Double-click
a card to inspect or edit its nodes, then use the back arrow above the canvas
to return to the pipeline. The source workflow keeps its three candidate
branches in separate cards so prompts and sampler controls are easy to compare.

The source and text-to-image model stack is:

1. `UNETLoader` — FLUX.2 Klein base 9B FP8.
2. `CLIPLoader` — Qwen 3 8B FP8 mixed with type `flux2`.
3. `VAELoader` — FLUX.2 VAE.
4. `LoraLoaderModelOnly` — loads the HOI4 adapter and exposes LoRA strength directly on the same node, defaulting to `1.00`.
5. `FluxGuidance`, `CFGGuider`, `KSamplerSelect`, and `Flux2Scheduler`: guidance 1 and CFG 1, with the branch-specific sampler and step count.

Restoration and text-to-image use Euler with six steps. The three source
candidates use Euler/6 steps, `res_2s`/4 steps, and `res_2m`/8 steps.

## Source workflow

The main README includes a [complete visual walkthrough](../README.md#what-the-source-workflow-does)
with one full-graph screenshot and a readable close-up of every group.

Groups run left to right:

1. **Source and ESRGAN** loads the portrait, detects the face and subject silhouette, and produces an 832 × 1120 head-and-shoulders crop. **Face zoom** accepts `0.0–1.0` and defaults to `0.90`; larger values remove more body space while the complete head, headwear, and a safety margin remain protected. A one-click manual bounding-box override is available for ambiguous multi-person sources. The selected crop then runs through RealESRGAN x2.
2. **FLUX.2 Klein 9B models** loads the base model, encoder, VAE, and LoRA.
3. **Optional FLUX.2 restoration** encodes the ESRGAN result as both its reference and starting latent for a conservative restoration pass. This keeps framing and pose anchored.
4. The restoration switch is off by default and sends the direct ESRGAN result
   onward. Turn it on to select the FLUX result. The disabled restoration pass
   does not run.
5. **HOI4 LoRA styling** runs three independent seed passes. Each pass encodes
   the selected processed image as both the reference and starting latent and
   uses a separate editable identity prompt in each branch with the LoRA-patched
   model. Candidate 1 uses Euler/6 steps, candidate 2 uses `res_2s`/4 steps,
   and candidate 3 uses `res_2m`/8 steps. This keeps all three candidates tied
   to the same face, crop, and pose while also comparing sampling behavior.
6. **Optional background** receives each decoded styled image, creates its
   foreground mask with BiRefNet, and composites each candidate over the same
   selected background.
7. **Preview and save** writes three 832 × 1120 masters and three 156 × 210
   PNGs, using `candidate_1`, `candidate_2`, and `candidate_3` prefixes.

The source graph opens with **Toggle FLUX restoration** set to `false`. Turn it
on for the single additional restoration pass. Keep the supplied connections
intact.

Each source prompt defaults to `hoi4_portrait, maintain the exact identity,
facing direction, and expression of the person, including every object they
are holding or wearing.` Keep that sentence and append deliberate requested
changes. Each prompt affects only its own candidate. Denoise defaults to
`1.00`; LoRA strength is editable directly on the LoRA loader and defaults to `1.00`.

Enable FLUX restoration for monochrome or sepia inputs. It restores plausible
natural color before the three LoRA candidates are generated.

## Processing workflow

This graph ends after automatic cropping, RealESRGAN, and the optional FLUX.2
restoration pass. The restoration switch is off by default. It saves the
processed 832 × 1120 image and the 156 × 210 game-size image.

## Text to image

This graph has no source, VAE reference encode, RealESRGAN, or restoration
pass. The positive prompt must begin with `hoi4_portrait`. It produces the
master and game-size outputs and uses the same final-only background branch.

## Positive prompt invariant

The source workflow uses three independent editable identity prompts, one per
candidate. The text-to-image prompt begins with `hoi4_portrait,` and uses a
short general person description. Neither prompt should request a game/style,
background, lighting, palette, or rendering behavior.

## Background replacement

Background masking and compositing run only after the final LoRA portrait has
been decoded. The red switch is off by default and applies the selected
background to all three source candidates when enabled.

`RemoveBackground` returns a foreground mask. Do not insert `InvertMask` into
any of the candidate branches, or the foreground/background regions will swap.

## Editing safely

- Change prompts, seeds, LoRA strength, and boolean switches freely.
- Adjust **Face zoom** when needed and confirm node `10`'s preview before
  queueing the expensive FLUX stages. Use the manual crop only when the source
  contains multiple plausible subjects.
- Keep the exact model family and encoder type together.
- Keep 832 and 1120 divisible by 16 if you change the work canvas.
- Do not connect a background composite into a reference-latent encode.
