# ComfyUI MCP Contract

## Route selection

### First-party Local MCP

ComfyUI documents a first-party local MCP with tools such as `server_info`, `run_workflow`, `job_status`, `wait_for_job`, `watch_job`, `fetch_outputs`, `launch_comfyui`, `stop_comfyui`, `search_templates`, `fetch_template`, `search_nodes`, `get_node`, `list_nodes`, `search_models`, and `validate_workflow`. It is in private testing and cannot be assumed available.

During implementation, discover the live tool schemas. Select it only when all required operations pass. Do not copy these tool names into code without discovery because the private-test surface may change.

### Project-owned adapter

The default plan is the narrow MCP adapter in `mcp/project_owned_mcp_contract.json`. Its tool names are explicitly project-owned. They are not claims about an existing server.

## Underlying verified ComfyUI operations

Map the adapter to current server routes after live discovery:

| Need | ComfyUI route or source |
| --- | --- |
| health and system stats | `/system_stats` and process health |
| feature inventory | `/features` |
| node inventory | `/object_info` and `/object_info/{node_class}` |
| model inventory | `/models` and `/models/{folder}` |
| upload image | `/upload/image` |
| upload mask | `/upload/mask` |
| validate and queue | `POST /prompt` |
| queue state and changes | `/queue` |
| history | `/history` and `/history/{prompt_id}` |
| cancel active work | `/interrupt` |
| free models | `/free` |
| progress | `/ws` messages including status, execution_start, executing, progress, and executed |
| output retrieval | `/view` and controlled file descriptors |

The adapter must test the live response schemas and version them. A changed route or message schema blocks production until the adapter test suite is updated.

## Project tool behavior

### `portrait_health`

Returns adapter version, ComfyUI version, frontend version, profile, process status, queue depth, GPU or MPS status, and dependency lock id.

### `portrait_capabilities`

Returns detected hardware, supported model loaders, MPS or CUDA flags, available ComfyUI routes, available workflow profiles, first-party MCP presence, and unresolved limitations.

### `portrait_inventory`

Returns:

- installed custom-node packages and commits
- node classes and schema hashes
- model filenames, folders, sizes, and checksums
- missing dependencies
- mismatched dependencies
- background registry status
- threshold registry status

### `portrait_validate_workflow`

Input is a registered workflow id or project-relative workflow file. It validates JSON, node classes, model references, locked controls, agent-autoprompter absence, evidence outputs, and profile policy.

### `portrait_import_workflow`

Registers only a checksummed workflow that already passed validation. It cannot import arbitrary remote URLs.

### `portrait_upload_source`

Writes source bytes to one job upload area, validates size and MIME, computes SHA-256, and returns an upload descriptor. It never decodes into the final evidence path until job validation.

### `portrait_submit_job`

Validates `portrait_job_input.schema.json`, idempotency, paths, source checksum, background, models, thresholds, and workflow. It returns a structured job record and queues the controller.

### `portrait_job_status` and `portrait_watch_job`

Return shared pipeline stage, percent when meaningful, ComfyUI prompt id, warnings, blockers, active attempt, and terminal result. Progress does not reveal source image bytes.

### `portrait_cancel_job`

Cancels queue or active execution, preserves evidence, and records caller identity and time.

### `portrait_fetch_outputs`

Returns only files listed in the terminal output manifest and authorized for the caller. It includes path, MIME, size, and SHA-256. It never exposes arbitrary filesystem paths.

### `portrait_history`

Returns bounded metadata. Source and face data are omitted unless explicitly requested and authorized.

### `portrait_free_memory`

Calls the verified ComfyUI free route, terminates optional sidecars, triggers safe local cleanup, and returns before and after memory measurements.

## Error contract

Every tool error returns:

```json
{
  "ok": false,
  "error": {
    "code": "MACHINE_READABLE_CODE",
    "message": "Actionable explanation",
    "retryable": false,
    "stage": "RESOLVING_DEPENDENCIES",
    "details": {}
  }
}
```

Do not return raw stack traces to remote callers. Write full traces to a protected job log with redaction.

## Security

- Local MCP uses stdio and an allowlisted project root.
- Remote MCP or gateway uses authenticated transport.
- Tool inputs do not accept shell, URL download, arbitrary ComfyUI JSON, or absolute output paths outside configured roots.
- Job ids cannot contain traversal sequences.
- Rate limit uploads, submits, status polling, and output downloads.
- Store audit identity and caller identity separately.

## MCP acceptance

Test every tool for success, schema failure, missing dependency, missing source, cancellation, duplicate job, unauthorized access, path traversal, oversized upload, malformed image, ComfyUI crash, and output retrieval after restart.
