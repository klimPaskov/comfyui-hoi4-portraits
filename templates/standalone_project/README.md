# Standalone Project Template Notes

Copy the `.gitignore` and `.gitattributes` files into the implementation repository during project initialization.

The ignore policy intentionally excludes:

- model weights
- the immutable user LoRA
- private source portraits
- generated real-person portraits
- biometric audit evidence
- private or installed-game backgrounds
- ComfyUI and custom-node checkouts
- RunPod caches and outputs
- credentials and logs

Git LFS is not a way around these exclusions. Use it only for redistributable public test fixtures after license review.
