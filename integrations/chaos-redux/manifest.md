# Chaos Redux Integration Manifest

**Baseline:** complete uploaded Chaos Redux snapshots read on 2026-07-26

**Application rule:** compare against the live Windows repository before every overwrite. A baseline hash mismatch requires a regenerated patch.

## Destination ledger

| Destination | Mode | Uploaded source | Source SHA-256 | Proposed SHA-256 | Patch |
| --- | --- | --- | --- | --- | --- |
| `AGENTS.md` | replace after live comparison | `AGENTS(4).md` | `ed9cb54702589a3663273e96fb150259551394f0eed78ddf5d1889dad58c41fe` | `fd3c73004c10eb26333d6c49f6c3afde65c6b1d47d87dcf7b114ee15125f020b` | `patches/AGENTS.md.patch` |
| `.agents/skills/chaos-redux-event-assets/SKILL.md` | replace after live comparison | `chaos-redux-event-assets(4).md` | `2b7d63f1407d861c70b44f62b0ab82ad5a653253de87c7ac667e19a4e06a6941` | `476be4c4335d5ba4463f69773faa03c6d97a14ed19db95a0fb8b4f2e55de90e9` | `patches/agents__skills__chaos-redux-event-assets__SKILL.md.patch` |
| `.agents/skills/chaos-redux-subagents/SKILL.md` | replace after live comparison | `chaos-redux-subagents(4).md` | `148d7311e488b75b645ebb218d14bf32386db580aee2cdb39b65a452ead621c2` | `394c789e90bfb0fcd928e0192a7697da48a8a85cba0675c6a06a99a8ae8ab3b5` | `patches/agents__skills__chaos-redux-subagents__SKILL.md.patch` |
| `.codex/agents/chaosx_asset_source_researcher.toml` | replace after live comparison | `chaosx_asset_source_researcher(1).toml` | `ebbbd47ffb0b931575c4e37ba7a5cec434df09dc00d5fc5807509621d919ccf9` | `bed9d44083d7939f678a3608daa24e13245d49324c935825054d7101282a6545` | `patches/codex__agents__chaosx_asset_source_researcher.toml.patch` |
| `.codex/agents/chaosx_generated_event_art.toml` | replace after live comparison | `chaosx_generated_event_art(1).toml` | `fdc4610d1d17353ce9a3736a7aaf7f9c809d1a12634d4f238747945f60fe7b52` | `1bd554b061f249789ee69d24a2c29116b38c24843b5eeaa4e44cbd94a6cd1e61` | `patches/codex__agents__chaosx_generated_event_art.toml.patch` |
| `.codex/agents/chaosx_country_package_auditor.toml` | replace after live comparison | `chaosx_country_package_auditor(1).toml` | `eb6564e92e1244c0e3396c1beaf2f81ad078fa50b885e9ca043b5d7f0bf0fe6b` | `4250e469f45ad5d6de5a5c6c813c5b1bee9fe6607b5878f3df95bd79ade207b2` | `patches/codex__agents__chaosx_country_package_auditor.toml.patch` |
| `.codex/agents/chaosx_skill_maintainer.toml` | replace after live comparison | `chaosx_skill_maintainer(1).toml` | `c6c431d50d070be8eec67ad400fd5caada97035071eb74d2907623c7fea2fc9d` | `e303ebe9b7ea8010d571ff3aca71b9e3f8edc5e116d5391ee52faa31038f25a5` | `patches/codex__agents__chaosx_skill_maintainer.toml.patch` |
| `.agents/skills/hoi4-portrait-pipeline/SKILL.md` | new | `new file` | `n/a` | `a2ab2a531bcfdd7b7689d58f667fea0b591f81efe5977859292d35f929405b8b` | `n/a` |
| `.codex/agents/chaosx_hoi4_portrait_pipeline.toml` | new | `new file` | `n/a` | `fdd3193d92b637f8de492541516d3ad3148b6e3b1a9d9a66cf4e79b16b6c8a4a` | `n/a` |
| `.codex/agents/chaosx_portrait_identity_auditor.toml` | new | `new file` | `n/a` | `d80ebe102f0fa7d5679880c9b6a4e22f4d8a25143f5042b526cbbc5b85fc6747` | `n/a` |

## Installation order

1. Preflight topology and permissions.
2. Create a dedicated Git branch and clean checkpoint.
3. Hash live destination files.
4. Apply patches only to matching baselines.
5. Regenerate patches for mismatched live files.
6. Add the three new files.
7. Parse TOML and validate Markdown frontmatter.
8. Run repository validation and review the diff.
9. Commit in bounded units and push without force.

## Overwritten-file list

- `AGENTS.md`
- `.agents/skills/chaos-redux-event-assets/SKILL.md`
- `.agents/skills/chaos-redux-subagents/SKILL.md`
- `.codex/agents/chaosx_asset_source_researcher.toml`
- `.codex/agents/chaosx_generated_event_art.toml`
- `.codex/agents/chaosx_country_package_auditor.toml`
- `.codex/agents/chaosx_skill_maintainer.toml`

## New-file list

- `.agents/skills/hoi4-portrait-pipeline/SKILL.md`
- `.codex/agents/chaosx_hoi4_portrait_pipeline.toml`
- `.codex/agents/chaosx_portrait_identity_auditor.toml`

## Source-version notes

- The uploaded snapshots may be older than the live Windows repository.
- The package preserves full snapshot replacements for review and drag-and-drop use only when live hashes match.
- The unified patches are safer than full overwrite when the live file contains newer unrelated work.
- The standalone portrait project, Mac hardware, live Chaos Redux converter, vanilla files, canonical portrait references, and live MCP route were unavailable during planning.

## Validation

- all TOML parses with Python `tomllib`
- new skill frontmatter contains `name` and `description`
- new routing names resolve to real files
- source, producer, auditor, and parent boundaries remain distinct
- no unauthenticated public ComfyUI guidance
- no producer self-approval
- no grounded-person generated substitute
- parent final wiring and in-game evidence remain required

## Rollback

Restore the pre-integration Git commit or the explicit backup of every overwritten file, then remove the three new files. Do not use broad `git clean` or `git reset --hard` in a worktree with unrelated uncommitted work.
