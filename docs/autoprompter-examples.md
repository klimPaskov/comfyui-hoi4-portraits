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
4. Paste the validated line into the source workflow's positive
   `CLIPTextEncode` node. The workflow itself remains core-node-only and can be
   imported into Comfy Cloud.

## Required output contract

Output one English line that begins with `hoi4_portrait,` and describes only
the visible person. Include useful facial features, hair, expression, visible
clothing, pose, gaze, and crop. Omit uncertain details.

Never add the game name, a style request, background, lighting, palette,
rendering language, restoration instructions, transformation instructions, or
preservation commands. The trigger and LoRA supply the learned look; the
reference-latent workflow supplies the source image.

## Validated outputs used in the gallery

Qwen generated these from the six supplied source portraits. The validated
outputs exclude unsupported color or lighting claims and use consistent pose
wording. These exact descriptions are printed beside the matching images in
the main README.

```text
hoi4_portrait, middle-aged man with short wavy hair, a moustache, wearing a suit and tie with a visible collar and lapels, looking slightly upward with a subtle smile, head tilted slightly to his right, shoulders squared, shown from the chest up.
```

```text
hoi4_portrait, young woman with short dark hair parted to the side, no glasses, wearing a high-collared garment with a visible round fastening, looking directly at the camera with a neutral expression, head slightly tilted, shown from the chest up in an oval crop.
```

```text
hoi4_portrait, young man with dark hair parted on the left, clean-shaven, wearing a collared shirt and tie, looking upward and to his right with a slight smile, head tilted, shown from the shoulders up in three-quarter profile with a visible ear, nose, and chin.
```

```text
hoi4_portrait, middle-aged man with short dark hair, no facial hair, wearing a high-collared uniform with decorative cords and a visible medal, looking slightly to his right with a neutral expression, head tilted slightly and mouth closed, shown from the chest up.
```

```text
hoi4_portrait, a man with short dark hair, round-rimmed glasses, no facial hair, and a long narrow face, dressed in a dark suit with a white collared shirt and dark tie, looking directly at the camera with a neutral expression, his head and shoulders angled slightly to his right, shown from the chest up in three-quarter view.
```

```text
hoi4_portrait, middle-aged man with a receding hairline, no facial hair, a prominent nose, defined jaw and chin, wearing a high-collared garment with a decorative corded tie and buttoned front, looking directly at the camera with a neutral expression and a slight head tilt, shown from the chest up.
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
