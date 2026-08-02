# Autoprompter examples

The earlier project used a Qwen vision sidecar. That custom node/service is no
longer embedded because it cannot be imported into Comfy Cloud. The current
instruction remains at
[`prompts/autoprompter_instruction.txt`](../prompts/autoprompter_instruction.txt)
for use with an external vision-language model.

## Required output contract

Output one English line that begins with `hoi4_portrait,` and describes only
the visible person. Include useful facial features, hair, expression, visible
clothing, pose, gaze, and crop. Omit uncertain details.

Never add the game name, a style request, background, lighting, palette,
rendering language, restoration instructions, transformation instructions, or
preservation commands. The trigger and LoRA supply the learned look; the
reference-latent workflow supplies the source image.

## Person-only examples

```text
hoi4_portrait, a middle-aged man with short dark hair brushed back, a small neat moustache, a calm closed-mouth expression and gaze angled slightly upward, wearing a dark three-piece suit, white shirt, and tie, seated at a slight angle with his hands folded and shown from the waist up.
```

```text
hoi4_portrait, a middle-aged man with short dark hair, round dark-rimmed glasses, a long narrow face, a slightly open mouth, and a gaze turned to his left, wearing a dark jacket over a light collared shirt and tie, shown from the shoulders up.
```

```text
hoi4_portrait, a young woman with light skin, dark wavy hair swept back from a side part, wide eyes, a small closed mouth, and a calm direct gaze, wearing a dark dress with a broad light sailor collar and a round pendant, shown from the chest up.
```

```text
hoi4_portrait, an older man with light skin, receding short light hair combed back, deep-set eyes, a long narrow face, a slightly open mouth, and a gaze angled upward, wearing a dark overcoat, white shirt, and dark tie, shown from the chest up at a slight angle.
```

```text
hoi4_portrait, a middle-aged man with a bald crown and short dark hair at the sides, straight brows, a long face, a closed mouth, and a direct gaze, wearing a dark clerical cassock with a piped collar and shoulder cape, shown from the chest up.
```

```text
hoi4_portrait, a middle-aged woman with dark hair pinned into a low bun, arched brows, a firm closed-mouth expression, and a direct gaze, wearing a high-necked dark jacket with a small round brooch, shown from the chest up at a slight angle.
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
