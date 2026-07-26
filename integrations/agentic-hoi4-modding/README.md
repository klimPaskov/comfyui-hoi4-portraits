# Generic Agentic HOI4 Modding Integration

This package contains complete repository-neutral portrait skill and subagent files. The live generic repository URL and current checkout were unavailable during planning, so this directory does not pretend that an exact diff against current repository files exists.

## Complete proposed new files

- `replacements/.agents/skills/hoi4-portrait-pipeline/SKILL.md`
- `replacements/.codex/agents/hoi4_portrait_pipeline.toml`
- `replacements/.codex/agents/hoi4_portrait_identity_auditor.toml`

These files contain no Chaos Redux paths, prefixes, event ids, or project-specific ownership assumptions.

## Patch templates

- `patches/AGENTS.md.patch.template`
- `patches/asset-routing.patch.template`
- `patches/subagent-routing.patch.template`

The templates define the exact rules that must be merged into the live repository after its current AGENTS, asset skills, portrait rules, subagent definitions, and folder conventions are read.

## Repository discovery gate

Do not invent the repository URL. Resolve it from current project configuration, an existing checkout, Git remotes, or explicit user input.

Suggested checkout area:

`/Users/klimpaskov/Documents/Projects/comfyui-hoi4-portraits/repos/agentic-hoi4-modding`

Before editing:

1. inspect the repository remote and default branch
2. read current AGENTS files
3. read every relevant asset, portrait, DDS, provenance, MCP, and subagent skill
4. inspect actual `.agents` and `.codex/agents` conventions
5. search for an existing portrait or ComfyUI workflow
6. update an existing equivalent instead of duplicating it
7. inspect the repository's converter and validation rules
8. inspect current tests and release process

## Installation plan

1. Fetch the current default branch.
2. Create `feat/hoi4-portrait-pipeline`.
3. Add or merge the generic skill.
4. Add or merge the producer and auditor roles.
5. Apply the three patch templates to the live routing files using their actual names and anchors.
6. Run TOML, frontmatter, routing, repository, and test validation.
7. Review for project-specific leakage and duplicated ownership.
8. Commit in bounded units.
9. Push without force.
10. Open a draft pull request and report branch, commits, checks, and pull-request details.

When the URL, authentication, or permissions are unavailable, produce a clean patch series and, when a local Git repository exists, a Git bundle. Report the exact blocker. Do not invent a pull request.

## Validation

```bash
python - <<'PY'
from pathlib import Path
import tomllib
for path in Path('.codex/agents').glob('*.toml'):
    tomllib.loads(path.read_text(encoding='utf-8'))
print('TOML OK')
PY

git diff --check
rg -n "hoi4-portrait-pipeline|hoi4_portrait_pipeline|hoi4_portrait_identity_auditor" AGENTS.md .agents .codex/agents
rg -n "Chaos Redux|chaosx_|C:/Users/klimp" .agents/skills/hoi4-portrait-pipeline .codex/agents/hoi4_portrait_pipeline.toml .codex/agents/hoi4_portrait_identity_auditor.toml
```

The final `rg` command must return no matches in the three generic files.

## Acceptance

- no Chaos Redux text or paths
- no invented repository URL
- no duplicate portrait workflow when one already exists
- source research, production, audit, and parent wiring remain separate
- producer cannot self-approve
- auditor cannot select a winner
- agent workflows contain no autoprompter
- local and remote profiles call the same standalone contract
- no central MCP skill is created
- no raw unauthenticated ComfyUI endpoint is exposed
- final PNG and DDS remain blocked until independent all-PASS audit
- parent agent retains live-consumer and completion ownership

## Rollback

Restore the pre-integration branch commit or remove the new files and reverse only the reviewed routing hunks. Do not use destructive reset or broad clean commands in a worktree with unrelated changes.
