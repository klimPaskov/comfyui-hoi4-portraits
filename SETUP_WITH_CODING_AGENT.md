# Setup with a coding agent

Give your coding agent [`prompts/install_into_existing_comfyui_agent_prompt.md`](prompts/install_into_existing_comfyui_agent_prompt.md), the repository path, and the path to an existing ComfyUI checkout.

The agent must:

- run all preflights before installing;
- use only pinned revisions and verify every checksum;
- install into the existing ComfyUI checkout without replacing it;
- keep raw ComfyUI on loopback;
- on Windows, copy the four supplied workflows;
- on RunPod, install only `human_full_power_gpu`;
- start the preprocessing and human-autoprompter sidecars when needed;
- stop and report any missing capability or unsupported format;
- run structural and live node/model compatibility checks;
- never claim final acceptance from generation alone.
