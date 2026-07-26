# Generic Integration Manifest

**Status:** complete new files plus anchor-based patch templates. Exact live-repository diffs were not possible because the repository URL and checkout were unavailable.

## Complete new-file ledger

| Destination proposal | SHA-256 |
| --- | --- |
| `.agents/skills/hoi4-portrait-pipeline/SKILL.md` | `e9586d914499b0ef55d86c1d67b3227e9d0caabc0780d96404822d57d8207052` |
| `.codex/agents/hoi4_portrait_identity_auditor.toml` | `4bac76adfe566edae71b238b982f17c2444cf78425cc5116adcedcd941107c78` |
| `.codex/agents/hoi4_portrait_pipeline.toml` | `1bd2df0799d9a50bb124f4c1642a09497306fd4a7133a6e570b5965f02b0efa1` |

## Patch-template ledger

| Template | Purpose |
| --- | --- |
| `patches/AGENTS.md.patch.template` | skill, subagent, visual-asset, and MCP routing |
| `patches/asset-routing.patch.template` | real-person source, production, audit, and parent ownership |
| `patches/subagent-routing.patch.template` | fork context, producer, auditor, and parent handoffs |

## Required live discovery

- repository URL and default branch
- current AGENTS files
- existing asset and portrait skills
- current subagent folder and naming conventions
- existing ComfyUI or MCP route
- current DDS converter and validation
- test and release commands

## Apply rule

Add the complete new files only when no equivalent exists. Otherwise merge their contract into the existing owner files. Convert the patch templates into exact unified diffs against the current repository before committing.

## Validation and rollback

Parse TOML, validate Markdown frontmatter, run repository tests, scan the generic files for Chaos Redux leakage, review the Git diff, and preserve a pre-integration commit. Roll back with selective restore or the named commit, never with destructive commands in a dirty worktree.
