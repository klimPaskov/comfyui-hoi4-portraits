# Chaos Redux Portable Integration Package

This directory is a drag-and-drop proposal generated from the complete uploaded Chaos Redux source snapshots. It is not proof that the remote Windows working copy still matches those snapshots.

## Contents

- `replacements/` contains the full intended destination tree, including complete replacement files and the three new files.
- `new/` contains only the three new files for easier review.
- `patches/` contains unified diffs for every modified baseline file.
- `manifest.md` records destination paths, source hashes, replacement hashes, installation order, validation, and rollback.
- `replacement_manifest.json` is the machine-readable file ledger.

## Hard topology gate

Direct integration is allowed only when the implementation session proves read and write access to both:

- `/Users/klimpaskov/Documents/Projects/comfyui-hoi4-portraits`
- the live Chaos Redux repository on the Windows machine

Record machine names, absolute roots, transport, permissions, credential boundary, line-ending policy, and rollback method. Do not assume one Codex session can access both computers.

When direct access is unavailable, copy this package to the Windows machine and apply it against the live repository there. Portrait jobs can still run on the Mac or authenticated RunPod route through portable checksummed job and result packages.

## Files introduced

- `.agents/skills/hoi4-portrait-pipeline/SKILL.md`
- `.codex/agents/chaosx_hoi4_portrait_pipeline.toml`
- `.codex/agents/chaosx_portrait_identity_auditor.toml`

## Files updated from uploaded baselines

- `AGENTS.md`
- `.agents/skills/chaos-redux-event-assets/SKILL.md`
- `.agents/skills/chaos-redux-subagents/SKILL.md`
- `.codex/agents/chaosx_asset_source_researcher.toml`
- `.codex/agents/chaosx_generated_event_art.toml`
- `.codex/agents/chaosx_country_package_auditor.toml`
- `.codex/agents/chaosx_skill_maintainer.toml`

## Installation order

1. Create a dedicated branch from the current live default branch.
2. Back up every destination file listed in `manifest.md` or rely on a clean Git worktree and a named restore commit.
3. Compare the live source SHA-256 values with the uploaded baseline hashes in `manifest.md`.
4. When a live file hash matches, apply the corresponding unified diff or copy the replacement file.
5. When a live file hash differs, read the live file and regenerate the patch. Do not overwrite it with the snapshot replacement.
6. Add the three new files.
7. Validate TOML, Markdown frontmatter, routing text, and repository policy.
8. Run the repository's own tests and any skill or agent discovery checks.
9. Review the complete diff before committing.
10. Commit in bounded units. Do not force-push.

## Safe Windows review commands

Run from the live Chaos Redux root in PowerShell.

```powershell
$ErrorActionPreference = "Stop"

# Review destination state.
Get-FileHash .\AGENTS.md -Algorithm SHA256
Get-FileHash .\.agents\skills\chaos-redux-event-assets\SKILL.md -Algorithm SHA256
Get-FileHash .\.agents\skills\chaos-redux-subagents\SKILL.md -Algorithm SHA256
Get-FileHash .\.codex\agents\chaosx_asset_source_researcher.toml -Algorithm SHA256
Get-FileHash .\.codex\agents\chaosx_generated_event_art.toml -Algorithm SHA256
Get-FileHash .\.codex\agents\chaosx_country_package_auditor.toml -Algorithm SHA256
Get-FileHash .\.codex\agents\chaosx_skill_maintainer.toml -Algorithm SHA256

# After reviewed copy or patch application.
python -c "import pathlib,tomllib; [tomllib.loads(p.read_text(encoding='utf-8')) for p in pathlib.Path('.codex/agents').glob('*.toml')]; print('TOML OK')"
git diff --check
rg -n "hoi4-portrait-pipeline|chaosx_hoi4_portrait_pipeline|chaosx_portrait_identity_auditor" AGENTS.md .agents .codex/agents
rg -n "fork_context=false" AGENTS.md .agents/skills/chaos-redux-subagents/SKILL.md .agents/skills/hoi4-portrait-pipeline/SKILL.md
rg -n "central MCP skill|self-approve|independent" .agents/skills/hoi4-portrait-pipeline/SKILL.md .agents/skills/chaos-redux-subagents/SKILL.md
```

Use the repository's normal parser, lint, and test commands after these structural checks.

## Post-copy acceptance

- The new skill has valid YAML frontmatter.
- Every TOML file parses.
- No new central MCP skill or router exists.
- Real-person source research ends at the immutable source and exact-crop handoff.
- Real-person production routes to `chaosx_hoi4_portrait_pipeline`.
- Independent review routes to `chaosx_portrait_identity_auditor`.
- The producer cannot approve itself.
- The auditor cannot generate, edit, rank, select, or convert candidates.
- Every custom subagent route requires `fork_context=false` and a context-complete prompt.
- Generated event art still owns eligible fictional portraits and cannot generate grounded substitutes.
- The country auditor refuses to wire an unaudited real-person portrait.
- The parent agent retains final character, GFX, live-consumer, in-game validation, and completion ownership.

## Rollback

Before applying, make a clean commit or copy the overwritten files to a dated directory outside the repository.

For a clean Git branch:

```powershell
git status --short
git diff --check
git restore --source=HEAD -- AGENTS.md .agents/skills/chaos-redux-event-assets/SKILL.md .agents/skills/chaos-redux-subagents/SKILL.md .codex/agents/chaosx_asset_source_researcher.toml .codex/agents/chaosx_generated_event_art.toml .codex/agents/chaosx_country_package_auditor.toml .codex/agents/chaosx_skill_maintainer.toml
git clean -f -- .agents/skills/hoi4-portrait-pipeline/SKILL.md .codex/agents/chaosx_hoi4_portrait_pipeline.toml .codex/agents/chaosx_portrait_identity_auditor.toml
```

Do not run the rollback commands when any listed file contains unrelated uncommitted work. Restore from the explicit backup or use selective Git hunks instead.
