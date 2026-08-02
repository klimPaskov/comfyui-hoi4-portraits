# Local test results

These images were generated locally with the actual FLUX.2 Klein base 9B
stack and `hoi4_portraits_flux2_klein_9b_lora_000002500.safetensors`. All six
sources came from the latest user-supplied `source_originals.zip`, not older
project fixtures. The tested archive contained 43 files and had SHA-256
`71924dbe78019464c21da9aa4d522441cb7faa99fc33b082f42561e2ff086321`.

## Test conditions

- ComfyUI 0.25.0;
- Apple-silicon Mac with 16 GB unified memory and MPS low-VRAM offloading;
- 416 × 560 evidence output; the public workflow canvas remains 832 × 1120;
- LoRA strength `0.7`, Euler, eight steps, CFG 5;
- full restoration: adjustable crop → RealESRGAN → FLUX restoration → LoRA;
- ESRGAN-only: adjustable crop → RealESRGAN → LoRA;
- the processed image is encoded as the sampler's starting latent to keep the
  original pose and composition anchored.

The reduced size is a local resource compromise, not a mechanical shortcut:
the same committed node/connectivity structure is used, with ordinary input
widgets overridden for each source, seed, prompt, crop, and evidence size.
Attempts at 832 × 1120 and 624 × 840 were stopped because a 16 GB MPS machine
could not complete them in a practical time; they did not expose a node, type,
or connection error.

## Three full-restoration triptychs

Each board shows initial source → cropped RealESRGAN plus FLUX restoration →
final LoRA portrait.

![Full restoration test 1](assets/test-runs/full-restoration-01.jpg)

Validated autoprompter description:

```text
hoi4_portrait, a middle-aged man with a broad oval face, short dark wavy hair swept upward from a side part, a small neat dark moustache, softly rounded cheeks, a straight nose, and a faint asymmetric smile that lifts one corner of his closed mouth, his head turned slightly toward the viewer's left while his eyes look upward toward the viewer's left, his body angled slightly toward the viewer's right, wearing a dark three-piece suit with broad lapels, a light shirt, and a dark tie, shown from the chest up.
```

![Full restoration test 2](assets/test-runs/full-restoration-02.jpg)

Validated autoprompter description:

```text
hoi4_portrait, a young woman with a softly heart-shaped face, dark hair swept back from a side part, gently arched brows, wide bright eyes looking directly at the viewer, a straight narrow nose, rounded cheeks, and a slight closed-mouth smile with subtly raised corners, her head held nearly level and turned only slightly toward the viewer's right, wearing a broad light collar over a dark garment, shown from the upper chest up.
```

![Full restoration test 3](assets/test-runs/full-restoration-03.jpg)

Validated autoprompter description:

```text
hoi4_portrait, a young man with a long narrow oval face, dark hair combed smoothly back from a side part, a high forehead, gently arched brows, a straight prominent nose, a defined chin, and a faint closed-mouth smile, his head turned slightly toward the viewer's right while his eyes look upward toward the viewer's right, wearing a dark suit jacket, light pointed collar, and dark tie, shown from the chest up.
```

## Three ESRGAN-only triptychs

Each board shows initial source → cropped RealESRGAN preparation → final LoRA
portrait. No FLUX restoration node is evaluated in this path.

![ESRGAN-only test 1](assets/test-runs/esrgan-only-01.jpg)

Validated autoprompter description:

```text
hoi4_portrait, a middle-aged man with a long angular face, a high receding hairline and short dark hair combed back, prominent ears, furrowed brows, narrow deep-set eyes, a straight prominent nose, lean cheeks with visible creases, and a restrained asymmetric half-smile, his head turned slightly toward the viewer's right while his gaze remains nearly forward, wearing a high-collared uniform with shoulder straps, braided cord, chest pockets, belt, and visible decorations, shown from the chest up.
```

![ESRGAN-only test 2](assets/test-runs/esrgan-only-02.jpg)

Validated autoprompter description:

```text
hoi4_portrait, a slender middle-aged man with a long narrow face, neatly parted dark hair combed close to the head, round wire-frame glasses, heavy-lidded eyes looking slightly toward the viewer's right, a long straight nose, hollow cheeks, and thin closed lips in a reserved unsmiling expression, his head and upper body turned in a clear three-quarter view toward the viewer's left, wearing a dark suit jacket, high light collar, and dark tie, shown from the chest up.
```

![ESRGAN-only test 3](assets/test-runs/esrgan-only-03.jpg)

Validated autoprompter description:

```text
hoi4_portrait, an older man with a long narrow face, a bald crown and sparse dark hair at the sides, gently arched dark eyebrows, heavy-lidded eyes with visible under-eye creases, a long prominent nose, hollow cheeks with fine cheek lines, thin compressed lips, a firm unsmiling expression, and faint horizontal forehead lines, facing nearly forward with his head held level and his gaze directed slightly toward the viewer's left, wearing a dark high-collared garment with a corded fastening, shown from the chest up.
```

## Three no-input portraits

The three portraits use recorded seeds and different person-only prompts. No
source image was supplied, and no prompt requested a game/style, background,
lighting, palette, or rendering treatment.

![Three no-input portraits](assets/test-runs/random-portraits.jpg)

```text
hoi4_portrait, an older man with a broad rectangular face, a high forehead, short silver hair brushed back, thick straight brows, deep-set eyes with crow's-feet and under-eye creases, a broad nose, weathered cheeks with visible nasolabial folds, a neat grey moustache, and a reserved closed-mouth expression, facing forward with a level gaze, wearing a dark double-breasted jacket, light collared shirt, and dark tie, shown from the chest up.
```

```text
hoi4_portrait, a middle-aged woman with an oval face, dark hair parted at the center and pinned into a low bun, arched brows, slightly hooded eyes, a straight nose, fine lines beneath the eyes and at the corners of her closed mouth, and a firm composed expression, her head turned slightly toward the viewer's left while her eyes look directly toward the viewer, wearing a high-necked dark jacket with a small round brooch, shown from the chest up.
```

```text
hoi4_portrait, a young man with a narrow angular face, close-cropped dark hair, straight low brows, deep-set eyes, prominent cheekbones, a straight nose, a defined jaw, and a serious closed-mouth expression, his head and body turned slightly toward the viewer's right while his gaze remains forward, wearing a plain buttoned service tunic without visible insignia, shown from the shoulders up.
```

## Fixed-seed 6/8/10/12/20/35-step control

The sampler control compared Euler, DPM++ 2M, Heun, and CFG 4. DPM++ 2M did
not improve the result, Heun was slower without a visual gain, and CFG 4 was
softer than CFG 5. The step-count comparison holds Euler and CFG 5 constant.

Prompt, source, crop, seed, resolution, LoRA strength, CFG, and Euler sampler
are held constant. Only `Flux2Scheduler.steps` changes.

![Euler at 6, 8, 10, 12, 20, and 35 steps](assets/test-runs/step-comparison.jpg)

Eight steps is the selected production limit. It improves structure over six
without the extra runtime and framing drift seen at 10, 12, 20, and 35. The
higher counts do not recover detail missing from the 416-pixel evidence canvas
and are retained only as a fixed-seed reference.

## Autoprompter validation

Each source was inspected at full resolution, then checked a second time for
expression, separate head/body/gaze direction, facial proportions, and visible
microtexture. The validated descriptions exclude unsupported lighting/color
claims and use consistent viewer-relative pose wording. The displayed lines
are the exact descriptions sent to the workflows. They describe the person
only; the LoRA and workflow provide the learned treatment and processing.

## Post-final background test

The background test loads a completed LoRA portrait directly into
the background group. Only BiRefNet, image scaling, mask compositing, and the
final switch are evaluated, proving that background work remains downstream
of final image creation.

![Post-final background replacement test](assets/test-runs/post-final-background.png)
