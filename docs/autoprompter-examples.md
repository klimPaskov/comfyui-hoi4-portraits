# Autoprompter examples

The Qwen vision instruction is provided as an external prompting resource
because an embedded sidecar cannot be imported into Comfy Cloud. Use
[`prompts/autoprompter_instruction.txt`](../prompts/autoprompter_instruction.txt)
with an external vision-language model.

## Use it with the Cloud-compatible workflows

1. Send the portrait and the complete instruction file to your vision-language
   model outside ComfyUI.
2. Confirm that its one-line answer starts with `hoi4_portrait,` and contains
   no treatment or unsupported identity claims.
3. Remove uncertain color/lighting language and any contradictory pose words.
4. Paste the validated line into the source workflow's positive prompt field.

## Required output contract

Output one English line that begins with `hoi4_portrait,` and describes only
the visible person. Include useful facial features, hair, expression, visible
clothing, pose, gaze, and crop. Omit uncertain details.

Never add the game name, a style request, background, lighting, palette,
rendering language, restoration instructions, transformation instructions, or
preservation commands. The trigger and LoRA supply the learned look; the
reference-latent workflow supplies the source image.

## Validated outputs used in the gallery

These were generated from full-resolution inspection of the six supplied
source portraits, followed by a second check for expression, separate
head/body/gaze direction, facial detail, and forbidden treatment language.
These exact descriptions are printed beside the matching images in the main
README.

```text
hoi4_portrait, a middle-aged man with a broad oval face, short dark wavy hair swept upward from a side part, a small neat dark moustache, softly rounded cheeks, a straight nose, and a faint asymmetric smile that lifts one corner of his closed mouth, his head turned slightly toward the viewer's left while his eyes look upward toward the viewer's left, his body angled slightly toward the viewer's right, wearing a dark three-piece suit with broad lapels, a light shirt, and a dark tie, shown from the chest up.
```

```text
hoi4_portrait, a young woman with a softly heart-shaped face, dark hair swept back from a side part, gently arched brows, wide bright eyes looking directly at the viewer, a straight narrow nose, rounded cheeks, and a slight closed-mouth smile with subtly raised corners, her head held nearly level and turned only slightly toward the viewer's right, wearing a broad light collar over a dark garment, shown from the upper chest up.
```

```text
hoi4_portrait, a young man with a long narrow oval face, dark hair combed smoothly back from a side part, a high forehead, gently arched brows, a straight prominent nose, a defined chin, and a faint closed-mouth smile, his head turned slightly toward the viewer's right while his eyes look upward toward the viewer's right, wearing a dark suit jacket, light pointed collar, and dark tie, shown from the chest up.
```

```text
hoi4_portrait, a middle-aged man with a long angular face, a high receding hairline and short dark hair combed back, prominent ears, furrowed brows, narrow deep-set eyes, a straight prominent nose, lean cheeks with visible creases, and a restrained asymmetric half-smile, his head turned slightly toward the viewer's right while his gaze remains nearly forward, wearing a high-collared uniform with shoulder straps, braided cord, chest pockets, belt, and visible decorations, shown from the chest up.
```

```text
hoi4_portrait, a slender middle-aged man with a long narrow face, neatly parted dark hair combed close to the head, round wire-frame glasses, heavy-lidded eyes looking slightly toward the viewer's right, a long straight nose, hollow cheeks, and thin closed lips in a reserved unsmiling expression, his head and upper body turned in a clear three-quarter view toward the viewer's left, wearing a dark suit jacket, high light collar, and dark tie, shown from the chest up.
```

```text
hoi4_portrait, an older man with a long narrow face, a bald crown and sparse dark hair at the sides, gently arched dark eyebrows, heavy-lidded eyes with visible under-eye creases, a long prominent nose, hollow cheeks with fine cheek lines, thin compressed lips, a firm unsmiling expression, and faint horizontal forehead lines, facing nearly forward with his head held level and his gaze directed slightly toward the viewer's left, wearing a dark high-collared garment with a corded fastening, shown from the chest up.
```

## What to remove

Reject any output that describes a desired image treatment instead of the
person. In particular, remove game/style labels, historical-color requests,
studio-lighting requests, background instructions, and game-ready rendering
language. Replace them with observable person traits only.

## Safety and uncertainty rules

- Do not identify the person by name unless the user supplies it.
- Do not infer nationality, politics, religion, ethnicity, sexuality, role,
  rank, unit, or organization from appearance.
- Do not invent a medal, insignia, hat, glasses, facial hair, accessory, or
  clothing detail.
- Use uncertainty internally, then omit the uncertain claim from the final
  one-line output.
