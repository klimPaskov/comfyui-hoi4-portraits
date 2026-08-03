# Local test results

These images were generated locally with the FLUX.2 Klein base 9B stack and
`hoi4_portraits_flux2_klein_9b_lora_000002500.safetensors`. All six source
portraits came from the supplied `source_originals.zip`. The archive SHA-256 is
`71924dbe78019464c21da9aa4d522441cb7faa99fc33b082f42561e2ff086321`.

## Test conditions

- ComfyUI 0.25.0;
- Apple-silicon Mac with 16 GB unified memory and MPS offloading;
- 416 × 560 evidence output; the public workflow canvas remains 832 × 1120;
- LoRA strength `0.7` for the evidence boards, Euler, six steps, CFG 5;
- the workflows use LoRA strength `0.7` by default with the same sampler;
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
workflow with restoration disabled. The boards show colour, clean crops, and
stable framing.

## Six source triptychs

Each board shows initial source → processed image → final LoRA portrait. The
first three use the FLUX restoration pass; the second three use the same source
workflow with that pass disabled.

![Source processing test 1](assets/test-runs/source-processing-01.jpg)

```text
hoi4_portrait, an Irish middle-aged man with short wavy dark hair and a moustache, wearing a dark civilian suit.
```

![Source processing test 2](assets/test-runs/source-processing-02.jpg)

```text
hoi4_portrait, an Irish young woman with dark hair swept back, wearing a dark civilian dress with a light collar.
```

![Source processing test 3](assets/test-runs/source-processing-03.jpg)

```text
hoi4_portrait, an Irish young man with dark hair combed back, wearing a dark civilian suit with a light collar and tie.
```

![Source processing without FLUX restoration, test 1](assets/test-runs/source-processing-restoration-off-01.jpg)

```text
hoi4_portrait, an Irish middle-aged man with receding dark hair and prominent ears, wearing a military uniform.
```

![Source processing without FLUX restoration, test 2](assets/test-runs/source-processing-restoration-off-02.jpg)

```text
hoi4_portrait, an Irish slender middle-aged man with neatly parted dark hair and round wire-frame glasses, wearing a dark civilian suit.
```

![Source processing without FLUX restoration, test 3](assets/test-runs/source-processing-restoration-off-03.jpg)

```text
hoi4_portrait, an Irish older man with sparse dark hair at the sides, wearing dark clerical clothing.
```

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
hoi4_portrait, an Irish young man with close-cropped dark hair, wearing a plain military service tunic.
```

## Fixed-seed 6/8/10/12/20/35-step control

The sampler control compared Euler, DPM++ 2M, Heun, and CFG 4. DPM++ 2M did
not improve the result, Heun was slower without a visual gain, and CFG 4 was
softer than CFG 5. The step-count comparison holds Euler and CFG 5 constant.

![Euler at 6, 8, 10, 12, 20, and 35 steps](assets/test-runs/step-comparison.jpg)

Use eight steps for production. It improves structure over six without the
extra runtime and framing drift seen at 10, 12, 20, and 35.

## Post-final background test

The background test loads a finished LoRA portrait directly into the background
stage. It uses BiRefNet, image scaling, mask compositing, and the final switch;
background work remains downstream of final image creation.

![Post-final background replacement test](assets/test-runs/post-final-background.png)
