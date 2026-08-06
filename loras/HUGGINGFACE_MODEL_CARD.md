---
license: mit
base_model: black-forest-labs/FLUX.2-klein-base-9B-fp8
library_name: diffusers
pipeline_tag: image-to-image
tags:
  - comfyui
  - flux2
  - flux2-klein
  - lora
  - hearts-of-iron-iv
  - portrait
---

# HOI4 portraits — FLUX.2 Klein 9B LoRA

FLUX.2 Klein 9B portrait adapter for the public
[`comfyui-hoi4-portraits`](https://github.com/klimPaskov/comfyui-hoi4-portraits)
ComfyUI workflows. Trigger: `hoi4_portrait`.

## Checkpoints

Model weights are not currently published. Compatible checkpoints must target
`black-forest-labs/FLUX.2-klein-base-9B-fp8`.

## Workflow settings

1. `UNETLoader`: `flux-2-klein-base-9b-fp8.safetensors`
2. `CLIPLoader`: `qwen_3_8b_fp8mixed.safetensors`, type `flux2`
3. `VAELoader`: `flux2-vae.safetensors`
4. `LoraLoaderModelOnly`: strength `1.00`
5. `CFGGuider`: CFG 1; `FluxGuidance`: 1; denoise `1.00`
6. Candidate 1: Euler, 6 steps
7. Candidate 2: `res_2s`, 4 steps
8. Candidate 3: `res_2m`, 8 steps

`res_2s` and `res_2m` require
[RES4LYF](https://github.com/ClownsharkBatwing/RES4LYF). The repository
installers add the pinned extension automatically.

For source portraits, the graph crops to 1024 × 1365 head-and-shoulders,
applies RealESRGAN, and optionally runs FLUX restoration. It then encodes the
processed image as both reference conditioning and sampler starting latent.
Restoration uses a fixed seed and is off by default; the three styling branches
use independent randomized seeds and separate prompts.

## Source prompt

```text
hoi4_portrait, maintain the exact identity, facing direction, and expression of the person, including every object they are holding or wearing.
```

Keep the identity sentence. Append an intentional edit only to the candidate
that should test it.

## Text-to-image example

```text
hoi4_portrait, an Irish middle-aged man with short wavy dark hair and a moustache, wearing a dark civilian suit.
```

Text-to-image prompts should describe the person only—not style, background,
lighting, framing, or rendering.

## License and model terms

The project grants the adapter under the repository's MIT license. The gated
FLUX.2 Klein 9B base remains subject to the FLUX Non-Commercial License; using
this adapter does not remove those restrictions. ComfyUI, the text encoder,
VAE, and any source or generated images retain their own terms. Hearts of Iron
IV is a trademark of Paradox Interactive; this community project is not
affiliated with or endorsed by Paradox Interactive.
