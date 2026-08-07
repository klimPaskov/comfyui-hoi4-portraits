# Workflow guide

## Shared design

Each workflow keeps its complete pipeline visible in labeled stage groups.
Controls and previews are placed beside the stage they affect. The source workflow keeps its three candidate
branches in separate cards so prompts and sampler controls are easy to compare.

The source and text-to-image model stack is:

1. `UNETLoader` — FLUX.2 Klein base 9B FP8.
2. `CLIPLoader` — Qwen 3 8B FP8 mixed with type `flux2`.
3. `VAELoader` — FLUX.2 VAE.
4. `LoraLoaderModelOnly` — loads the HOI4 adapter and exposes LoRA strength directly on the same node, defaulting to `1.00`.
5. `LoraLoaderModelOnly` — loads Adonis Base for the optional restoration pass.
6. Standard sampling controls: independently adjust the fixed seed, sampler, FLUX.2 steps, denoise, CFG, guidance, and canvas size for that branch.

The [identity comparison pack](identity-comparison.md) keeps this stack and
generation policy fixed while testing nine alternate preservation paths.

Restoration and text-to-image use Euler with six steps. The three source
candidates use Euler/6 steps, `res_2s`/4 steps, and `res_2m`/8 steps.

## Source workflow

The main README includes a [complete visual walkthrough](../README.md#what-the-source-workflow-does)
with one full-graph screenshot and a readable close-up of every group.

Groups run left to right:

1. **Source and ESRGAN** loads the portrait, detects the face and subject silhouette, and produces a 1024 × 1365 head-and-shoulders crop. **Face zoom** accepts `0.0–1.0` and defaults to `0.90`; larger values remove more body space. **Preserve hat/headwear** defaults to `true` and protects the complete headwear silhouette. Set it to `false` for a normal face-led crop that may cut oversized hats. **Toggle face processing** defaults to on; turn it off to skip face detection and retain the full composition or multiple people. The bypass still applies a centered canvas crop and RealESRGAN. A manual bounding-box override remains available for selecting one person.
2. **FLUX.2 Klein 9B models** loads the base model, encoder, VAE, and LoRA.
3. **Optional FLUX.2 restoration** applies the Adonis Base LoKr and encodes the ESRGAN result as both its reference and starting latent for a conservative restoration pass.
4. The restoration switch is on by default and selects the FLUX result. Turn it
   off to use the direct ESRGAN result; the disabled restoration branch does not run.
5. **HOI4 LoRA styling** runs three independent seed passes. Each pass encodes
   the selected processed image as the starting latent and attaches it once as
   the source reference. Each branch uses a separate editable prompt with the
   HOI4 LoRA model. Candidate 1 uses Euler/6 steps, candidate 2 uses `res_2s`/4 steps,
   and candidate 3 uses `res_2m`/8 steps. This keeps all three candidates tied
   to the same face, crop, and pose while also comparing sampling behavior.
6. **Optional background** receives each decoded styled image, creates its
   foreground mask with BiRefNet, and composites each candidate over the same
   selected background.
7. **Preview and save** writes three 1024 × 1365 masters and three centered
   156 × 210 PNGs, using `candidate_1`, `candidate_2`, and `candidate_3` prefixes.

The source graph opens with **Toggle FLUX restoration** enabled. Turn it off to
bypass the single restoration pass. Keep the supplied connections intact.

Each source prompt defaults to `hoi4_portrait, maintain the exact identity,
facing direction, and expression of the person, including every object they
are holding or wearing.` Keep that sentence and append deliberate requested
changes. Each prompt affects only its own candidate. Denoise defaults to
`1.00`; LoRA strength is editable directly on the LoRA loader and defaults to
`1.00`.

Enable FLUX restoration for monochrome or sepia inputs. It restores plausible
natural color before the three LoRA candidates are generated.

## Processing workflow

This graph ends after automatic cropping, RealESRGAN, and the optional FLUX.2
restoration pass. Face processing and restoration are enabled by default. It saves the
processed 1024 × 1365 image and the centered 156 × 210 game-size image.
The centered game crop removes the slight ratio mismatch from the left and
right edges instead of distorting the image.

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
- Adjust **Face zoom** when needed and confirm the dedicated crop + ESRGAN
  preview before
  queueing the expensive FLUX stages. Use the manual crop only when the source
  contains multiple plausible subjects.
- Keep the exact model family and encoder type together.
- Keep the published 1024 × 1365 master size. FLUX.2 performs latent sampling
  at its supported internal grid and each decoded stage is normalized back to
  the exact master size before preview, compositing, or saving.
- Do not connect a background composite into a reference-latent encode.
