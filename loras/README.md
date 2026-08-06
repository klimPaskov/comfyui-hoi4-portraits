# FLUX.2 Klein 9B style LoRA

Compatible checkpoints target FLUX.2 Klein base 9B FP8 and use the trigger
`hoi4_portrait`. Place the checkpoint under `ComfyUI/models/loras/` and select
it in `LoraLoaderModelOnly`.

Comfy Cloud users should import the checkpoint they want to test through
**Models → Import**, select **LoRA**, and wait for the filename to appear in
the `LoraLoaderModelOnly` dropdown.

Choose checkpoints in `LoraLoaderModelOnly` to compare them under the same
prompt and seed. Start with LoRA strength `1.00`, CFG 1, and FLUX guidance 1.
The three source candidates
use Euler/6 steps, `res_2s`/4 steps, and `res_2m`/8 steps. Source candidates default to `hoi4_portrait,
maintain the exact identity, facing direction, and expression of the person,
including every object they are holding or wearing.` Text-to-image
prompts describe only the person—not the game/style, background, lighting, or
rendering.

For source portraits, crop to 1024 × 1365 head and shoulders before RealESRGAN and use the
encoded processed portrait as the sampler starting latent. The source
workflows include this connection.
