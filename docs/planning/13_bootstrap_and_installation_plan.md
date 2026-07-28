# Bootstrap and Installation Plan

## Scope

The implementation agent performs installation later. This planning response performs none of these actions.

## Phase 0: topology and capability preflight

Before writing to either target repository:

- verify the Mac project path
- verify actual Mac hardware and free disk
- verify whether the session can reach the Windows Chaos Redux repository
- verify the generic repository URL and permission
- verify RunPod credentials only through environment or secret manager presence, never by reading values into logs
- verify the style LoRA exists and is immutable
- resolve the approved portrait background

Write a preflight report. A missing required input blocks only the affected route.

## Phase 1: initialize standalone Git project

Create the target directory, initialize Git, create the project layout, add README, AGENTS, schemas, manifests, and `.gitignore`. Record the initial LoRA checksum without adding the weight to Git.

Recommended `.gitignore` classes:

```gitignore
.env
.env.*
!.env.example
jobs/**
!jobs/.gitkeep
models/cache/**
backgrounds/private/**
repos/comfyui/**
repos/custom_nodes/**
loras/*.safetensors
!loras/*.sha256
**/*.ckpt
**/*.pt
**/*.pth
**/*.gguf
**/*.onnx
**/__pycache__/
.DS_Store
*.log
```

Private test fixtures, source portraits, generated portraits, audit embeddings, and RunPod output caches also remain ignored.

## Phase 2: install ComfyUI workspace

Use the current official installation method selected after preflight. For a headless project, prefer `comfy-cli` or a pinned manual checkout. Record the exact commands in the dependency lock and capability report.

Requirements:

- no manual browser installation
- dedicated Python environment
- pinned ComfyUI commit after qualification
- Manager enabled through the supported current mechanism
- loopback server
- automatic startup and stop scripts

## Phase 3: install custom nodes

- install the project node pack from the repository source
- install `comfyui-krea2edit` at the pinned commit
- use Manager registry versions only when the exact revision can be locked
- use direct Git checkout for unregistered or commit-pinned nodes
- install dependencies through the ComfyUI environment
- run import tests before model download

Inspect every custom node for arbitrary execution, network access, install hooks, and license.

## Phase 4: restore models

For every lock entry:

1. verify official repository and immutable revision
2. check redistribution and access terms
3. download to a temporary file
4. verify size and SHA-256
5. move atomically to the exact ComfyUI model folder
6. create no duplicate weight copies unless a loader requires one
7. record local path and checksum

Use symlinks or ComfyUI extra model paths for the immutable style LoRA when supported.

## Phase 5: build project nodes and workflows

- implement deterministic project nodes
- build graph specification
- generate four UI JSON and four API JSON files
- validate node classes and model references
- load each UI graph in the pinned frontend
- record checksums

## Phase 6: implement controller and MCP

- implement schemas and exit codes
- implement ComfyUI API client
- implement WebSocket progress
- implement project-owned MCP server
- implement local stdio registration
- implement authenticated remote gateway
- test interruption and recovery

## Phase 7: calibrate audit

Build calibration fixtures, run same-person and different-person comparisons, choose thresholds, write locked threshold files, and obtain reviewer approval. Production stays disabled until this completes.

## Phase 8: local acceptance

Run the full local suite. Produce capability, memory, runtime, thermal, quality, and failure reports. Do not mark local generation available until two consecutive full runs pass.

## Phase 9: RunPod acceptance

Build the container, create template, attach persistent storage, restore from locks, run remote tests, verify authentication and cancellation, and measure cost.

## Phase 10: integrations

Inspect live repositories, apply or regenerate the proposed patches, run repository tests, and create portable packages or draft pull requests as allowed.

## User interaction boundary

The implementation must not require the user to:

- install ComfyUI manually
- click Manager install buttons
- move model files
- repair node paths
- edit workflow JSON
- start servers by hand for normal operation
- convert DDS in Photoshop

The user may need to provide or authorize:

- source photographs
- credentials through the operating system or provider secret store
- a repository URL that cannot be discovered
- approval for license terms
- the standard background source when it is not present
- final review for an UNCERTAIN identity case
