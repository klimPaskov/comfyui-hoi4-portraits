# Testing and evidence

Run checks from the project root.

## Reproduce checks

```bash
PYTHONPATH=src .venv/bin/python scripts/run_tests.py
.venv/bin/hoi4-portrait-preflight --root .
PYTHONPATH=src .venv/bin/python scripts/run_acceptance.py
```

The acceptance command writes both JSON and Markdown reports under `docs/acceptance/` and returns the documented non-zero exit code when any hard gate is unresolved.

## Current evidence

- `41/41` automated tests pass on the detected Mac runtime; rerun them with `scripts/run_tests.py` after every bounded change.
- The required four workflows plus the local-NVIDIA agent workflow are structurally valid and live-schema loadable in the pinned loopback ComfyUI.
- Local preprocessing artifacts and the private autoprompter health/negative-validation path are verified.
- The live human-local qualification measured the Apple MPS `Float8_e4m3fn` and NVFP4 capability failures. A separate CPU-only NVFP4 fallback then ran the exact human/autoprompter route at 832×1120 for eight steps and produced a real candidate in 34:36; heavy swap, the missing two-run benchmark, unapproved thresholds, and the `UNCERTAIN` independent audit keep production acceptance blocked. See [`preflight/local_human_execution_2026-07-28.json`](preflight/local_human_execution_2026-07-28.json), [`preflight/krea_precision_options_2026-07-28.md`](preflight/krea_precision_options_2026-07-28.md), and [`../scripts/runtime/apply_mps_fp8_workaround.py`](../scripts/runtime/apply_mps_fp8_workaround.py).
- The project-owned staged-load barrier was exercised in the live `human_local_mac_16gb` graph. It correctly released the CPU-resident conditioning stage and reached Krea model loading, but a bounded 208×280 one-step canary still reached approximately 1.02 GiB free RAM and 263.81 MB free swap before the first sampler step. See [`preflight/mps_barrier_canary_2026-07-29.md`](preflight/mps_barrier_canary_2026-07-29.md).
- A fresh retry through the exact live user-facing `human_local_mac_16gb` graph again passed submission, preprocessing, and autoprompting, then was safely interrupted during Krea model loading at approximately 1.07 GiB free unified memory before the first sampler step. No candidate was produced; ComfyUI was restarted successfully. See [`preflight/mps_retry_canary_2026-07-29.md`](preflight/mps_retry_canary_2026-07-29.md).
- The live ComfyUI process was then restarted with the updated custom node and its non-generative prefix was executed through the background guard. All seven structural mask components were written and the eroded foreground interior stayed pixel-identical; Krea sampling was not run in this prefix check. See [`preflight/mask_component_execution_2026-07-29.md`](preflight/mask_component_execution_2026-07-29.md).
- The official lower-storage NVFP4 artifact is also checksum-verified and reaches the sampler on the Mac, but its live MPS dequantization path fails with `Undefined type Float8_e4m3fn`; it is reserved for its pinned NVIDIA Blackwell policy. See [`preflight/krea_precision_options_2026-07-28.md`](preflight/krea_precision_options_2026-07-28.md).
- The private Library of Congress qualification fixture passes YuNet, MediaPipe Face Landmarker, and BiRefNet on MPS. Run it with:

  ```bash
  PYTHONPATH=src .venv/bin/python scripts/preflight/qualify_source_fixture.py --root .
  ```

  Raw landmarks and mattes remain under the ignored `jobs/` root; the checked-in summary is `docs/preflight/source_fixture_execution.json`.
- The full-power autoprompter format and processor schema are verified, but CUDA execution is unavailable on the detected Mac.
- DDS acceptance is synthetic-only; production DDS remains prohibited without an independent auditor PASS.
- The current acceptance report is `BLOCKED` with exit code `20`; schema and service health are passing, while local production generation remains fail-closed.
- When a local profile is blocked before or during generation, the controller writes `jobs/<job_id>/local_generation_unavailable.json` and sets the output warning/error code to `LOCAL_GENERATION_UNAVAILABLE`. The marker records only project-relative evidence and explicitly confirms that no remote job was queued.

## Current blockers

The acceptance report directly records every blocked or deferred gate. The important production blockers are the measured local MPS/FP8 incompatibility, uncalibrated identity/style thresholds, incomplete independent-audit evidence, the still-unqualified source-specific Krea execution path, and the deferred remote RunPod qualification. RunPod is outside the current live scope, but its workflow and authenticated gateway remain fail-closed.

These blockers are deliberate. The project does not label schema validation, preprocessing qualification, dry-run reports, or a blocked output as local image generation.

## Evidence files

- [Initial preflight](preflight/initial_preflight.md)
- [Live ComfyUI compatibility](preflight/live_comfy_compatibility.json)
- [Autoprompter runtime test](preflight/autoprompter_runtime_test.json)
- [Source fixture review](preflight/source_fixture_review.json)
- [Source fixture preprocessing execution](preflight/source_fixture_execution.json)
- [Live human-local execution evidence](preflight/local_human_execution_2026-07-28.json)
- [Mac staged-load barrier canary](preflight/mps_barrier_canary_2026-07-29.md)
- [Mac live retry canary](preflight/mps_retry_canary_2026-07-29.md)
- [Mask component prefix qualification](preflight/mask_component_execution_2026-07-29.md)
- [Background runtime candidate](preflight/background_runtime_candidate.json)
- [Acceptance report](acceptance/acceptance_report.md)
- [Identity/style matrix](../experiments/identity_style_matrix.json)
- [Workflow manifest](../manifests/workflow_manifest.json)
