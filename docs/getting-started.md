# Getting started

## 1. Clone without private artifacts

```bash
git clone https://github.com/klimPaskov/comfyui-hoi4-portraits.git
cd comfyui-hoi4-portraits
```

The public clone does not include model weights, source portraits, generated images, caches, secrets, or binary model artifacts. The immutable style LoRA is stored in a private, authenticated Hugging Face repository and remains excluded from Git.

Authenticate with an account that has access before running the installer:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install "huggingface-hub==1.25.1"
.venv/bin/hf auth login
```

The bootstrap recognizes the standard Hugging Face token cache or `HF_TOKEN`. It resolves the exact revision in [`dependencies/models.lock.json`](../dependencies/models.lock.json), verifies size and SHA-256, and writes only the ignored local copy under `loras/`.

If you already have ComfyUI, use [`SETUP_WITH_CODING_AGENT.md`](../SETUP_WITH_CODING_AGENT.md) and the included agent prompt. That route runs `scripts/install_into_existing_comfyui.py`, reports `"comfyui_downloaded": false`, preserves unrelated custom nodes and configuration, and copies all six workflows into ComfyUI’s user workflow directory.

## 2. Install the pinned runtime

The supported installer records preflight evidence before it changes the runtime. A private qualification install must be explicit:

```bash
python3.12 scripts/bootstrap/bootstrap.py \
  --profile local_mac_16gb \
  --private-qualification-install \
  --owner-authorized-private-install \
  --restore-from-lock
```

Use `local_nvidia_16gb` on a local NVIDIA host. `full_power_gpu` and `agent_full_power_gpu` are ComfyUI Cloud routes; local bootstrap does not download their Cloud models. A normal restore remains fail-closed and will stop on missing source, background, license, threshold, checksum, or capability evidence.

The exact model and dependency revisions are recorded in [`dependencies/models.lock.json`](../dependencies/models.lock.json), [`dependencies/autoprompter_runtime.lock.json`](../dependencies/autoprompter_runtime.lock.json), and the runtime profile locks.

## 3. Start the loopback services

Start the preprocessing sidecar in one terminal:

```bash
.venv/bin/python -m portrait_pipeline.preprocessing_service \
  --root "$PWD" --host 127.0.0.1 --port 8790
```

Start ComfyUI in another terminal with the sidecar endpoints explicitly bound to loopback:

```bash
HOI4_PORTRAIT_PROJECT_ROOT="$PWD" \
HOI4_SUBJECT_SERVICE_LOOPBACK="http://127.0.0.1:8790/v1/subject" \
HOI4_MASK_SERVICE_LOOPBACK="http://127.0.0.1:8790/v1/mask" \
.venv/bin/python comfyui/main.py --listen 127.0.0.1 --port 8188
```

Raw ComfyUI is intentionally bound to loopback. Remote operations use the authenticated Comfy Cloud API or authenticated project gateway, never a public raw ComfyUI port.

On Apple Silicon, check the reversible FP8/MPS fallback before starting ComfyUI:

```bash
PYTHONPATH=src .venv/bin/python scripts/runtime/apply_mps_fp8_workaround.py --check
```

Use `--apply` only on the pinned local checkout when the check identifies the expected runtime files. This workaround is not an upstream feature and does not override the local 16 GB capacity gate.

## 4. Load a workflow

Open `http://127.0.0.1:8188/`, click the canvas, and paste the selected UI workflow JSON. On macOS use `Command+V`; on Linux/Windows use `Control+V`. Dragging the same JSON file onto the canvas is also supported by ComfyUI.

For the detected Mac, start with:

```text
workflows/human/local_mac_16gb/human_local_mac_16gb.json
```

The graph should load and show its grouped nodes. Loading is not the same as production generation: the source, background, provenance, threshold, and audit guards still run before any candidate can be accepted.

On a local NVIDIA machine, load:

```text
workflows/human/local_nvidia_16gb/human_local_nvidia_16gb.json
```

## 5. Provide a job contract

Use the exact schema at [`schemas/portrait_job_input.schema.json`](../schemas/portrait_job_input.schema.json). A sanitized example is [`docs/examples/job_input.example.json`](examples/job_input.example.json). Real jobs must use relative paths, an attributed source, an approved background registry entry, and calibrated threshold IDs.

Validate a contract before submitting it:

```bash
PYTHONPATH=src .venv/bin/python - <<'PY'
import json
from pathlib import Path
from portrait_pipeline.contracts import validate_job

root = Path.cwd()
path = root / "jobs" / "<job_id>" / "input.json"
job = json.loads(path.read_text(encoding="utf-8"))
issues = validate_job(job, root)
print(json.dumps({"valid": not issues, "issues": [issue.as_dict() for issue in issues]}, indent=2))
raise SystemExit(0 if not issues else 10)
PY
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
