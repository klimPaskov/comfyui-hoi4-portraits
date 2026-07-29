# Project style LoRA

The workflows reference `loras/hoi4_portrait_new_style_lora.safetensors` as an immutable project-owned input.

The binary is checksum-locked and ignored by Git. Its public Hugging Face source is [`Hoops-McCann/hoi4-portrait-new-style-lora`](https://huggingface.co/Hoops-McCann/hoi4-portrait-new-style-lora), pinned to commit:

```text
2eb855d3176908af4329640c8d966a1b26fc3d6b
```

The installer downloads the exact pinned safetensors object into this directory, verifies its size and checksum, and stops on an unavailable source, unsupported format, or mismatch. It never commits the binary.

```text
Size      228587816 bytes
SHA-256  2ad94552d151d2dedf151cf7356cdd3ea07677607ff289fc0ac61534b34dead1
```

The ComfyUI loader still selects the local filename because ComfyUI model nodes load materialized files, not HTTP URLs. The workflow must stop on a missing or mismatching file. Do not rewrite, merge, re-train, redistribute, or commit the binary without a new rights decision.
