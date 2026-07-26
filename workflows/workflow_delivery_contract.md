# Workflow Delivery Contract

## Required files

Implementation must deliver both UI graph JSON and API-format JSON for each workflow:

```text
workflows/human/local_mac_16gb/human_local_mac_16gb.json
workflows/human/local_mac_16gb/human_local_mac_16gb.api.json
workflows/human/full_power_gpu/human_full_power_gpu.json
workflows/human/full_power_gpu/human_full_power_gpu.api.json
workflows/agent/local_mac_16gb/agent_local_mac_16gb.json
workflows/agent/local_mac_16gb/agent_local_mac_16gb.api.json
workflows/agent/remote_runpod/agent_remote_runpod.json
workflows/agent/remote_runpod/agent_remote_runpod.api.json
```

## Build rule

Maintain one typed graph specification under `src/portrait_pipeline/graph_spec/`. Generate all four graphs through a deterministic builder. Hand-editing one workflow without updating the shared graph specification is forbidden. The builder must assign stable node ids, group names, note text, exposed controls, bypass states, and output names.

## Standalone rule

Every UI JSON must load by itself into the pinned ComfyUI build with no missing-node placeholder. Shared implementation code and models may be common, but no workflow may require another workflow JSON to be open.

## Graph groups

Use these exact top-level group labels in this order:

1. `00 Job and source`
2. `01 Subject selection`
3. `02 Crop and source preparation`
4. `03 Color and restoration`
5. `04 Masks and approved background`
6. `05 Prompt`
7. `06 Krea 2 identity edit`
8. `07 HOI4 style LoRA`
9. `08 Candidate generation`
10. `09 Preview and evidence export`

Human graphs expose source, subject selector, optional crop override, colorization override, conservative restoration level, prompt preview, seed mode, candidate count, and output directory. Identity thresholds, model paths, manifest ids, audit gates, and DDS settings stay locked.

Agent graphs expose no clickable production requirement. Every value comes from validated job JSON. Any node widget that could bypass a gate must be locked or replaced with a controller input.

## Validation

For every workflow, record:

- ComfyUI commit and frontend version
- every core and custom node class
- every node-package version or commit
- every model filename and checksum
- UI JSON and API JSON checksum
- successful import result
- missing-node result
- missing-model result
- one dry validation job
- one real acceptance job for the target profile

The workflow manifest stays `UNVALIDATED` until all required evidence exists.
