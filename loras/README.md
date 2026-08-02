# FLUX.2 Klein 9B style LoRA

Download `hoi4_portraits_flux2_klein_9b_lora_000002500.safetensors` from the
public [Hugging Face model repository](https://huggingface.co/Hoops-McCann/hoi4-portraits-flux2-klein-9b-lora)
and place it in `ComfyUI/models/loras/`.

Comfy Cloud users should import the same Hugging Face file through
**Models → Import**, select **LoRA**, and wait for the filename to appear in
the `LoraLoaderModelOnly` dropdown.

The trigger word is `hoi4_portrait`. Start with LoRA strength `0.8`; try `0.7`
when a source portrait needs a lighter influence. After the trigger, describe
only the person—not the game/style, background, lighting, or rendering.
