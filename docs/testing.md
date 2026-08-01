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
- RealESRGAN → optional FLUX restoration order;
- restoration switch bypass to direct ESRGAN output;
- LoRA-patched model ancestry for the final styled decode;
- final-only background replacement dependency order.

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

## Local execution boundary

The local checkout has RealESRGAN and the LoRA but not the gated FLUX.2 Klein
9B base model, Qwen 3 8B encoder, FLUX.2 VAE, or ComfyUI BiRefNet package. The
test Mac also has 16 GB unified memory. A full local image run would therefore
stop at model availability/resources; that is not reported as a graph failure.

On 2026-08-01, ComfyUI 0.25.0 was started locally in CPU and
`--disable-all-custom-nodes` mode. Its live `/object_info` endpoint contained
all 25 node classes used by the workflows. All three API graphs were then sent
to the native `/prompt` validator. Each reached model selection and stopped
only for the four absent files listed above; no unknown class, bad input,
malformed link, or type error was reported. No sampler ran.

Mechanical validation is separated from inference validation so resource
limits cannot hide malformed nodes or connections.
