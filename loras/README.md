# FLUX.2 Klein 9B style LoRA

The installer uses one canonical HOI4 style LoRA:

```text
hoi4_portrait_flux2_klein_9b_lora_000002500.safetensors
```

The workflows load this file at strength `1`, and style sampling seeds randomize after every generation.

It targets FLUX.2 Klein 9B and uses the trigger `hoi4_portrait`. Place the checkpoint under `ComfyUI/models/loras/` and select it in `LoraLoaderModelOnly`.

Comfy Cloud users should import the checkpoint through **Models → Import**, select **LoRA**, and wait for the filename to appear in the `LoraLoaderModelOnly` dropdown.

The workflow defaults are tuned: LoRA strength `1.00`, CFG `1.0`, FLUX guidance `1.0`, **Euler** sampler, **simple** scheduler, **4 steps**, and denoise `1.00`.

Source portraits default to the exact prompt:

```text
make this portrait hoi4_portrait style
```

The text-to-image workflow uses the example prompt:

```text
hoi4_portrait style, a soviet soldier with the head of a brown bear wearing a soviet hat, ears still visible. No military uniform decorations.
```

For source portraits, the graph crops to 1024 × 1365 head and shoulders, applies RealESRGAN, optionally runs the Adonis restoration pass, and then uses the processed portrait as the sampler starting latent. The source workflows include these connections.
