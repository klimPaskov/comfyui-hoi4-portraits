# FLUX.2 Klein 9B style LoRA

The installer downloads the retrained checkpoints from steps 1500, 2000, 2250,
2500, 3000, 3500, and 4000 from the public
[Hugging Face model repository](https://huggingface.co/Hoops-McCann/hoi4-portraits-flux2-klein-9b-lora)
into `ComfyUI/models/loras/`. It also keeps the previous adapter available as a
baseline during checkpoint selection.

Comfy Cloud users should import the checkpoint they want to test through
**Models → Import**, select **LoRA**, and wait for the filename to appear in
the `LoraLoaderModelOnly` dropdown.

The source and text-to-image workflows initially select the 1500-step
checkpoint. Choose another checkpoint in `LoraLoaderModelOnly` to compare it
under the same prompt and seed. The trigger word is `hoi4_portrait`. Start with LoRA strength `0.70`, Euler,
eight steps, and CFG 5. Fixed-seed tests at 6, 8, 10, 12, 20, and 35 steps found
no useful gain above eight. Source candidates default to `hoi4_portrait,
maintain the exact identity, facing direction, and expression of the person,
including every object they are holding or wearing.` Text-to-image
prompts describe only the person—not the game/style, background, lighting, or
rendering.

For source portraits, crop to head and shoulders before RealESRGAN and use the
encoded processed portrait as the sampler starting latent. The source
workflows include this connection.
