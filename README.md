# ComfyUI HOI4 Portrait Pipeline Planning Package

**Package date:** 2026-07-26  
**Target project:** `/Users/klimpaskov/Documents/Projects/comfyui-hoi4-portraits`  
**Status:** implementation planning only

This package specifies an autonomous pipeline that turns an attributed photograph of a real person into a Hearts of Iron IV portrait while treating identity as a non-compensable acceptance gate. It does not install ComfyUI, download model weights, run a cloud GPU, edit a live repository, or claim that the workflow has already passed a hardware test.

## Start here

1. Read `00_executive_brief.md` for the design decision.
2. Read `01_current_capability_and_dependency_audit.md` for the live capability findings and unresolved gates.
3. Read `02_system_architecture.md` through `06_autoprompter_specification.md` for the shared system.
4. Read the execution profile that applies to the target machine.
5. Use `20_implementation_order.md` as the implementation sequence.
6. Give `prompts/implementation_goal_prompt.md` to the coding agent together with this whole package.

## Core decision

The system is a controller-led pipeline with four standalone ComfyUI workflow JSON files. ComfyUI owns the model graph and image tensors. A project controller owns job validation, evidence folders, bounded retries, threshold calibration, independent audit, DDS conversion, and optional mod integration. The four graphs are generated from one versioned graph specification so that fixes remain shared while every delivered workflow stays independently loadable.

The current Krea 2 identity route is the community `comfyui-krea2edit` node pack and the Krea 2 Identity Edit LoRA. It is a live implementation candidate, not an assumed guarantee. The implementation must run the comparison experiment in `03_shared_processing_pipeline.md` and select the architecture by measured likeness, style, mask, memory, and reproducibility results.

## Four required workflow artifacts

- `human_local_mac_16gb.json`
- `human_full_power_gpu.json`
- `agent_local_mac_16gb.json`
- `agent_remote_runpod.json`

The human graphs contain the autoprompter. The agent graphs do not contain, invoke, or depend on it.

## Hard blockers carried into implementation

- The actual Mac hardware, macOS version, free disk, and Krea 2 MPS compatibility have not been inspected.
- The existing HOI4 style LoRA file was not available in this environment, so its size, metadata, compatibility, and checksum remain unverified.
- The approved standard HOI4 portrait background was not present. Generation must stop until the background resolver records an exact source, path, checksum, provenance, and redistribution rule.
- The live Chaos Redux repository, its actual converter scripts, installed vanilla HOI4 files, offline Paradox wiki, and canonical portrait reference library were not accessible.
- The generic agentic HOI4 repository URL and checkout were not available.
- ComfyUI Local MCP is in private testing. The baseline implementation is therefore the narrow project-owned MCP adapter specified here, unless first-party access and full operation parity are proven during implementation.

## Planning-package contents

The numbered documents define architecture, workflows, profiles, integration, testing, licensing, release, and implementation order. `schemas/` contains stable machine contracts. `manifests/` contains dependency and workflow templates. `integrations/chaos-redux/` contains complete replacements, unified patches, source hashes, installation order, validation, and rollback. `integrations/agentic-hoi4-modding/` contains complete repository-neutral skill and subagent files plus live-repository patch templates. `templates/standalone_project/` contains the Git ignore and attributes policy. `bootstrap/` contains the autonomous bootstrap command contract.

## Completion boundary

A portrait job is complete only when one candidate passes every mandatory gate, the independent auditor returns PASS, the final PNG is exactly 156 by 210, the DDS passes byte-level and pixel-level validation, and the manifest links every source, intermediate, model, node, prompt, setting, checksum, comparison, and verdict. Mod wiring remains parent-agent work and needs a live in-game consumer check.
