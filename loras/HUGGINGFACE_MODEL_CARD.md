---
tags:
  - comfyui
  - lora
  - hoi4
---

# HOI4 portrait new-style LoRA

Private, project-owned style adapter used by the
[`comfyui-hoi4-portraits`](https://github.com/klimPaskov/comfyui-hoi4-portraits)
workflows.

## Immutable artifact

- File: `hoi4_portrait_new_style_lora.safetensors`
- Size: `228587816` bytes
- SHA-256: `2ad94552d151d2dedf151cf7356cdd3ea07677607ff289fc0ac61534b34dead1`

The file is an immutable input. Consumers must verify both size and SHA-256
before loading it and must stop on a mismatch.

## Access and use

This repository is private and exists to provide an authenticated,
revision-pinned source for authorized local setup and Comfy Cloud model import.
No open-source or third-party license is inferred or granted by this model
card. Access does not grant rights to redistribute the weights, source
portraits, HOI4 assets, backgrounds, or generated outputs.

The adapter is loaded with `LoraLoaderModelOnly` after the Krea 2 identity-edit
adapter. It is not a face-swap model. The workflow must not promote a generated
candidate to final DDS or mod integration unless the separate auditor returns
PASS for identity, geometry, expression, accessories, masks, style, and
provenance.
