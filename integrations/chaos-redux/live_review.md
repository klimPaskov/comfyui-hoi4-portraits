# Chaos Redux live review

The live checkout was read before packaging the portable integration files.
The review is recorded in `live_review.json`. Its current baseline is
`master@420cfb326e8ec78ec5641b152f32fce2b2d94db6` with unrelated untracked user
work under `docs/assets/` and `gfx/interface/ideas/test_icon.dds`; those files
were not touched.

The portable package is ready for a parent-controlled, selective application,
but direct application is blocked. The live repository has no
`.agents/skills/chaos-redux-subagents/SKILL.md`, no `.codex/agents/*.toml`, no
vanilla game checkout, and differs materially from the uploaded replacement
snapshots. The current live converter and sampled portrait headers are recorded
alongside the divergence, so the parent must regenerate a target-specific diff
and run a live in-game consumer check before any portrait is wired.

