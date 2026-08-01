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
- Suggested starting strength: `1.0`

## Recommended ComfyUI stack

1. `UNETLoader`: `flux-2-klein-base-9b-fp8.safetensors`
2. `CLIPLoader`: `qwen_3_8b_fp8mixed.safetensors`, type `flux2`
3. `VAELoader`: `flux2-vae.safetensors`
4. `LoraLoaderModelOnly`: this LoRA at strength `1.0`
5. 20 steps, CFG 5, Euler sampler, `Flux2Scheduler`

For source portraits, use FLUX.2 reference-latent conditioning and explicitly
ask the model to preserve identity, facial geometry, expression, hairstyle,
clothing, pose, camera angle, and crop.

## Example prompt

```text
hoi4_portrait, transform the supplied person into a polished Hearts of Iron IV leader portrait. Preserve exact identity, facial geometry, expression, hairstyle, visible clothing, pose, camera angle, and crop. Use a hand-painted 1930s-1940s grand-strategy portrait finish, restrained brushwork, realistic skin, crisp eyes, soft directional studio light, muted historical colors, and a formal head-and-shoulders composition.
```

## License and model terms

The project grants the adapter under the repository's MIT license. The gated
FLUX.2 Klein 9B base remains subject to the FLUX Non-Commercial License; using
this adapter does not remove those restrictions. ComfyUI, the text encoder,
VAE, and any source or generated images retain their own terms. Hearts of Iron
IV is a trademark of Paradox Interactive; this community project is not
affiliated with or endorsed by Paradox Interactive.
