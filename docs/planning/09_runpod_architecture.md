# RunPod Architecture

## Deployment choice

Use a reproducible RunPod Pod template first because ComfyUI needs a persistent interactive server, model cache, WebSocket progress, and explicit lifecycle control. A later Serverless variant is allowed only after the Pod route passes and the worker contract can preserve the same job evidence.

## Container architecture

Build a versioned Linux AMD64 image with:

- pinned CUDA base compatible with the selected PyTorch build
- pinned Python
- pinned ComfyUI commit
- current Manager support
- project controller and MCP adapter
- project custom-node package
- pinned `comfyui-krea2edit`
- system libraries required by image decoding and DDS validation
- no model weights or credentials baked into public image layers

The image entrypoint:

1. verifies `/workspace`
2. restores dependency locks
3. verifies model files and downloads only missing approved artifacts
4. starts ComfyUI on `127.0.0.1:8188`
5. starts the project gateway on its internal port
6. runs health and workflow validation
7. marks the Pod ready only after inventory passes

## Persistent volume

```text
/workspace/hoi4-portraits/
  project/
  models/
  huggingface-cache/
  comfyui-output/
  jobs/
  logs/
  dependency-locks/
```

Temporary upload chunks and decoded scratch files may use `/tmp`. Durable source and job evidence stay under the job root until retention cleanup.

## Environment variables

Non-secret configuration:

- `PORTRAIT_PROJECT_ROOT=/workspace/hoi4-portraits/project`
- `PORTRAIT_MODEL_ROOT=/workspace/hoi4-portraits/models`
- `PORTRAIT_JOB_ROOT=/workspace/hoi4-portraits/jobs`
- `COMFYUI_HOST=127.0.0.1`
- `COMFYUI_PORT=8188`
- `PORTRAIT_PROFILE=agent_remote_runpod`
- `PORTRAIT_IDLE_SHUTDOWN_MINUTES=<bounded value>`
- `PORTRAIT_MAX_UPLOAD_BYTES=<bounded value>`
- `PORTRAIT_MAX_ACTIVE_JOBS=1`

Secrets use RunPod secret references:

- `PORTRAIT_GATEWAY_TOKEN`
- `HF_TOKEN` when required by a source
- `GITHUB_TOKEN` only for private source checkout when authorized
- optional object-store credentials

Never print secret values or include them in manifests.

## Network policy

- ComfyUI listens on loopback only.
- The public service is the project gateway.
- Use RunPod HTTP proxy for short authenticated REST operations.
- Use asynchronous submission because the HTTP proxy timeout is 100 seconds.
- Use polling, server-sent events, or an authenticated WebSocket through a supported exposure path for progress.
- Prefer SSH tunneling for development.
- Add request authentication, authorization, rate limits, body limits, MIME validation, and path containment.
- Disable arbitrary ComfyUI workflow submission from the public API. The gateway accepts only registered workflow ids and validated job inputs.

## Remote API flow

1. `POST /v1/uploads` creates an upload id.
2. Upload source bytes with checksum and size.
3. `POST /v1/jobs` validates the job and returns HTTP 202 plus job id.
4. `GET /v1/jobs/<id>` returns state and progress.
5. `POST /v1/jobs/<id>/cancel` requests cancellation.
6. `GET /v1/jobs/<id>/outputs` returns authorized descriptors after terminal state.
7. The MCP adapter maps its tools to these routes.

Every caller request has an idempotency key. Duplicate submission returns the existing job rather than creating a new paid run.

## Queue and cancellation

Use one active generation job per GPU by default. Preprocessing may overlap only after profiling.

Cancellation:

- marks the controller job cancel requested
- calls ComfyUI `/interrupt` for an active prompt
- removes queued prompt entries through the verified queue route
- preserves partial logs and candidate artifacts
- releases models if safe
- returns exit code 32

## Model cache

Models are fetched from official sources named in the lock. The download process:

1. checks expected filename, revision, and size
2. downloads to a temporary path
3. verifies SHA-256
4. atomically moves into the final folder
5. records the cache entry

A checksum mismatch deletes the temporary file and blocks execution. No mirror fallback.

## Logs and observability

Record:

- Pod id and GPU type
- image digest
- ComfyUI and custom-node versions
- queue wait
- stage timings
- peak VRAM and host RAM
- download cache hits and misses
- retry reason
- cancellation
- output checksums
- idle-shutdown decision

Logs redact source URLs containing tokens, authorization headers, query secrets, and personal metadata not needed for operations.

## Cost safeguards

- explicit allowed GPU classes
- maximum candidates and retries
- maximum active jobs
- per-job runtime timeout
- per-job estimated cost before queueing
- account or daily budget threshold
- idle shutdown after the configured period
- no automatic upgrade to a more expensive GPU class
- no provider call when the budget preflight fails

## Clean deployment acceptance

Launch a new Pod with an empty persistent directory and run:

- bootstrap
- model restoration
- custom-node import
- all four workflow validation, even though only remote graph executes
- one fixture generation
- independent audit
- DDS validation
- output download
- cancellation test
- authentication failure test
- idle shutdown test

Keep the first populated volume for normal use. The empty-volume test proves reproducibility.
