# FLUX.2 Klein 9B style LoRA

The project uses the 2500-step HOI4 style LoRA:

```text
hoi4_portrait_flux2_klein_9b_lora_000002500.safetensors
```

It targets the **distilled** FLUX.2 Klein 9B model and works with the project's full, FP8, and GGUF distilled variants. Use the trigger `hoi4_portrait` and load the file at strength `1.00` in `LoraLoaderModelOnly`.

Place the checkpoint under `ComfyUI/models/loras/`. Comfy Cloud users can import it through **Models → Import**, select **LoRA**, and wait for the filename to appear in the loader dropdown.

Style sampling uses CFG `1.0`, FLUX guidance `1.0`, **Euler**, **simple** scheduling, **4 steps**, and denoise `1.00`. The source workflow starts with fixed seeds `757254001619850`, `629907966167866`, and `42`; batch starts with fixed seed `42`; text-to-image is randomized by default. Set **Control after generate** to **randomize**, **increment**, or **decrement** to explore different results.

Source prompt:

```text
make this portrait hoi4_portrait style
```

Text-to-image prompt:

```text
hoi4_portrait style, a soviet soldier with the head of a brown bear wearing a soviet hat, ears still visible. No military uniform decorations.
```

Source, processing-only, and batch workflows use the Adonis Base → Post restoration path when enabled; the source and batch graphs keep one red restoration switch. Source starts with three candidates, while batch defaults to one candidate per input and can create more. All image-based outputs keep the input filename stem.

See the [Hugging Face model card](HUGGINGFACE_MODEL_CARD.md), [workflow guide](../docs/workflows.md), and [output layout reference](../docs/output-layout.md) for the complete model stack, workflow behavior, and saved-file structure.
