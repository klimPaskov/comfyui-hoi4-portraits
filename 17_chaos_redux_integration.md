# Chaos Redux Integration

## Topology preflight

Chaos Redux normally lives on a remote Windows machine while the portrait project lives on the Mac. One Codex session must not assume it can access both.

Direct integration is allowed only after proving read and write access to:

- `/Users/klimpaskov/Documents/Projects/comfyui-hoi4-portraits`
- the live Windows Chaos Redux repository

Record machine names, paths, transport, permissions, line-ending policy, and rollback capability. If either side is unavailable, use portable integration.

## Direct integration mode

1. Read the live `AGENTS.md`.
2. Read the live current `chaos-redux-event-assets`, `chaos-redux-subagents`, and related subagent TOMLs.
3. Inspect the actual `.agents` and `.codex/agents` folder conventions.
4. Compare them with the proposed files under `integrations/chaos-redux/`.
5. Regenerate diffs against live files.
6. Apply bounded changes.
7. Validate routing, paths, TOML, Markdown, and repository rules.
8. Commit on a dedicated branch.

Do not copy the uploaded snapshot replacements over newer live files without comparison.

## Portable integration mode

The portable package keeps destination structure and includes:

- complete new files
- replacement files generated from the uploaded baseline
- unified diffs
- manifest with destination paths and checksums
- source baseline hashes
- overwrite list
- install order
- post-copy validation
- rollback instructions

The `integrations/chaos-redux/manifest.md` in this package is the proposal manifest. Implementation regenerates checksums after final live review.

## Ownership boundaries

### Existing sourced asset researcher

Owns:

- finding the real photograph
- attribution and rights notes
- immutable original source
- subject ownership search
- exact source crop and crop evidence
- source handoff to the portrait pipeline

It no longer owns Krea generation, final portrait production, identity approval, or DDS conversion for real-person portraits after this integration.

### New portrait pipeline

Owns:

- deterministic preparation after crop intake
- conditional colorization
- conservative restoration and upscale
- subject masks and background replacement
- Krea 2 generation and style LoRA
- candidates and comparisons
- production manifest
- final PNG and DDS after independent PASS

### New identity auditor

Read-only. Owns the independent identity, style, mask, and provenance verdict. It cannot edit images or select the final candidate.

### Generated event art

Retains eligible fictional generated portraits. It must route real and grounded identities to sourced research plus the portrait pipeline. It cannot generate a substitute face.

### Parent coding agent

Owns:

- final character and GFX wiring
- gameplay path
- live consumer
- in-game validation
- completion claim

## Required new files

- `.agents/skills/hoi4-portrait-pipeline/SKILL.md`
- `.codex/agents/chaosx_hoi4_portrait_pipeline.toml`
- `.codex/agents/chaosx_portrait_identity_auditor.toml`

## Existing files to update

At minimum, after live review:

- `AGENTS.md`
- `.agents/skills/chaos-redux-event-assets/SKILL.md`
- `.agents/skills/chaos-redux-subagents/SKILL.md`
- `.codex/agents/chaosx_asset_source_researcher.toml`
- `.codex/agents/chaosx_generated_event_art.toml`
- `.codex/agents/chaosx_country_package_auditor.toml`
- `.codex/agents/chaosx_skill_maintainer.toml`

## Parent prompt contract

Every portrait subagent uses `fork_context=false`. The parent prompt includes:

- subject record name and classification
- source and crop paths
- source and crop checksums
- provenance manifest
- intended HOI4 role
- exact output stem and final path
- approved background registry id
- prompt without the person's name
- local or remote profile
- candidate and retry limits
- threshold ids
- exact handoff path
- forbidden changes and simplifications

## Runtime handoff

The portrait pipeline returns:

- final PNG and DDS
- sprite name proposal
- source and crop evidence
- production manifest
- independent audit
- comparison sheet
- checksums
- exact final path proposal

The parent then checks character ownership, updates character and GFX files, copies the DDS, verifies the live consumer, and records runtime evidence.

## Validation

- TOML parse
- Markdown frontmatter parse
- all named skill and subagent paths exist
- no central MCP skill created
- sourced and generated routes remain distinct
- producer and auditor remain separate
- `fork_context=false` repeated in routing rules
- no real-person generated substitute language remains
- converter ownership is clear
- parent final-wiring ownership is clear
