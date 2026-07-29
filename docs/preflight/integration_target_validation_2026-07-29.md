# Integration target validation — 2026-07-29

Status: **PORTABLE_VALIDATION_PASS_LIVE_APPLY_BLOCKED**

This is a read-only audit of the local live target checkouts. No target repository was edited, reset, cleaned, committed, or pushed.

## Chaos Redux

- Target snapshots found: `2`.
- Installed-game target consumer surface: `PRESENT`.
- Direct apply: `BLOCKED_READ_ONLY_AUDIT`.
- Baseline comparisons are recorded in the JSON report; divergent or missing files require a regenerated patch and parent review.

## Generic Agentic HOI4 Modding

- Portrait package file parity: `PASS`.
- Whole-target setup manifest: `BLOCKED_PREEXISTING_EXPECTED_FILE_DRIFT` (211 mismatches, 0 missing files).
- TOML parse: `PASS`.
- Portrait leak/spawn-policy scan: `PASS`.
- Live consumer validation: `NOT_RUN_PARENT_OWNED`.

## Remaining blockers

- Chaos Redux direct application remains blocked until a clean, current target diff and parent-owned consumer validation exist.
- The generic target has pre-existing setup-manifest expected-file drift and remains uncommitted/unpushed by owner instruction.
- Parent-owned live consumer validation and final mod wiring were not run because no independently audited production candidate exists.

Machine-readable evidence: [`integration_target_validation_2026-07-29.json`](integration_target_validation_2026-07-29.json).
