# Getting started

## 1. Clone without private artifacts

```bash
git clone https://github.com/klimPaskov/comfyui-hoi4-portraits.git
cd comfyui-hoi4-portraits
```

The public clone does not include model weights, source portraits, generated images, caches, secrets, or the private immutable LoRA. Supply those through the documented private runtime instead of committing them.

## 2. Install the pinned runtime

The supported installer records preflight evidence before it changes the runtime. A private qualification install must be explicit:

```bash
python3.12 scripts/bootstrap/bootstrap.py \
  --profile local_mac_16gb \
  --private-qualification-install \
  --owner-authorized-private-install
```

Use `full_power_gpu` on a CUDA host. Use `remote_runpod` only after the remote image lock and gateway credentials are resolved. A normal restore remains fail-closed and will stop on missing source, background, license, threshold, checksum, or capability evidence.

The exact model and dependency revisions are recorded in [`dependencies/models.lock.json`](../dependencies/models.lock.json), [`dependencies/autoprompter_runtime.lock.json`](../dependencies/autoprompter_runtime.lock.json), and the runtime profile locks.

## 3. Start ComfyUI on loopback

```bash
.venv/bin/python comfyui/main.py --listen 127.0.0.1 --port 8188
```

Raw ComfyUI is intentionally not exposed publicly. Remote operations go through the authenticated project gateway, not directly to ComfyUI.

## 4. Load a workflow

Open `http://127.0.0.1:8188/`, click the canvas, and paste the selected UI workflow JSON. On macOS use `Command+V`; on Linux/Windows use `Control+V`. Dragging the same JSON file onto the canvas is also supported by ComfyUI.

For the detected Mac, start with:

```text
workflows/human/local_mac_16gb/human_local_mac_16gb.json
```

The graph should load and show its grouped nodes. Loading is not the same as production generation: the source, background, provenance, threshold, and audit guards still run before any candidate can be accepted.

## 5. Provide a job contract

Use the exact schema at [`schemas/portrait_job_input.schema.json`](../schemas/portrait_job_input.schema.json). A sanitized example is [`docs/examples/job_input.example.json`](examples/job_input.example.json). Real jobs must use relative paths, an attributed source, an approved background registry entry, and calibrated threshold IDs.

Validate a contract before submitting it:

```bash
PYTHONPATH=src .venv/bin/python -m portrait_pipeline.contracts path/to/job.json
```

If your checkout exposes the console entry point, the equivalent is:

```bash
.venv/bin/hoi4-portrait-validate-job path/to/job.json
```

## What you can test immediately

- workflow loading and node/schema presence;
- prompt-source separation between human and agent graphs;
- local preprocessing, prompt validation, audit negative paths, and DDS synthetic round-trip tests.

Do not treat a blocked-output example or a schema pass as a generated portrait. The current acceptance state is documented in [testing and evidence](testing-and-evidence.md).
