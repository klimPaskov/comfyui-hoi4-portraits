# Workflow guide

## Shared design

Every workflow keeps its complete pipeline visible in labeled stage groups and
opens with a **Setup guide** column that explains the model folders, the
sampler controls, and prompting. Controls and previews sit beside the stage
they affect. All generation nodes are one advanced sampler card:

`Hoi4PortraitSampler` exposes the seed, steps, CFG, FLUX guidance, sampling
algorithm (Euler by default), scheduler (simple by default), denoise, and the
advanced partial-step controls on a single node. Sampling is live — the editor
shows the portrait being constructed while it runs.

The model stack is:

1. `UNETLoader` — the **distilled** FLUX.2 Klein 9B (`flux-2-klein-9b.safetensors`
   for full, `flux-2-klein-9b-fp8.safetensors` for FP8, or
   `UnetLoaderGGUF` + `flux-2-klein-9b-*.gguf` for GGUF).
2. `CLIPLoader` — Qwen 3 8B FP8 mixed with type `flux2`.
3. `VAELoader` — FLUX.2 VAE.
4. `LoraLoaderModelOnly` — the tuned 2500-step HOI4 LoRA at strength `1.00`.
5. `LoraLoaderModelOnly` — Adonis Base and Adonis Post for the optional
   restoration pass.

The tuned generation policy is CFG `1.0`, guidance `1.0`, **Euler**, **simple**,
**4 steps**, denoise `1.00`.

## Source workflow

Groups run left to right:

1. **Welcome & setup** — the model folder guide, sampler explanation, and
   prompting guide.
2. **Source and ESRGAN** — loads the portrait (with a source preview), detects
   the face and subject silhouette, and produces a 1024×1365 head-and-shoulders
   crop. **Face zoom** defaults to `0.90`; **Preserve hat/headwear** defaults
   to `true`; **Toggle face processing** defaults to on. RealESRGAN upscales
   next (with an ESRGAN preview), and the crop + ESRGAN preview lets you verify
   framing before generation.
3. **FLUX.2 Klein 9B models** — the distilled model, encoder, VAE, LoRA, and
   Adonis LoKrs.
4. **Optional FLUX.2 restoration** — Adonis Base then Adonis Post reconstruct
   detail and colour. The red toggle is ON by default; turn it off for the
   direct ESRGAN output.
5. **HOI4 LoRA styling** — three independent seed passes, each with its own
   editable prompt and advanced sampler card. Below the cards, the comparison
   row shows the ESRGAN source, the restoration pass, and the three game-size
   finals side by side for a clear head-to-head.
6. **Optional background** — BiRefNet masking and compositing run only after
   the final decode; off by default.
7. **Preview and save** — writes three full-res masters, three 156×210 PNGs,
   and three 156×210 DXT5 DDS files.

Each source prompt defaults to the exact phrase:

```text
make this portrait hoi4_portrait style
```

Append a deliberate change only to the candidate that should test it.

## Text-to-image workflow

The same model stack and one advanced sampler card, but no source, no
restoration pass, and one final portrait. Start the prompt with `hoi4_portrait,`
and describe only the person:

```text
hoi4_portrait, an Irish middle-aged man with neatly combed dark hair, wearing a plain civilian jacket.
```

## Processing workflow

The same crop, RealESRGAN, and optional Adonis restoration as the source
workflow, but no LoRA styling. A comparison row shows the ESRGAN result, the
restoration pass, and the processed 156×210 final.

## Batch workflow

Drop any number of source photos into `ComfyUI/input/hoi4_portraits_batch/`
and queue once. Every image is processed one by one through the same crop,
ESRGAN, optional restoration, and the **single** HOI4 sampler. Results are
saved to `output/1024x1365/`, `output/156x210/`, and `output/156x210/dds/`.

## Output folders and DDS

All four workflows save to the same output folders:

```text
ComfyUI/output/1024x1365/     full-res master PNG
ComfyUI/output/156x210/       game-size PNG
ComfyUI/output/156x210/dds/   HOI4-ready DDS
```

The game-size resize is a normal Lanczos resize followed by a centered crop —
it never stretches. The DDS files are 156×210 DXT5 (BC3) with no mipmaps, the
format HOI4 reads natively, so they can be dropped into `gfx/portraits`
without a crash.
