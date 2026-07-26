# Codex Goal Prompt

Implement the complete autonomous ComfyUI HOI4 portrait system specified by this planning package in:

`/Users/klimpaskov/Documents/Projects/comfyui-hoi4-portraits`

Read every file in this package before editing or installing anything. Treat the numbered documents, schemas, manifests, integration proposals, and workflow delivery contract as acceptance criteria. Do not redesign or silently simplify the system.

Build four standalone, loadable ComfyUI workflows:

- `human_local_mac_16gb`
- `human_full_power_gpu`
- `agent_local_mac_16gb`
- `agent_remote_runpod`

The human workflows contain the exact autoprompter instruction in `prompts/autoprompter_instruction.txt`. The agent workflows must contain no autoprompter and must receive the prompt through the job contract.

Before installation, run the hardware, topology, dependency, license, source-background, LoRA, and repository preflights. Use only current verified official or primary sources. Pin every dependency and model revision, record checksums, and stop on an unsupported model format, missing node, missing approved background, checksum mismatch, license blocker, or unavailable required capability.

Preserve the existing LoRA as immutable:

`loras/hoi4_portrait_new_style_lora.safetensors`

Use Krea 2 Turbo only after live compatibility verification. Run the required identity-edit and style-LoRA experiment matrix. Select by identity first. Do not use face swapping. Do not create a final DDS or mod integration output unless the separate auditor returns PASS for identity, geometry, expression, accessories, masks, style, and provenance.

Implement the project-owned MCP adapter unless first-party ComfyUI Local MCP access and complete operation parity are proven. Keep raw ComfyUI on loopback. Authenticate every remote operation. Do not put secrets, source portraits, generated portraits, model weights, or caches in Git.

Test the full local route on the detected 16 GB Mac. Report infeasibility honestly if measured evidence shows it cannot run. Keep local preprocessing, prompting, validation, auditing, DDS work, and remote submission usable without relabeling remote generation as local.

Implement the schemas and documented exit codes exactly. Generate all evidence, manifests, comparisons, checksums, benchmark reports, and acceptance reports. Produce the Chaos Redux and generic agentic HOI4 integration packages only after reading each live target repository. Use `fork_context=false` for every custom subagent. The parent agent owns final mod wiring and live-consumer validation.

Work in bounded commits on a dedicated branch. Run the complete acceptance suite before claiming completion. Report every failed, skipped, uncertain, or blocked gate directly.
