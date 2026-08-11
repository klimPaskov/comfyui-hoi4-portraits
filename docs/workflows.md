# Workflow guide

## Canvas layout

Every processing step stays on the main canvas. The coloured groups follow the
same order as the portrait: preparation, models, restoration, styling, and
saving.

The main visible controls are:

| Control | Responsibility |
| --- | --- |
| `📂 Setup and downloads` | Narrow dark-brown card with a clear folder tree and clickable model downloads |
| `KSampler` | Standard ComfyUI sampler with seed, 4 steps, CFG 1, Euler, simple scheduling, and full denoise |
| `Adaptive Portrait Crop` | Automatic, centered, or manual portrait framing with headwear protection |
| `Use Adonis restoration` | One red true/false control for the complete Base → Post branch; enabled by default |
| `HOI4 Optional Background Replacement` | One optional BiRefNet background-replacement operation; sizing remains separate |
| `HOI4 Batch Input Folder` | List output that executes one source at a time |
| `HOI4 Save DDS` | HOI4-ready 156×210 portrait DDS |

The following steps use separate nodes: diffusion model,
Qwen Q8 encoder, VAE, every LoRA loader, face detection, subject mask,
RealESRGAN, Adonis preprocessing, both prompt encodes, source reference
encoding, Adonis Base sampling, Adonis Post reference conditioning, Adonis
Post sampling, final VAE decode, restoration switch, master crop, and game crop.

The tuned style settings are CFG `1`, guidance `1`, **Euler**, **simple**,
**4 steps**, and denoise `1`. The HOI4 style checkpoint is
`hoi4_portrait_flux2_klein_9b_lora_000002500.safetensors` at strength `1`.

## Restoration path

The source, processing-only, and batch canvases inline the current functional
graph from `adonis_post_workflows/Adonis_Base_Post_gguf.json`:

1. scale to `1.7` MP, a multiple of `16`, using crop + Lanczos;
2. combine and encode the official fixed + Base prompt;
3. zero the Base negative conditioning;
4. VAE-encode the prepared source and apply both Base reference latents;
5. create the correctly sized empty FLUX.2 latent;
6. use the upstream RES4LYF options: Laplacian noise, initial scale `1`,
   alternate denoise `1`, channelwise CFG off;
7. run a complete nine-step Adonis Base generation;
8. combine and encode the official fixed + Post prompt, zero its negative,
   and use the Base output latent for both Post reference branches;
9. run a second complete nine-step Adonis Post generation from the same
    empty latent, seed, and options;
10. VAE-decode the Post result;
11. use one red toggle to choose the prepared portrait or the complete Adonis
    result for every downstream node.

Base and Post share the same seed (`42`) and per-model step (`9`) controls.
Base uses eta `0.8`; Post uses eta `0.5`. Both use
`exponential/res_2s`, simple scheduling, CFG `1`, full denoise, standard mode,
and `steps_to_run = -1`, matching the current upstream graph.

## Source workflow

The source canvas has 74 nodes in seven groups:

1. one narrow setup card with model folders and clickable downloads;
2. source loader, face detection, subject mask, focused crop controls, and
   RealESRGAN—the upload card itself already shows the source;
3. six model/LoRA loaders below the green preparation group;
4. the complete Adonis Base → Post restoration path and its single red toggle;
5. three style samplers, one shared background switch, and separate output sizing;
6. PNG and DDS saves for every portrait;
7. a compact portrait-ratio comparison row containing RealESRGAN, Adonis,
   and the three final 156×210 portraits.

Every source sampler uses the exact prompt:

```text
make this portrait hoi4_portrait style
```

The three seeds are `42`, `43`, and `44`. Adonis Base and Post are part of the
source path; use the processing-only workflow when you want the restored
portrait without style sampling.

## Text-to-image workflow

This 20-node graph keeps the diffusion model, Qwen encoder, VAE, and style
LoRA loaders separate. It runs one standard ComfyUI sampler, then shows optional
background replacement, master sizing, game sizing, all three saves, and one
tall final preview. Its example prompt is:

```text
hoi4_portrait style, an Irish middle-aged man with neatly combed dark hair, wearing a plain civilian jacket.
```

## Processing-only workflow

This 41-node graph includes source preparation and the entire Adonis topology.
It does not load the style LoRA. RealESRGAN, restored, and final 156×210
portraits appear together in the comparison row.

## Batch workflow

This 50-node graph reads compatible images from
`ComfyUI/input/hoi4_portraits_batch/`. `HOI4 Batch Input` returns list items,
so ComfyUI handles one source at a time in stable, case-insensitive filename
order. It rescans the folder on every queue instead of reusing a cached file
list. There is one standard sampler and one set of automatic final saves.

## Output contract

All workflows save to:

```text
ComfyUI/output/1024x1365/     master PNG
ComfyUI/output/156x210/       centered game PNG
ComfyUI/output/156x210/dds/   HOI4-ready DDS
```

The DDS saver writes uncompressed 32-bit BGRA data with alpha in the
A8R8G8B8/B8G8R8A8-style layout used by HOI4 portraits. Both native PNG savers
and `HOI4 Save DDS` are terminal output nodes. Queueing
the workflow therefore executes every connected save branch automatically;
numbered counters prevent repeated runs from overwriting existing portraits.

Master and game sizing use separate `ImageScale` nodes with Lanczos
resampling and center cropping. The portrait is never stretched, and there is
no redundant upscale after style generation.
