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

- `28/28` automated tests pass.
- Four workflows are structurally valid and live-schema loadable in the pinned loopback ComfyUI.
- Local preprocessing artifacts and the private autoprompter health/negative-validation path are verified.
- The private Library of Congress qualification fixture passes YuNet, MediaPipe Face Landmarker, and BiRefNet on MPS. Run it with:

  ```bash
  PYTHONPATH=src .venv/bin/python scripts/preflight/qualify_source_fixture.py --root .
  ```

  Raw landmarks and mattes remain under the ignored `jobs/` root; the checked-in summary is `docs/preflight/source_fixture_execution.json`.
- The full-power autoprompter format and processor schema are verified, but CUDA execution is unavailable on the detected Mac.
- DDS acceptance is synthetic-only; production DDS remains prohibited without an independent auditor PASS.
- The current acceptance report is `BLOCKED` with exit code `15`.

## Current blockers

The acceptance report directly records every blocked or deferred gate. The important production blockers are an unresolved approved background and rights record, no production-approved source fixture authorization, uncalibrated identity/style thresholds, pending license review, absent RunPod credentials/image qualification, and no live generic target repository.

These blockers are deliberate. The project does not label schema validation, preprocessing qualification, dry-run reports, or a blocked output as local image generation.

## Evidence files

- [Initial preflight](preflight/initial_preflight.md)
- [Live ComfyUI compatibility](preflight/live_comfy_compatibility.json)
- [Autoprompter runtime test](preflight/autoprompter_runtime_test.json)
- [Source fixture review](preflight/source_fixture_review.json)
- [Source fixture preprocessing execution](preflight/source_fixture_execution.json)
- [Background runtime candidate](preflight/background_runtime_candidate.json)
- [Acceptance report](acceptance/acceptance_report.md)
- [Identity/style matrix](../experiments/identity_style_matrix.json)
- [Workflow manifest](../manifests/workflow_manifest.json)
