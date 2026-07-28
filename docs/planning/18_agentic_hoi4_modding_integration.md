# Generic Agentic HOI4 Modding Integration

## Repository discovery

The generic repository URL was unavailable during planning. Implementation must discover it from current project configuration, user environment, or an explicit input. Do not invent a URL.

Suggested checkout path:

`/Users/klimpaskov/Documents/Projects/comfyui-hoi4-portraits/repos/agentic-hoi4-modding`

Before editing:

- read current AGENTS
- read current asset and portrait skills
- read current subagent definitions
- inspect folder and naming conventions
- search for existing portrait, image, provenance, DDS, ComfyUI, or MCP workflows
- update an existing equivalent rather than duplicating it

## Generic files proposed here

- generic `hoi4-portrait-pipeline` skill
- generic portrait producer subagent
- generic read-only identity auditor subagent
- AGENTS and routing patch templates

These files contain no Chaos Redux paths, event ids, prefixes, or project-specific source folders.

## Generic contract

Inputs:

- real or fictional subject classification
- attributed source and exact crop for real people
- prompt
- intended role
- approved background registry id
- profile
- final PNG and DDS paths
- optional mod root, tag, character id, sprite name, and gameplay path

Outputs:

- candidates
- independent audit
- final PNG and DDS after PASS
- manifest and comparisons
- integration handoff

The parent repository agent owns character, GFX, file placement, live consumer, and final validation.

## Local and remote profiles

The generic integration calls the standalone project through the same MCP contract. It does not duplicate ComfyUI installation inside every mod repository. Project configuration stores the MCP command or endpoint without credentials.

## Git workflow

When repository URL, authentication, and permission exist:

1. fetch and update the default branch
2. create `feat/hoi4-portrait-pipeline`
3. add new files and bounded routing updates
4. run repository validation
5. commit in logical units
6. push without force
7. open a draft pull request
8. report branch, commits, checks, and pull request

When unavailable, create:

- a clean patch series
- a commit bundle when a local repository exists
- a destination manifest
- a blocker report naming the missing URL, auth, or permission

## Acceptance

- no Chaos Redux text
- no assumption about mod-root layout without discovery
- no new central MCP skill
- real-person source and audit contract preserved
- producer cannot self-approve
- four standalone workflows remain in the standalone project
- generic repository receives only routing and invocation logic
