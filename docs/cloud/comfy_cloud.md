# ComfyUI Cloud route

The `human_full_power_gpu` and `agent_full_power_gpu` profiles are the remote full-power profiles. They use authenticated Comfy Cloud access; there is no separate remote deployment directory.

## Current status

**BLOCKED_CLOUD_NODE_MODEL_PARITY** — OAuth authentication is configured and the signed-in Cloud UI shows `5 / 5 runs left`. All six workflows were imported and saved, but the human and agent full-power graphs each report three errors: Cloud does not support the project-owned `HOI4*`/`Krea2Edit*` custom-node pack and does not have the immutable style LoRA or pinned identity-edit LoRA. No run was submitted. The complete probe is recorded in [`../preflight/comfy_cloud_ui_probe_2026-07-29.md`](../preflight/comfy_cloud_ui_probe_2026-07-29.md).

The current Codex task still exposes no callable Comfy Cloud MCP tool even though OAuth is configured, so the authenticated Cloud UI was used for import and parity inspection. This is not an execution qualification. The official MCP documentation describes the service as public beta; discovery is free, while generation consumes Cloud credits and may require a subscription or available credit balance.

The project-owned adapter remains the default orchestration boundary until first-party MCP access and complete operation parity are proven. Raw local ComfyUI stays on `http://127.0.0.1:8188`; direct project API requests use HTTPS and `X-API-Key`. If the Codex Cloud MCP server is available in the client, use OAuth at `https://cloud.comfy.org/mcp` instead of placing a key in this repository.

## Enable the route

1. For MCP, add `https://cloud.comfy.org/mcp` in Codex Settings → MCP servers, choose Streamable HTTP, save, and click **Authenticate**. The official setup is documented [here](https://docs.comfy.org/agent-tools/mcp).
2. If free runs/credits are visible in the Cloud billing status, they may be used for the two requested tests only after node/model parity passes; otherwise activate an eligible plan at [ComfyUI Cloud](https://cloud.comfy.org/).
3. For the project-owned API adapter, create a key at [platform.comfy.org/login](https://platform.comfy.org/login), following the [official API-key instructions](https://docs.comfy.org/development/api-development/getting-an-api-key), then export it only in the local shell or secret manager:

   ```bash
   export COMFY_CLOUD_API_KEY='paste-the-key-locally'
   ```

4. Do not put the key in a job contract, workflow JSON, `.env` committed to Git, screenshot, log, or chat.
5. Run the Cloud preflight and import the six generated workflow files only after the response inventory and node parity checks pass. Importing and saving a graph with red errors is evidence of transport only, not a runnable workflow.

The documented Cloud API uses `https://cloud.comfy.org/api/object_info`, multipart `/api/upload/image`, `/api/prompt`, `/api/job/{prompt_id}/status`, and `/api/view`. See the [official Cloud API reference](https://docs.comfy.org/development/cloud/api-reference).

## Required tests after access is enabled

- Import and schema-check every workflow without changing locked controls.
- Run one human full-power job using the approved source/background contract.
- Run one agent full-power job with a parent-supplied prompt in the job contract. The parent writes the country/role-aware prompt from the source record; the workflow itself must not invent it.
- Record Cloud job ID, model/node revisions, upload/output checksums, latency, failures, and billing/plan response.

## Current Cloud limitation

Comfy Cloud provides pre-installed node packs rather than arbitrary project custom-node installation. Its model-import feature is limited to supported Civitai/Hugging Face links and Creator/Pro access; local-drive upload is not supported. The project’s private custom nodes and immutable local LoRA therefore remain a hard stop until an approved Cloud-supported distribution and capability path exists.
- Keep both outputs in evidence only until the independent auditor returns PASS for identity, geometry, expression, accessories, masks, style, and provenance.
