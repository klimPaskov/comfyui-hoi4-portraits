# Security, Licensing, and Provenance

## Source image policy

Real historical or grounded identities use attributed real photographs or user-provided authorized photographs. The pipeline does not generate a substitute person. Record:

- source URL or user-provided classification
- attribution and archive
- date when known
- rights or license notes
- download date
- original checksum
- source ownership search when the mod already has a character roster

A source with unclear rights can be retained for private review only when the applicable use permits it. Do not bundle it in a public integration package without a resolved redistribution right.

## Consent and likeness

This system is designed for attributed historical and authorized portrait work. It is not a face-swap service. Do not use the identity-edit model's face, head, eye, or person replacement capabilities. Prompts and graph policy reject swap verbs and subject replacement routes.

For living people or private photographs, require a user authorization record and apply private retention by default.

## Model licenses

Store exact license texts and notices for:

- Krea 2 base model
- Krea 2 identity edit derivative
- Qwen VLM models and GGUF files
- ComfyUI and Manager
- custom nodes
- BiRefNet
- DDColor
- Real-ESRGAN
- OpenCV model files
- MediaPipe assets
- every style-audit dependency

The Krea identity model card states that it uses the Krea 2 Community License and describes commercial, moderation, and disclosure obligations. Implementation must read the actual license agreement and decide whether local use, public deployment, derivative distribution, and output distribution fit the project. A summary in this plan is not legal clearance.

## Background rights

The approved background registry stores a redistribution rule:

- `bundle_allowed`: source can be committed or distributed under its terms
- `local_copy_only`: bootstrap may copy from an installed game or private repository, but Git and portable packages exclude it
- `blocked`: no use until permission is resolved

When a background comes from installed HOI4, the resolver records the local source and copies it only into `backgrounds/private/`. The portable package contains resolver instructions, not the proprietary asset.

## Secrets

Secrets live in:

- macOS Keychain or process environment for local use
- RunPod secrets for remote use
- GitHub credential manager or environment for repository operations

Forbidden locations:

- source files
- workflow JSON
- job input and output
- manifests
- logs
- Docker image layers
- Git commits
- Markdown docs

Implement secret scanning before every commit and release.

## Network security

- local ComfyUI binds to loopback
- remote ComfyUI binds to loopback inside the container
- only the authenticated gateway is exposed
- allowlisted origins and request methods
- strict upload size and MIME checks
- no URL-based source fetching in workflow nodes
- no arbitrary graph submission
- no arbitrary output path
- no shell arguments derived from job text
- rate limiting and audit logs

## Custom-node security

A custom node executes with the ComfyUI process permissions. Before installation:

- inspect repository ownership and history
- pin commit
- inspect install files and dependencies
- scan for shell, subprocess, network, arbitrary file, pickle, and dynamic import behavior
- run in a constrained test environment
- record the review

The project node pack avoids network access except the explicit loopback autoprompter client in human profiles. It uses allowlisted roots and atomic writes.

## Biometric-derived data

Face embeddings, landmarks, and comparison sheets can be sensitive. Treat them as private job evidence. Define a retention policy with:

- default retention period
- explicit keep flag for approved mod assets
- deletion of rejected candidates after review
- no telemetry containing biometric data
- no public object-store bucket
- access-control logs

## Provenance ledger

Every artifact row records:

- artifact id
- parent artifact ids
- operation id and version
- parameters
- producer process
- created time
- path
- MIME
- dimensions when relevant
- SHA-256
- rights or privacy classification

The ledger makes it possible to trace the final DDS back to the original bytes.

## Git LFS

Do not use Git LFS to bypass the rule against committing model weights, private sources, or generated real-person portraits. Git LFS is optional only for redistributable large test assets or public reference material after a license review. Even then, prefer download manifests when possible.

## Release scan

Before release:

- secret scan working tree and full branch history
- scan for `.safetensors`, `.gguf`, source portraits, generated portraits, and private backgrounds
- validate license inventory
- verify notices
- verify no job folder or biometric evidence is included
- verify every external URL belongs to a named source
