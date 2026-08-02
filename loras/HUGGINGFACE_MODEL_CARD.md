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

Style adapter used by the public
[`comfyui-hoi4-portraits`](https://github.com/klimPaskov/comfyui-hoi4-portraits)
workflows.

## File

- `hoi4_portraits_flux2_klein_9b_lora_000002500.safetensors`
- Trigger word: `hoi4_portrait`
- Base: `black-forest-labs/FLUX.2-klein-base-9B-fp8`
- Training step: 2,500 (epoch 5)
- ComfyUI loader: `LoraLoaderModelOnly`
- Suggested starting strength: `0.8`

## Recommended ComfyUI stack

1. `UNETLoader`: `flux-2-klein-base-9b-fp8.safetensors`
2. `CLIPLoader`: `qwen_3_8b_fp8mixed.safetensors`, type `flux2`
3. `VAELoader`: `flux2-vae.safetensors`
4. `LoraLoaderModelOnly`: this LoRA at strength `0.8`
5. 20 steps, CFG 5, Euler sampler, `Flux2Scheduler`

Use `0.7` when a source portrait needs a lighter LoRA influence. In the
positive prompt, describe only the visible person. Do not request a game
style, background, lighting, rendering, restoration, transformation, or
preservation behavior.

## Example prompt

```text
hoi4_portrait, a middle-aged man with short dark hair, round wire-frame glasses, a long narrow face, a neat moustache, and a reserved expression, wearing a dark jacket over a light collared shirt and tie, shown from the shoulders up while looking slightly left.
```

The `hoi4_portrait` trigger and LoRA supply the learned look. Prompt text after
the trigger should describe the person, not the desired treatment.

## License and model terms

The project grants the adapter under the repository's MIT license. The gated
FLUX.2 Klein 9B base remains subject to the FLUX Non-Commercial License; using
this adapter does not remove those restrictions. ComfyUI, the text encoder,
VAE, and any source or generated images retain their own terms. Hearts of Iron
IV is a trademark of Paradox Interactive; this community project is not
affiliated with or endorsed by Paradox Interactive.
