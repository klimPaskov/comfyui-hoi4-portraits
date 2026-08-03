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
3. Remove uncertain color/lighting language and any unsupported identity claims.
4. Paste the validated line into the source workflow's positive prompt field.

## Required output contract

Output one concise English line that begins with `hoi4_portrait,` and describes
only the visible person. Include broad age, hair or facial hair, supported
ethnicity, and general clothing classification. Do not repeat crop or framing
controls. Leave emotion, expression, pose, gaze, and facing direction
out of the line: the input portrait is the authority for them, and repeating
them in text can make the final face drift.

Never add the game name, a style request, background, lighting, palette,
rendering language, restoration instructions, transformation instructions, or
preservation commands. The trigger and LoRA supply the learned look; the
reference-latent workflow supplies the source image.

## Examples used in the gallery

The six supplied source portraits use concise person-only prompts. Pose and
expression come from the source reference. These exact descriptions appear
beside the matching images in the main README.

```text
hoi4_portrait, an Irish middle-aged man with short wavy dark hair and a moustache, wearing a dark civilian suit.
```

```text
hoi4_portrait, an Irish young woman with dark hair swept back, wearing a dark civilian dress with a light collar.
```

```text
hoi4_portrait, an Irish young man with dark hair combed back, wearing a dark civilian suit with a light collar and tie.
```

```text
hoi4_portrait, an Irish middle-aged man with receding dark hair and prominent ears, wearing a military uniform.
```

```text
hoi4_portrait, an Irish slender middle-aged man with neatly parted dark hair and round wire-frame glasses, wearing a dark civilian suit.
```

```text
hoi4_portrait, an Irish older man with sparse dark hair at the sides, wearing dark clerical clothing.
```

## What to remove

Reject any output that describes a desired image treatment instead of the
person. In particular, remove game/style labels, historical-color requests,
studio-lighting requests, background instructions, and game-ready rendering
language. Replace them with observable person traits only.

## Safety and uncertainty rules

- Do not identify the person by name unless the user supplies it.
- Do not infer nationality, politics, religion, sexuality, role, rank, unit, or
  organization from appearance. Use ethnicity or nationality only when the
  source context supplies it.
- Do not invent a medal, insignia, hat, glasses, facial hair, accessory, or
  clothing detail.
- Use uncertainty internally, then omit the uncertain claim from the final
  one-line output. Do not over-list wrinkles or other micro-details.
