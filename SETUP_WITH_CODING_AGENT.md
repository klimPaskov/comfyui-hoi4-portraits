# Set up with a coding agent

This package is designed for an existing ComfyUI installation. It does not
contain or download ComfyUI.

1. Extract or copy this package to a permanent folder.
2. Open [`prompts/install_into_existing_comfyui_agent_prompt.md`](prompts/install_into_existing_comfyui_agent_prompt.md).
3. Replace the two path placeholders and choose the detected Mac or NVIDIA
   profile.
4. Give the complete prompt to a coding agent with local filesystem and
   terminal access.

The agent installs the pinned nodes, places all six workflows in ComfyUI’s
workflow directory, adds the project model paths without replacing existing
configuration, downloads checksum-locked model inputs, and runs verification.

The public package excludes ComfyUI, model weights, the private style LoRA,
source portraits, backgrounds, generated portraits, caches, and secrets.
Authorized model downloads happen during setup. Setup success is not a
production portrait PASS; the acceptance report remains authoritative.
