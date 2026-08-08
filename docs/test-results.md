# Local test results

These images were generated locally with the distilled FLUX.2 Klein 9B stack and
`hoi4_portraits_flux2_klein_9b_lora_000002500.safetensors`. All six source
portraits came from the supplied `source_originals.zip`.

## Test conditions

- ComfyUI 0.25.0;
- accepted color boards retain the LoRA strength printed in each final panel;
- accepted boards retain the settings printed in each image; source workflow controls remain editable;
- source path: adjustable crop → RealESRGAN → optional FLUX restoration → FLUX.2 Klein 9B LoRA;
- the first three `source-processing` boards use the optional FLUX restoration
  path;
- the three `source-processing-restoration-off` boards use the direct ESRGAN
  path; the no-input gallery remains a separate reference;
- the processed image is encoded as the sampler's starting latent to keep the
  original pose and composition anchored.

The reduced size is a local resource compromise. The same workflow connections
are used for each source, seed, prompt, crop, and evidence size. The first
three source boards use the source workflow with FLUX restoration enabled to
recover colour and detail from aged material. The other three use the same
workflow with restoration disabled. Only color finals with clean crops and
stable framing are included.

## Six source triptychs

Each board shows initial source → processed image → final LoRA portrait. The
first three use the FLUX restoration pass; the second three use the same source
workflow with that pass disabled.

![Source processing test 1](assets/test-runs/source-processing-01.jpg)

![Source processing test 2](assets/test-runs/source-processing-02.jpg)

![Source processing test 3](assets/test-runs/source-processing-03.jpg)

![Source processing without FLUX restoration, test 1](assets/test-runs/source-processing-restoration-off-01.jpg)

![Source processing without FLUX restoration, test 2](assets/test-runs/source-processing-restoration-off-02.jpg)

![Source processing without FLUX restoration, test 3](assets/test-runs/source-processing-restoration-off-03.jpg)

## Three no-input portraits

These retained no-input examples use short person-only prompts. No prompt
requests a game or visual treatment, background, lighting, palette, or
rendering behavior.

![Three no-input portraits](assets/test-runs/random-portraits.jpg)

```text
hoi4_portrait, an Irish older man with short silver hair and a grey moustache, wearing a dark civilian jacket.
```

```text
hoi4_portrait, an Irish middle-aged woman with dark hair pinned into a low bun, wearing a high-necked civilian jacket.
```

```text
hoi4_portrait, an Irish man with close-cropped dark hair, wearing a plain military service tunic.
```

## Fixed-seed 6/8/10/12/20/35-step control

The step-count comparison holds Euler and CFG 5 constant.

![Euler at 6, 8, 10, 12, 20, and 35 steps](assets/test-runs/step-comparison.jpg)

Use eight steps for production. It improves structure over six without the
extra runtime and framing drift seen at 10, 12, 20, and 35.

## Post-final background test

The background test loads a finished LoRA portrait directly into the background
stage. It uses BiRefNet, image scaling, mask compositing, and the final switch;
background work remains downstream of final image creation.

![Post-final background replacement test](assets/test-runs/post-final-background.png)

The same post-final branch can use the bundled scientist background with the
completed FLUX portrait:

![Post-final portrait over the scientist background](assets/test-runs/post-final-scientist-background.png)
