# ComfyUI Cloud route

The `human_full_power_gpu` and `agent_full_power_gpu` profiles are the remote full-power profiles. They use authenticated Comfy Cloud access; there is no separate remote deployment directory.

## Current status

**BLOCKED_CLOUD_NODE_MODEL_PARITY** — OAuth authentication is configured and the signed-in Cloud UI shows `5 / 5 runs left`. All six workflows were imported and saved, but the human and agent full-power graphs report unsupported project-owned `HOI4*`/`Krea2Edit*` nodes and missing LoRAs. The immutable style LoRA is now available from a private, revision-pinned Hugging Face repository for a future Creator/Pro model import, but it has not been imported into Cloud. Hosting the weight does not make unsupported node classes available. No run was submitted. The complete point-in-time probe is recorded in [`../preflight/comfy_cloud_ui_probe_2026-07-29.md`](../preflight/comfy_cloud_ui_probe_2026-07-29.md).

No Comfy Cloud MCP setup is part of the current delivery. Raw local ComfyUI stays on `http://127.0.0.1:8188`; any future direct Cloud API use must use HTTPS and `X-API-Key`.

## Enable the route

1. Upgrade to Creator or Pro only if you want to use Comfy Cloud model import and API access.
2. Add a Hugging Face read token in Cloud Secrets, then import the exact pinned private URL from [`dependencies/models.lock.json`](../../dependencies/models.lock.json).
3. Confirm every required node class through Cloud’s live node inventory. A saved graph with unsupported nodes is not runnable.
4. If using the Cloud API later, create a key and export it only in the local shell or secret manager:

   ```bash
   export COMFY_CLOUD_API_KEY='paste-the-key-locally'
   ```

5. Do not put any token in a job contract, workflow JSON, `.env` committed to Git, screenshot, log, or chat.
6. Run the Cloud preflight and import the generated workflow files only after node/model parity passes. Importing and saving a graph with red errors is evidence of transport only, not a runnable workflow.

The documented Cloud API uses `https://cloud.comfy.org/api/object_info`, multipart `/api/upload/image`, `/api/prompt`, `/api/job/{prompt_id}/status`, and `/api/view`. See the [official Cloud API reference](https://docs.comfy.org/development/cloud/api-reference).

## Required tests after access is enabled

- Import and schema-check every workflow without changing locked controls.
- Run one human full-power job using the approved source/background contract.
- Run one agent full-power job with a parent-supplied prompt in the job contract. The parent writes the country/role-aware prompt from the source record; the workflow itself must not invent it.
- Record Cloud job ID, model/node revisions, upload/output checksums, latency, failures, and billing/plan response.

## Current Cloud limitation

Comfy Cloud provides pre-installed node packs rather than arbitrary project custom-node installation. Its model-import feature is limited to supported Civitai/Hugging Face links and Creator/Pro access; local-drive upload is not supported. The project’s private custom nodes and immutable local LoRA therefore remain a hard stop until an approved Cloud-supported distribution and capability path exists.
- Keep both outputs in evidence only until the independent auditor returns PASS for identity, geometry, expression, accessories, masks, style, and provenance.
