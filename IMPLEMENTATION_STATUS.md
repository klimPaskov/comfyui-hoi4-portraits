# Implementation status

This branch implements the standalone project, graph builder, project-owned
ComfyUI node pack, strict job/audit contracts, authenticated adapter, fail-closed
bootstrap, experiment design, evidence manifests, independent DDS oracle, and
portable integration packages.

The release is intentionally not marked production-ready. The formal reports
are under `docs/preflight/` and `docs/acceptance/`. The acceptance run returns
exit code `15` (`BACKGROUND_UNRESOLVED`) because the first hard blocker is the
unresolved approved HOI4 background.

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

## Runtime boundary

The four workflows are structurally generated and validated. Their runtime
load/execution status is `BLOCKED_UNVERIFIED` until the pinned ComfyUI runtime,
Krea nodes/models, preprocessing/audit assets, approved background, calibration
thresholds, and (for RunPod) authenticated endpoint are live-tested. No final
PNG, DDS, or mod wiring was created.

