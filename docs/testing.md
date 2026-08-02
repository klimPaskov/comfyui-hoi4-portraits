# Testing and audit notes

## Deterministic build

```bash
python scripts/build_workflows.py
```

This recreates all three editor and API graphs plus `workflows/manifest.json`.
Generated files are deterministic.

## Structural and layout validation

```bash
python scripts/validate_workflows.py
```

The validator checks:

- JSON shape and unique node/link IDs;
- every link endpoint, source slot, target slot, and type;
- allowlisted core-node classes only;
- no Krea or project custom-node classes;
- required `SaveImage` outputs;
- every node contained inside its declared group;
- no overlapping groups;
- no overlapping/too-close nodes within a group;
- one group per node and no node extending beyond its group;
- RealESRGAN → optional FLUX restoration order;
- restoration switch bypass to direct ESRGAN output;
- LoRA-patched model ancestry for the final styled decode;
- final-only background replacement dependency order.
- LoRA strength `0.8` in all default graphs;
- person-only positive prompts after the required `hoi4_portrait,` trigger.

## Unit tests

```bash
python -m unittest discover -s tests -v
```

Tests rebuild into a temporary directory, compare generated artifacts, run the
validator, exercise the installer against a fake ComfyUI tree, verify the model
lock, and check internal documentation links.

## Comfy Cloud preflight

The API files were submitted to Comfy Cloud MCP with `dry_run: true`. All
passed without creating a job or spending credits. The new LoRA filename is a
non-blocking advisory until it is imported into the user's Cloud model
library.

## Local inference evidence

On 2026-08-01, all six pinned model files were downloaded and checksum-
verified. ComfyUI 0.25.0 then ran on a 16 GB Apple-silicon Mac with MPS,
low-VRAM offloading, split cross-attention, no previews, and
`--disable-all-custom-nodes`.

The public graphs remain 832 × 1120, Euler, 20 steps, CFG 5. To complete a
broad local functional suite within the machine's resource limit, test copies
were overridden to 416 × 560. FLUX restoration used two steps; final LoRA
generation used six steps, CFG 5, Euler, and LoRA strength `0.8`.

Successful runs:

- five source portraits through RealESRGAN → FLUX restoration → final LoRA;
- five different source portraits through RealESRGAN → final LoRA;
- five no-input text-to-image portraits;
- one final-image-only BiRefNet background replacement run;
- seven controlled setting variants using a fixed prompt and seed.

The background test replaced the final decode with a completed saved image,
then evaluated only BiRefNet, compositing, and the final switch. It completed
in 7.73 seconds and proves that background work is downstream of generation.

The reduced previews are evidence of executable nodes and connections, not a
claim that six steps match public 20-step quality. See [the rendered results
and setting analysis](test-results.md).

Mechanical validation remains separate from inference validation so resource
limits cannot hide malformed nodes or connections.

Cloud GPU testing later that day completed the ESRGAN-only and full-power
graphs with a compatible catalog LoRA at zero strength, validating both
restoration paths and all three output nodes. A text-to-image run with
background replacement enabled exposed an inverted foreground mask. The
inversion was removed, a direct-mask regression check was added, and the fixed
background branch then completed successfully on Cloud.
