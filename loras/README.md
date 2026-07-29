# Project style LoRA

The workflow references `loras/hoi4_portrait_new_style_lora.safetensors` as an immutable project-owned input.

The binary is intentionally checksum-locked and ignored by Git because it is a model artifact and the project’s rights record does not authorize redistribution. It is not stored under a `private/` workflow folder. Obtain the authorized local copy separately, then verify it against:

```text
SHA-256  2ad94552d151d2dedf151cf7356cdd3ea07677607ff289fc0ac61534b34dead1
```

The workflow must stop on a missing or mismatching file. Do not rewrite, merge, re-train, or commit the binary without a new rights decision.
