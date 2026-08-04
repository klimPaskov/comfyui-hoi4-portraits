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
- Suggested starting strength: `1.00`

## Recommended ComfyUI stack

1. `UNETLoader`: `flux-2-klein-base-9b-fp8.safetensors`
2. `CLIPLoader`: `qwen_3_8b_fp8mixed.safetensors`, type `flux2`
3. `VAELoader`: `flux2-vae.safetensors`
4. `LoraLoaderModelOnly`: this LoRA at strength `1.00`
5. Eight steps, CFG 5, Euler sampler, `Flux2Scheduler`

Fixed-seed tests at 6, 8, 10, 12, 20, and 35 steps support eight as the
practical limit. Source workflows use a concise identity prompt for each
candidate; append deliberate edits only to the branch that should test them.
Text-to-image prompts describe only the visible person. Do not request a game
style, background, lighting, or rendering behavior.

For image-to-image use, crop the source to head and shoulders before ESRGAN,
then encode that processed image as both the FLUX.2 reference and the sampler
starting latent. Starting from an empty latent can change pose and framing even
when reference conditioning is present.

## Source prompt

```text
hoi4_portrait, maintain the identity, facing direction, and expression of the person in the portrait, including any objects they are holding or wearing.
```

Each source candidate has its own prompt. Keep the identity sentence and append
requested changes, such as `Add a military hat.` Editing one prompt affects
only that candidate.

## Text-to-image example

```text
hoi4_portrait, an Irish middle-aged man with short wavy dark hair and a moustache, wearing a dark civilian suit.
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
