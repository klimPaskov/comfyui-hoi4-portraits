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
- final-only background replacement dependency order;
- adjustable crop → RealESRGAN order in both source graphs;
- the encoded processed source as the sampler's starting latent, with no empty
  latent in either image-to-image graph;
- LoRA strength `0.7` and six scheduler steps in all default graphs;
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

On 2026-08-02, all six pinned model files were downloaded and checksum-
verified. ComfyUI 0.25.0 then ran on a 16 GB Apple-silicon Mac with MPS,
low-VRAM offloading, split cross-attention, no previews, and
`--disable-all-custom-nodes`.

The public graphs use an 832 × 1120 canvas, LoRA strength `0.7`, Euler, six
steps, and CFG 5. To complete a broad local functional suite within the
machine's resource limit, test copies were overridden to 416 × 560. A fixed-
seed control also ran the same source for 8, 10, and 20 steps.

Successful runs:

- three source portraits through crop → RealESRGAN → FLUX restoration → final LoRA;
- three source portraits through crop → RealESRGAN → final LoRA;
- three no-input text-to-image portraits;
- one fixed-source, fixed-seed Euler comparison at 6, 8, 10, and 20 steps.

The background test replaced the final decode with a completed saved image,
then evaluated only BiRefNet, compositing, and the final switch. It completed
in 7.73 seconds and proves that background work is downstream of generation.

The reduced previews are evidence of executable nodes and connections. They
also make the runtime and visual differences between 6, 8, 10, and 20 steps
directly inspectable. See [the rendered results and setting
analysis](test-results.md).

Mechanical validation remains separate from inference validation so resource
limits cannot hide malformed nodes or connections.

Cloud GPU testing later that day completed the ESRGAN-only and full-power
graphs with a compatible catalog LoRA at zero strength, validating both
restoration paths and all three output nodes. A text-to-image run with
background replacement enabled exposed an inverted foreground mask. The
inversion was removed, a direct-mask regression check was added, and the fixed
background branch then completed successfully on Cloud.
