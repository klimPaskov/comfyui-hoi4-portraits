# Workflow guide

## Visible-node design

Every public workflow keeps its real processing topology on the main canvas.
Colored canvas groups label stages, but they are saved expanded and contain no
subgraphs or collapsed implementations.

Only operations that are genuinely one control surface remain custom nodes:

| Focused custom node | Responsibility |
| --- | --- |
| `HOI4 Portrait Sampler` | Prompt, reference/text mode, seed, steps, CFG, guidance, sampler, scheduler, denoise, partial-step controls, and live previews |
| `Adaptive Portrait Crop` | Automatic, centered, or manual portrait framing with headwear protection |
| `HOI4 Optional Background Replacement` | One optional BiRefNet background-replacement operation; sizing remains separate |
| `HOI4 Batch Input Folder` | List output that executes one source at a time |
| `HOI4 Save DDS` | 156×210 DXT5/BC3 DDS with no mipmaps |

The following nodes are deliberately separate and visible: diffusion model,
Qwen Q8 encoder, VAE, every LoRA loader, face detection, subject mask,
RealESRGAN, Adonis preprocessing, reference encoding, Adonis Base sampling,
Adonis Refine sampling, VAE decode, restoration switch, master crop, and game
crop.

The tuned style settings are CFG `1`, guidance `1`, **Euler**, **simple**,
**4 steps**, and denoise `1`. The only style checkpoint is
`hoi4_portrait_flux2_klein_9b_lora_000002500.safetensors` at strength `1`.

## Expanded Adonis topology

The source, processing-only, and batch canvases inline the functional graph
from `n8te0/adonis_flux2klein/Adonis_Workflow.json`:

1. scale to `1.7` MP, a multiple of `16`, using crop + Lanczos;
2. encode the exact `uhdmanscale` restoration prompt;
3. zero the negative conditioning;
4. VAE-encode the prepared source and apply positive/negative reference latents;
5. create the correctly sized empty FLUX.2 latent;
6. use the upstream RES4LYF options: Laplacian noise, initial scale `1`,
   alternate denoise `1`, channelwise CFG off;
7. run visible Adonis Base for the first `5` of `9` steps;
8. run visible Adonis Refine for the remaining steps in `resample` mode;
9. VAE-decode and pass through the visible restoration switch.

Both `ClownsharKSampler_Beta` nodes remain visible and provide live latent
previews. Base and Refine share visible seed (`42`) and total-step (`9`) nodes.

## Source workflow

The source canvas has 61 nodes in seven visible groups:

1. beginner setup, sampler, prompt, and restoration notes;
2. source loader, tall source preview, face detection, subject mask, focused
   crop controls, RealESRGAN, and the optional background loader;
3. six separate model/LoRA loaders;
4. the fully expanded Adonis Base → Refine graph;
5. three focused live style samplers with separately visible output sizing;
6. automatic PNG and DDS saves for every candidate;
7. a compact portrait-ratio comparison row containing RealESRGAN, Adonis,
   and the three final 156×210 portraits.

Every source sampler uses the exact prompt:

```text
make this portrait hoi4_portrait style
```

The three seeds are `42`, `43`, and `44`. Restoration is enabled by default
through the visible switch and can be disabled for a clean modern photo.

## Text-to-image workflow

This 16-node graph keeps the diffusion model, Qwen encoder, VAE, and style
LoRA loaders separate. It runs one focused style sampler, then shows optional
background replacement, master sizing, game sizing, all three saves, and one
tall final preview as visible nodes. Its exact prompt is:

```text
hoi4_portrait style, an Irish middle-aged man with neatly combed dark hair, wearing a plain civilian jacket.
```

## Processing-only workflow

This 38-node graph exposes source preparation and the entire Adonis topology.
It does not load the style LoRA. RealESRGAN, restored, and final 156×210
portraits appear together in the comparison row.

## Batch workflow

This 40-node graph reads compatible images from
`ComfyUI/input/hoi4_portraits_batch/`. `HOI4 Batch Input` returns list items,
so ComfyUI executes the visible shared graph once per source. There is one
focused style sampler and one set of final saves.

## Output contract

All workflows save to:

```text
ComfyUI/output/1024x1365/     master PNG
ComfyUI/output/156x210/       centered game PNG
ComfyUI/output/156x210/dds/   156×210 DXT5 DDS, no mipmaps
```

Master and game sizing use separate visible `ImageScale` nodes with Lanczos
resampling and center cropping. The portrait is never stretched, and there is
no redundant upscale after style generation.
