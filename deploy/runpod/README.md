# RunPod Pod deployment surface

This directory implements the documented Pod-first deployment shape: raw
ComfyUI remains on `127.0.0.1:8188`, and only the authenticated project REST
gateway is exposed. The Pod uses a persistent volume with these directories:

```text
/workspace/hoi4-portraits/project
/workspace/hoi4-portraits/models
/workspace/hoi4-portraits/huggingface-cache
/workspace/hoi4-portraits/comfyui-output
/workspace/hoi4-portraits/jobs
/workspace/hoi4-portraits/logs
/workspace/hoi4-portraits/dependency-locks
```

The image contains project code and lock metadata only. Model weights,
source portraits, generated portraits, caches, and secrets are mounted or
provided at runtime. `image_lock.json` is intentionally blocked because the
current image lock still lacks the image-specific Python artifact checksum and
exact system package pins, and live GPU compatibility is unverified.
`Dockerfile` refuses to build until that lock is changed to `RESOLVED` and the
caller supplies exact system package pins.

Builds must use the project root as context so the complete checksum-covered
planning package is present: `docker build -f deploy/runpod/Dockerfile .`.
The selected ComfyUI profile lock and the separate project dependency closure
are both SHA-256 verified before installation.

Required non-secret configuration is described by the environment variables in
`09_runpod_architecture.md`; the only mandatory gateway secret is
`PORTRAIT_GATEWAY_TOKEN`. The entrypoint refuses a non-loopback ComfyUI bind,
non-remote profile, incomplete persistent project, missing runtime lock,
missing model mount, or failed health/inventory readiness. An actually empty
project volume is seeded only from the reviewed code payload in the image; the
private immutable style LoRA still has to be supplied on the persistent
project volume. It does not print secret values.

The public REST routes are implemented by
`portrait_pipeline.mcp.gateway`:

```text
POST /v1/uploads
PUT  /v1/uploads/<upload_id>
GET  /v1/uploads/<upload_id>
POST /v1/jobs
GET  /v1/jobs/<job_id>
POST /v1/jobs/<job_id>/cancel
GET  /v1/jobs/<job_id>/outputs
GET  /v1/jobs/<job_id>/outputs/<artifact_id>
GET  /v1/health
GET  /v1/capabilities
```

The `PUT` and upload-status requests carry the owning job id in
`X-Portrait-Job-Id`; the gateway uses it to keep upload metadata and source
bytes inside that job's contained directory.

Every request uses an Authorization-header token. Uploads require an idempotency key,
size and SHA-256 metadata, MIME validation, path containment, and a bounded
body. Jobs require an idempotency key, a completed upload, the normative job
schema, and `agent_remote_runpod`; arbitrary ComfyUI workflow submission is
not accepted. Duplicate job ids are handled by the controller's normalized
input hash. One active GPU job is the default, and the optional bounded idle
shutdown is implemented by the gateway process.

The deployment acceptance remains blocked until a clean empty-volume Pod can
run bootstrap, model restoration, node import, all four workflow validation,
one fixture generation, independent audit, DDS validation, output download,
cancellation, failed-auth, idle-shutdown, and restart tests.
