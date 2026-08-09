# Workflow guide

## Compact card system

The public canvases use a small set of project-owned logical cards instead of
exposing dozens of implementation nodes:

| Card | Responsibility |
| --- | --- |
| `HOI4 Distilled Model Stack` | Distilled FLUX.2 Klein variant, Qwen 3 8B Q8 GGUF, VAE, step-2500 style LoRA, and optional Adonis Base/Refine LoKrs |
| `HOI4 Source Prep` | Automatic or manual face crop, headwear protection, and RealESRGAN |
| `HOI4 Adonis Restoration` | Exact upstream 1.7 MP, reference-conditioning, Base → Refine RES4LYF topology with live sampling |
| `HOI4 Portrait Sampler` | Prompt, reference/text mode, seed, steps, CFG, guidance, sampler, scheduler, denoise, noise, partial-step controls, and live preview callback |
| `HOI4 Final Output` | Optional BiRefNet background replacement and centered master/game crops without stretching |
| `HOI4 Save DDS` | 156×210 DXT5/BC3 DDS with no mipmaps |

The model stack uses only distilled FLUX.2 Klein 9B. Its selectable file is
the full safetensors, FP8 safetensors, or a city96 GGUF diffusion model. Text
conditioning always uses `Qwen3-8B-Q8_0.gguf` through the pinned
`calcuis/gguf` `ClipLoaderGGUF` implementation.

The tuned style settings are CFG `1`, guidance `1`, **Euler**, **simple**,
**4 steps**, and denoise `1`. The only installed style checkpoint is
`hoi4_portrait_flux2_klein_9b_lora_000002500.safetensors` at strength `1`.

## Source workflow

The source canvas has 29 nodes arranged as six visible stages. There are no
collapsible group containers or hidden subgraphs, so the entire workflow stays
visible on the main canvas:

1. beginner setup, sampler, prompt, and restoration notes;
2. large source loader, explicit source preview, face/manual crop, and RealESRGAN;
3. one model-stack card and one exact Adonis Base → Refine card;
4. three independent live sampler cards plus centered final-output cards;
5. automatic PNG and DDS saves for every candidate;
6. one compact portrait-ratio comparison row: RealESRGAN, Adonis restoration,
   and three final 156×210 portraits.

Every source sampler uses the exact prompt:

```text
make this portrait hoi4_portrait style
```

The three seeds are `42`, `43`, and `44`. Restoration is enabled by default
and can be bypassed on its own card for a clean modern photo.

## Text-to-image workflow

This ten-node graph loads only the style stack, runs one sampler, offers
optional post-generation background replacement, and saves one master PNG,
one game PNG, and one DDS. Its exact default prompt is:

```text
hoi4_portrait style, an Irish middle-aged man with neatly combed dark hair, wearing a plain civilian jacket.
```

## Processing-only workflow

This 13-node graph runs source prep and exact Adonis restoration without
loading or applying the style LoRA. Its comparison row contains RealESRGAN,
Adonis, and the centered 156×210 result.

## Batch workflow

This 14-node graph reads every compatible image in
`ComfyUI/input/hoi4_portraits_batch/`. `HOI4 Batch Input` returns list items,
so ComfyUI executes the shared graph one source at a time. There is exactly
one restoration card and one style sampler.

## Output contract

All workflows save to:

```text
ComfyUI/output/1024x1365/     master PNG
ComfyUI/output/156x210/       centered game PNG
ComfyUI/output/156x210/dds/   156×210 DXT5 DDS, no mipmaps
```

The resize uses aspect-preserving bicubic resampling followed by a centered
crop. No workflow stretches the portrait, and there is no redundant upscale
after the 1024×1365 style decode.
