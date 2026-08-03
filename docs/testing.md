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
- supported workflow classes only;
- no Krea dependencies;
- required `SaveImage` outputs;
- every node contained inside its declared group;
- no overlapping groups;
- no overlapping/too-close nodes across the entire canvas, including group boundaries;
- one group per node and no node extending beyond its group;
- RealESRGAN → optional FLUX restoration order;
- restoration switch bypass to direct ESRGAN output;
- LoRA-patched model ancestry for the final styled decode;
- final-only background replacement dependency order;
- adjustable crop → RealESRGAN order in both source graphs;
- the encoded processed source as the sampler's starting latent, with no empty
  latent in either image-to-image graph;
- LoRA strength `0.7` and eight scheduler steps in all default graphs;
- person-only positive prompts after the required `hoi4_portrait,` trigger.

## Unit tests

```bash
python -m unittest discover -s tests -v
```

Tests rebuild into a temporary directory, compare generated artifacts, run the
validator, exercise the installer against a fake ComfyUI tree, verify the model
lock, and check internal documentation links.

## Comfy Cloud preflight

Comfy Cloud MCP accepts the API files with `dry_run: true` without creating a
job or spending credits. The project LoRA filename is an advisory until the
LoRA is imported into the Cloud model library.

## Local inference evidence

The six pinned model files are checksum-verified. ComfyUI 0.25.0 ran with
optional extensions disabled.

The public graphs use LoRA strength `0.7`, Euler, eight steps, and CFG 5. A
fixed-seed control covers the same source at 6, 8, 10, 12, 20, and 35 steps.

The local evidence set includes:

- six source portraits through crop → RealESRGAN → final LoRA;
- three no-input text-to-image portraits;
- one fixed-source, fixed-seed Euler comparison at 6, 8, 10, 12, 20, and 35 steps.

The first three source boards use the source workflow with FLUX restoration
enabled; the other three use the same workflow with restoration disabled. The
no-input gallery is a separate reference.
The boards contain colour, clean crops, and stable framing.

The background test uses a finished saved image in place of the final decode,
then evaluates only BiRefNet, compositing, and the final switch. It completes
in 7.73 seconds and proves that background work is downstream of generation.

The reduced previews show executable connections and make the runtime and
visual differences between 6, 8, 10, 12, 20, and 35 steps directly
inspectable. See [the rendered results and setting
analysis](test-results.md).

Structural checks run separately from inference checks, so resource limits
cannot hide malformed nodes or connections.

Cloud GPU checks cover the source, processing, and text-to-image graphs with a
compatible catalog LoRA at zero strength, both restoration paths, and all three
output nodes. The text-to-image background test also covers the final
foreground-mask connection.
