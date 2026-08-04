# FLUX.2 Klein 9B style LoRA

Download `hoi4_portraits_flux2_klein_9b_lora_000002500.safetensors` from the
public [Hugging Face model repository](https://huggingface.co/Hoops-McCann/hoi4-portraits-flux2-klein-9b-lora)
and place it in `ComfyUI/models/loras/`.

Comfy Cloud users should import the same Hugging Face file through
**Models → Import**, select **LoRA**, and wait for the filename to appear in
the `LoraLoaderModelOnly` dropdown.

The trigger word is `hoi4_portrait`. Start with LoRA strength `0.70`, Euler,
eight steps, and CFG 5. Fixed-seed tests at 6, 8, 10, 12, 20, and 35 steps found
no useful gain above eight. Source candidates default to `hoi4_portrait,
maintain the exact identity, facing direction, and expression of the person,
including every object they are holding or wearing.` Text-to-image
prompts describe only the person—not the game/style, background, lighting, or
rendering.

For source portraits, crop to head and shoulders before RealESRGAN and use the
encoded processed portrait as the sampler starting latent. The source
workflows include this connection.
