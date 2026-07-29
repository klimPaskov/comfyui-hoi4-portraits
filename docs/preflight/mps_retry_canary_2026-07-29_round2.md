# Mac MPS retry canary — 2026-07-29

The exact user-facing `human_local_mac_16gb` graph was submitted through the live loopback ComfyUI API with one candidate, the locked `832x1120` canvas, and the locked eight-step Krea 2 Turbo settings.

- Source intake, subject selection, crop/preparation, mask/background guards, and the exact autoprompter completed.
- Krea model loading was requested, but the first sampler step was not reached.
- Free unified memory fell from about 6.88 GiB after restart to about 1.10 GiB at the loader boundary.
- No new candidate, final preview/save pair, DDS, or mod output was created.
- The interrupt endpoint did not unwind the blocking loader. A controlled ComfyUI SIGINT and restart restored the loopback server successfully.

The machine is therefore usable for local preprocessing, prompting, validation, auditing, and remote submission, but the measured Mac route remains generation-infeasible for the pinned production canvas. Full machine-readable evidence is in [`mps_retry_canary_2026-07-29_round2.json`](mps_retry_canary_2026-07-29_round2.json).
