# Screenshots

These images are sanitized public documentation assets. They are not production portrait evidence and contain no source portrait, generated portrait, model weight, or secret.

## Live ComfyUI capture — 2026-07-28

The following UI-only captures were taken from the pinned local `human_local_mac_16gb` graph. They document the actual grouped canvas and the measured local runtime blocker; they do not contain the private input portrait.

![Live human-local workflow overview](assets/live_test_2026-07-28/01_live_human_workflow_overview.png)

![Live human workflow stages](assets/live_test_2026-07-28/02_live_human_workflow_stages.png)

![Live input and preprocessing stages](assets/live_test_2026-07-28/03_live_input_preprocessing.png)

![Live Krea and evidence stages](assets/live_test_2026-07-28/05_live_workflow_detail.png)

![Live preview and save pair](assets/live_test_2026-07-28/06_live_preview_save_pair_clean.png)

![Live MPS/FP8 blocked result](assets/live_test_2026-07-28/07_live_mps_float8_blocked.png)

The actual source, crop, prepared reference, mask, and background composite from the private qualification run remain under the ignored `jobs/` directory. No generated after portrait was produced: the first run stopped on the MPS FP8 capability error, and the reversible fallback run stopped under the 16 GB memory/offload limit before the first sampler step completed.

![Human local workflow graph](assets/workflow_human_local_mac_16gb.png)

*The human local Mac workflow loaded in the pinned ComfyUI editor.*

![Human workflow preview-stage detail](assets/workflow_human_local_mac_16gb_preview_stage.png)

*The colored stage board includes four human-only preview checkpoints: crop/reference, prepared reference, approved background, and final candidate. In the current graph, the final preview shares the exact image input used by `SaveImage`.*

![Example job input contract](assets/input_contract_example.png)

*A fictional, non-executable example of the job contract shape. The paths and background hash are placeholders.*

![Blocked output example](assets/blocked_output_example.png)

*A truthful blocked result: no candidate or final DDS is claimed while production gates are unresolved.*

For authoritative results, use the JSON/Markdown evidence reports linked from [testing and evidence](testing-and-evidence.md).
