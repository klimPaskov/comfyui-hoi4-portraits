# Workflow guide

All four workflows share the same nine visible stages:

1. Job and source
2. Subject selection
3. Crop and source preparation
4. Color, restoration, mask, and approved background
5. Human autoprompt or agent contract prompt
6. Krea 2 identity edit
7. Immutable HOI4 style LoRA
8. Portrait generation
9. Large previews, evidence export, and save

Local workflows target 12–16 GB NVIDIA GPUs with staged loading. The one-command RunPod installer installs only the human full-power workflow and keeps raw ComfyUI on loopback behind an authenticated SSH tunnel. The agent full-power JSON remains available for contract-driven deployments but is not copied by that installer.

The local graph includes visible 12 GB and 8 GB GGUF placeholders. They are switch points, not automatic substitutions: a user must provide a revision-pinned, checksum-verified, live-compatible model before selecting one.

ControlNet is not included. The accepted graph already uses source conditioning, Krea identity editing, a foreground mask, and an approved background. A ControlNet may be added only after an identity-first experiment demonstrates a measurable improvement without geometry or accessory regressions.
