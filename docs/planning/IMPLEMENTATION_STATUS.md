# Implementation status

This branch implements the standalone project, graph builder, project-owned
ComfyUI node pack, strict job/audit contracts, authenticated adapter, fail-closed
bootstrap, experiment design, evidence manifests, independent DDS oracle, and
portable integration packages.

The release is intentionally not marked production-ready. The formal reports
are under `docs/preflight/` and `docs/acceptance/`. The latest acceptance run
is `BLOCKED` with recommended exit code `20` because calibrated identity/style
thresholds, source-specific production qualification, the immutable-LoRA
experiment matrix, and independent all-PASS audit evidence remain unresolved.
The approved background, pinned dependencies, preprocessing artifacts, live
ComfyUI schema, and project-owned loopback services are passing gates.

## Commands

```bash
PYTHONPATH=src python3 scripts/run_tests.py
./scripts/run_experiment_matrix.py
./scripts/run_acceptance.py
./scripts/bootstrap/bootstrap.sh --profile local_mac_16gb --restore-from-lock
```

Bootstrap stops before any download or install while a hard preflight gate is
blocked. `models/`, private backgrounds, job roots, generated portraits, and
caches are ignored by Git. The existing style LoRA remains at its original path
and is verified against SHA-256
`2ad94552d151d2dedf151cf7356cdd3ea07677607ff289fc0ac61534b34dead1`.

The mandatory preprocessing lock now records exact primary-source revisions,
artifact sizes, formats, destination paths, and SHA-256 values for BiRefNet,
DDColor, YuNet, MediaPipe Face Landmarker, and SFace. All five mandatory
artifacts and the pinned BiRefNet runtime source files are installed and
checksum-verified locally; a source-specific qualification fixture has passed
YuNet, MediaPipe, and BiRefNet on MPS. The verification record is
`dependencies/licenses/preprocessing-artifacts.source.md`, with the bounded
execution evidence in `docs/preflight/source_fixture_execution.json`.

## Runtime boundary

The five checked-in workflow artifacts are structurally generated and validated
against the live local ComfyUI node registry. The user-facing MPS server is
healthy on loopback, but the measured [`human_local_mac_16gb` MPS canary](../preflight/mps_canary_2026-07-29.md)
could not complete a sampler step even at `208x280`. The separate
[`CPU fallback canary`](../preflight/cpu_canary_2026-07-29.md) reached Krea model
loading but was interrupted under swap pressure; the earlier full CPU NVFP4
run remains execution-only evidence. These results are recorded as Mac
infeasibility evidence, not silently relabeled as production success. No final
PNG, DDS, or mod wiring was created.

The live graph also includes `HOI4KreaModelLoadBarrier`, which was exercised on
the same Mac after the canary. The barrier released the CPU-resident Qwen
conditioning stage before sampling, but the bounded 208×280 run still reached
approximately 1.02 GiB free RAM and 263.81 MB free swap before the first
sampler step. See [`staged-load barrier evidence`](../preflight/mps_barrier_canary_2026-07-29.md).

The current automated suite is `41/41` passing. The RunPod route remains
deferred by the project owner, and the generic/Chaos integration packages remain
portable and fail-closed until the parent-owned live consumer validation and
final mod wiring gates are completed. The read-only live-target audit is recorded
in [`integration target validation`](../preflight/integration_target_validation_2026-07-29.md).
