# ComfyUI HOI4 Portraits

Fail-closed, auditable ComfyUI workflows for preparing a portrait source for a Hearts of Iron IV portrait. The graph handles source intake, subject selection, crop, conservative preparation, foreground masking, approved-background compositing, prompt control, Krea 2 identity editing, the immutable HOI4 style LoRA, candidate evidence, and human preview checkpoints.

Generation and acceptance are separate. A candidate is never promoted to DDS or mod wiring until an independent auditor returns `PASS` for identity, geometry, expression, accessories, mask integrity, style, and provenance. There is no face-swapping route.

## Current live status

The pinned workflows load in the live local ComfyUI instance. On the detected 16 GB Apple Silicon Mac, the private qualification run passed contract validation, subject selection, preprocessing, masking, approved-background compositing, and Krea model/conditioning setup. The first unmodified MPS attempt stopped at the sampler because the locked official FP8 Krea checkpoint is not supported by Apple MPS:

```text
TypeError: Trying to convert Float8_e4m3fn to the MPS backend but it does not have support for that dtype.
```

The project now includes a reversible local workaround that performs FP8 conversion on CPU and returns supported tensors to MPS. It removes the dtype exception, but the same 16 GB Mac then exhausted practical unified-memory headroom during model/offload and did not complete the first sampler step. This is still a measured local-runtime infeasibility, not a successful portrait generation. No generated “after” portrait, final PNG, DDS, or mod integration is claimed. See the [sanitized execution report](docs/preflight/local_human_execution_2026-07-28.json) and the [MPS workaround](scripts/runtime/apply_mps_fp8_workaround.py).

## Workflows by target

| Workflow | Prompt source | Runtime | Human controls |
| --- | --- | --- | --- |
| [`human_local_mac_16gb`](workflows/human/local_mac_16gb/human_local_mac_16gb.json) | Exact autoprompter instruction | Apple Silicon MPS / 16 GB | Yes |
| [`human_full_power_gpu`](workflows/human/full_power_gpu/human_full_power_gpu.json) | Exact autoprompter instruction | CUDA GPU | Yes |
| [`agent_local_mac_16gb`](workflows/agent/local_mac_16gb/agent_local_mac_16gb.json) | Validated job contract | Apple Silicon MPS / 16 GB | No |
| [`agent_full_power_gpu`](workflows/agent/full_power_gpu/agent_full_power_gpu.json) | Validated job contract | Local NVIDIA CUDA GPU | No |
| [`agent_remote_runpod`](workflows/agent/remote_runpod/agent_remote_runpod.json) | Validated job contract | Authenticated remote CUDA gateway | No |

The human/agent pair is available for both Mac and NVIDIA targets. The original required four profiles remain intact; `agent_full_power_gpu` is an additional local-NVIDIA agent route so an agent can run without RunPod. Human graphs contain the exact text in [`prompts/autoprompter_instruction.txt`](prompts/autoprompter_instruction.txt). Agent graphs contain no autoprompter and accept the prompt only from the job contract. RunPod deployment is documented but deferred from the current live qualification scope.

## Live workflow screenshots

These are screenshots of the user-facing ComfyUI canvas running the pinned human-local graph. They contain workflow UI only; private source portraits and model weights are not checked in.

![Live human-local workflow overview](docs/assets/live_test_2026-07-28/01_live_human_workflow_overview.png)

*The complete color-coded stage board.*

![Live workflow stage board](docs/assets/live_test_2026-07-28/02_live_human_workflow_stages.png)

*The connected route from intake through Krea, style, candidate generation, and evidence export.*

![Live input and preprocessing stages](docs/assets/live_test_2026-07-28/03_live_input_preprocessing.png)

*The source, subject, crop, preparation, and mask/background stages.*

![Live Krea, style, and evidence stages](docs/assets/live_test_2026-07-28/05_live_workflow_detail.png)

*The producer-to-evidence handoff on the right side of the graph.*

![Live preview and save stage](docs/assets/live_test_2026-07-28/06_live_preview_save_pair_clean.png)

*The human preview cluster. The final preview and `SaveImage` consume the same evidence-export image.*

![Measured local Mac blocker](docs/assets/live_test_2026-07-28/07_live_mps_float8_blocked.png)

*The live ComfyUI log showing the original measured MPS/FP8 failure before the local fallback was applied. The graph stops; it does not fabricate an output.*

## Before → after, honestly

The public repository uses sanitized cards for examples. The supplied portrait archive and all private stage images remain under ignored private paths. The local run produced useful “before” evidence—source intake, crop, prepared reference, mask, and approved-background composite—but no “after” candidate because the sampler failed. The private evidence is retained under the job directory and is not redistributed.

![Sanitized input contract](docs/assets/input_contract_example.png)

*Public, fictional input-contract example—not a real portrait.*

![Sanitized blocked result](docs/assets/blocked_output_example.png)

*Public blocked-result example. This is the correct visual state when a hard gate prevents promotion.*

Do not read the screenshots above as a production before/after comparison. A real comparison sheet is created only after a candidate exists and the independent audit has enough evidence to evaluate it.

## Use a workflow

### 1. Clone the public code

```bash
git clone https://github.com/klimPaskov/comfyui-hoi4-portraits.git
cd comfyui-hoi4-portraits
```

The public clone intentionally excludes source portraits, generated portraits, model weights, caches, secrets, and the private immutable style LoRA. Read the [public-repository and licensing policy](docs/licensing-and-public-repository.md) before adding any artifact.

### 2. Install the pinned private runtime

Run the fail-closed installer only on an owner-authorized private machine:

```bash
python3.12 scripts/bootstrap/bootstrap.py \
  --profile local_mac_16gb \
  --private-qualification-install \
  --owner-authorized-private-install
```

The exact model revisions, dependency versions, source URLs, sizes, and SHA-256 values live in [`dependencies/`](dependencies/). Installation stops on an unsupported format, missing node, checksum mismatch, license blocker, or missing capability.

### 3. Start the local services

Start the preprocessing sidecar in one terminal:

```bash
.venv/bin/python -m portrait_pipeline.preprocessing_service \
  --root "$PWD" --host 127.0.0.1 --port 8790
```

Start ComfyUI in another terminal. The environment variables are required so the project nodes can reach the sidecar without exposing it beyond loopback:

```bash
HOI4_PORTRAIT_PROJECT_ROOT="$PWD" \
HOI4_SUBJECT_SERVICE_LOOPBACK="http://127.0.0.1:8790/v1/subject" \
HOI4_MASK_SERVICE_LOOPBACK="http://127.0.0.1:8790/v1/mask" \
.venv/bin/python comfyui/main.py --listen 127.0.0.1 --port 8188
```

On Apple Silicon, verify the local FP8 fallback before starting a qualification run. It patches only the local pinned runtime files, creates timestamped backups, and does not alter model weights or the immutable LoRA:

```bash
PYTHONPATH=src .venv/bin/python scripts/runtime/apply_mps_fp8_workaround.py --check
PYTHONPATH=src .venv/bin/python scripts/runtime/apply_mps_fp8_workaround.py --apply
```

This is a local compatibility workaround, not an upstream ComfyUI feature. It can remove the dtype exception, but it cannot make a 12B Krea route practical on every 16 GB Mac. The measured report remains authoritative.

Open `http://127.0.0.1:8188/`. Raw ComfyUI remains loopback-only. The human local autoprompter is staged through its own loopback sidecar when the graph reaches that node.

### 4. Load one standalone graph

Drag one of the `.json` files from the workflow table onto the ComfyUI canvas. For the detected Mac, begin with:

```text
workflows/human/local_mac_16gb/human_local_mac_16gb.json
```

For a local NVIDIA host, use `human_full_power_gpu.json` for the human route or `workflows/agent/full_power_gpu/agent_full_power_gpu.json` for the agent route. The NVIDIA agent profile uses the same job contract and audit boundaries; it simply selects the CUDA-capable local runtime lock.

The grouped graph is intentionally organized as numbered stages. Human workflows expose review controls; agent workflows do not expose a prompt editor or autoprompter.

### 5. Create and validate a private job contract

Create a private `jobs/<job_id>/input.json` from the normative schema [`schemas/portrait_job_input.schema.json`](schemas/portrait_job_input.schema.json). A real contract needs:

- a project-relative source path and immutable provenance record;
- a matching approved background registry entry and SHA-256;
- a profile matching the loaded workflow;
- a prompt beginning exactly with `hoi4_portrait,` for agent workflows;
- calibrated identity/style threshold IDs before production acceptance.

Validate it before queueing:

```bash
PYTHONPATH=src .venv/bin/python - <<'PY'
import json
from pathlib import Path
from portrait_pipeline.contracts import validate_job

root = Path.cwd()
job_path = root / "jobs" / "<job_id>" / "input.json"
job = json.loads(job_path.read_text(encoding="utf-8"))
issues = validate_job(job, root)
print(json.dumps({"valid": not issues, "issues": [issue.as_dict() for issue in issues]}, indent=2))
raise SystemExit(0 if not issues else 10)
PY
```

### 6. Inspect the human previews

Human graphs include four read-only checkpoints:

1. `PREVIEW 1 • crop / identity reference`
2. `PREVIEW 2 • prepared reference`
3. `PREVIEW 3 • approved background`
4. `PREVIEW 4 • same image as SaveImage`

The fourth preview is deliberately wired to the exact image consumed by `SaveImage`; the visible preview is what the graph is saving. These nodes do not bypass provenance, audit, thresholds, DDS, or integration gates.

### 7. Queue, inspect, and record the result

Use the ComfyUI Run button or the project controller. Keep the live logs open while qualifying a new host. A blocked run is evidence: record its exit code, node, model revision, hardware, and checksum state. Never relabel a schema pass or preprocessing pass as generated output.

### 8. Promote only after the independent audit

The controller selects by identity first, then style. A separate read-only auditor must return an all-gate `PASS` before the PNG can be finalized, DDS can be written, or mod wiring can occur. The graph itself contains no DDS node and cannot self-approve.

## Repository map

- [`docs/getting-started.md`](docs/getting-started.md) — installation and loopback startup.
- [`docs/workflows.md`](docs/workflows.md) — route comparison and stage semantics.
- [`docs/contracts-and-safety.md`](docs/contracts-and-safety.md) — schemas, exit codes, and guards.
- [`docs/testing-and-evidence.md`](docs/testing-and-evidence.md) — repeatable tests and evidence policy.
- [`docs/screenshots.md`](docs/screenshots.md) — public screenshot index.
- [`dependencies/models.lock.json`](dependencies/models.lock.json) — pinned model revisions and checksums.
- [`manifests/workflow_manifest.json`](manifests/workflow_manifest.json) — workflow delivery manifest.

## Public boundary and license

Project-owned code is released under [`LICENSE`](LICENSE). That license does not grant rights to Krea 2, ComfyUI, third-party preprocessing assets, HOI4 assets, private source portraits, or the immutable style LoRA. The LoRA remains local/private because its current rights record does not authorize redistribution.
