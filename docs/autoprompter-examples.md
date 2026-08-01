# Autoprompter examples

The earlier project used a Qwen vision sidecar. That custom node/service is no
longer embedded in the v2 workflows because it cannot be imported into Comfy
Cloud. The instruction file remains available at
[`prompts/autoprompter_instruction.txt`](../prompts/autoprompter_instruction.txt)
for use with any external vision-language model.

## Prompts the autoprompter produced

These lines are copied from successful local evidence records from the earlier
pipeline:

```text
hoi4_portrait, an adult man in a formal uniform, neutral expression, direct gaze
```

```text
hoi4_portrait, an adult man in formal military clothing, neutral expression, direct gaze
```

```text
hoi4_portrait, an older man with a reserved expression, direct gaze, close-cropped hair and a moustache
```

```text
hoi4_portrait, middle-aged man, military officer, wearing glasses, dark curly hair, mustache, uniform with four stars on collar, aviator wings on sleeve, serious expression, head slightly turned, eyes slightly apart, straight nose, closed lips, defined jawline and chin, fair skin, symmetrical face, uniform with buttons and pockets, no visible jewelry
```

Treat role, rank, branch, insignia, and color claims as observations to verify,
not facts to invent. Remove any uncertain detail before using a real person's
portrait.

## FLUX.2-ready expansion pattern

Append a preservation and style instruction to the observed traits:

```text
hoi4_portrait, [visible subject traits]. Transform the supplied person into a polished Hearts of Iron IV leader portrait. Preserve exact identity, facial geometry, expression, hairstyle, visible clothing, pose, camera angle, and crop. Use a hand-painted 1930s-1940s grand-strategy portrait finish, restrained brushwork, realistic skin, crisp eyes, soft directional studio light, muted historical colors, and a formal head-and-shoulders composition. Do not invent medals, insignia, hats, glasses, facial hair, or accessories.
```

## Example expanded prompts

Historical officer:

```text
hoi4_portrait, a middle-aged man in a plain period military tunic, wire-frame glasses, dark curly hair, a neat moustache, serious expression, and a slightly turned head. Transform the supplied person into a polished Hearts of Iron IV leader portrait. Preserve exact identity, facial geometry, expression, hairstyle, glasses, moustache, visible clothing, pose, camera angle, and crop. Use restrained brushwork, realistic skin, crisp eyes, soft directional studio light, and muted olive-brown historical colors. Do not invent medals or insignia.
```

Civilian politician:

```text
hoi4_portrait, an older civilian statesman in a dark 1940s suit and tie, reserved expression, direct gaze, close-cropped hair, and a small moustache. Preserve exact identity and all visible features. Render a formal hand-painted grand-strategy head-and-shoulders portrait with realistic skin, crisp eyes, soft studio light, and a muted neutral palette. No uniform, medals, insignia, text, or modern accessories.
```

Fictional leader without a source:

```text
hoi4_portrait, a stern middle-aged 1940s army logistics officer in a plain dark service uniform, direct gaze, closed mouth, neatly combed hair, formal head-and-shoulders composition, hand-painted grand-strategy portrait, restrained brushwork, realistic skin, crisp eyes, soft directional studio light, muted olive and brown historical palette, no visible text.
```

## Output rules for an external autoprompter

- Output one English line beginning with `hoi4_portrait,`.
- Describe only visible identity and composition traits.
- Use `uncertain` internally for ambiguous details, then omit them from the final prompt.
- Do not identify the person by name unless the user supplies it.
- Do not infer nationality, politics, religion, ethnicity, or sexuality from appearance.
- Never invent a role, rank, unit, medal, insignia, or organization.
