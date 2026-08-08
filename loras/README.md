# FLUX.2 Klein 9B style LoRA

The tuned checkpoint is the **2500-step** LoRA:

```text
hoi4_portrait_flux2_klein_9b_lora_000002500.safetensors
```

It targets the **distilled** FLUX.2 Klein 9B model (never the base model) and
uses the trigger `hoi4_portrait`. Place the checkpoint under
`ComfyUI/models/loras/` and select it in `LoraLoaderModelOnly`.

Comfy Cloud users should import the checkpoint through **Models → Import**,
select **LoRA**, and wait for the filename to appear in the
`LoraLoaderModelOnly` dropdown.

The workflow defaults are tuned: LoRA strength `1.00`, CFG `1.0`, FLUX
guidance `1.0`, **Euler** sampler, **simple** scheduler, **4 steps**, and
denoise `1.00`.

Source portraits default to the exact prompt:

```text
make this portrait hoi4_portrait style
```

Text-to-image prompts describe only the person—not the game/style,
background, lighting, or rendering. Example:

```text
hoi4_portrait, an Irish middle-aged man with neatly combed dark hair, wearing a plain civilian jacket.
```

For source portraits, the graph crops to 1024 × 1365 head and shoulders,
applies RealESRGAN, optionally runs the Adonis restoration pass, and then uses
the processed portrait as the sampler starting latent. The source workflows
include these connections.
