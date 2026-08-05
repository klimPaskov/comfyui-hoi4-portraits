# FLUX.2 Klein 9B style LoRA

The installer downloads the selected checkpoints from steps 2000, 2250, and
2500 from the public
[Hugging Face model repository](https://huggingface.co/Hoops-McCann/hoi4-portraits-flux2-klein-9b-lora)
into `ComfyUI/models/loras/`.

Comfy Cloud users should import the checkpoint they want to test through
**Models → Import**, select **LoRA**, and wait for the filename to appear in
the `LoraLoaderModelOnly` dropdown.

The source and text-to-image workflows initially select the 2250-step
checkpoint. Choose another checkpoint in `LoraLoaderModelOnly` to compare it
under the same prompt and seed. The trigger word is `hoi4_portrait`. Start with
LoRA strength `1.00`, CFG 1, and FLUX guidance 1. The three source candidates
use Euler/6 steps, `res_2s`/4 steps, and `res_2m`/8 steps. Source candidates default to `hoi4_portrait,
maintain the exact identity, facing direction, and expression of the person,
including every object they are holding or wearing.` Text-to-image
prompts describe only the person—not the game/style, background, lighting, or
rendering.

For source portraits, crop to head and shoulders before RealESRGAN and use the
encoded processed portrait as the sampler starting latent. The source
workflows include this connection.
