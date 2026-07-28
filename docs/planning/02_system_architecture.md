# System Architecture

## Architecture overview

The system uses a controller around ComfyUI rather than placing every responsibility inside one graph. This keeps source evidence, retries, audit independence, DDS conversion, remote authentication, and mod integration testable outside a visual graph.

```text
Caller or human
    |
    v
Portrait controller and MCP adapter
    |-- validate job JSON and topology
    |-- create immutable evidence root
    |-- resolve background, models, workflow, thresholds
    |-- upload source to ComfyUI
    |-- queue one bounded graph execution per candidate batch
    |-- collect intermediates and candidates
    |-- invoke separate auditor
    |-- select only from audited PASS candidates
    |-- run deterministic final PNG and DDS pipeline
    `-- return structured result

ComfyUI
    |-- deterministic project nodes
    |-- approved preprocessing models
    |-- Krea 2 Turbo and Qwen encoder
    |-- identity edit adapter
    |-- HOI4 style LoRA
    `-- image and mask outputs

Independent auditor
    |-- calibrated face embedding
    |-- calibrated landmark and pose checks
    |-- attribute and mask checks
    |-- HOI4 reference style check
    `-- signed PASS, FAIL, or UNCERTAIN record
```

## Repository layout

```text
/Users/klimpaskov/Documents/Projects/comfyui-hoi4-portraits/
  README.md
  AGENTS.md
  .gitignore
  pyproject.toml
  uv.lock or equivalent resolved Python lock
  config/
    profiles/
    identity_thresholds/
    style_thresholds/
    background_registry.json
    exit_codes.json
  dependencies/
    dependencies.lock.json
    models.lock.json
    custom_nodes.lock.json
    licenses/
  docs/
    architecture/
    benchmarks/
    capability_reports/
    audits/
    runbooks/
  integrations/
    chaos-redux/
    agentic-hoi4-modding/
  jobs/
    .gitkeep
  loras/
    hoi4_portrait_new_style_lora.safetensors
    hoi4_portrait_new_style_lora.safetensors.sha256
  models/
    manifests/
    cache/
  backgrounds/
    redistributable/
    private/
  repos/
    comfyui/
    custom_nodes/
    agentic-hoi4-modding/
  scripts/
    bootstrap/
    run/
    validate/
    convert/
    benchmark/
    integration/
  src/
    portrait_pipeline/
      controller/
      graph_spec/
      mcp/
      audit/
      dds/
      manifests/
      provenance/
      integration/
    comfyui_hoi4_portrait_nodes/
  tests/
    fixtures/
    unit/
    integration/
    acceptance/
    security/
  workflows/
    human/local_mac_16gb/
    human/full_power_gpu/
    agent/local_mac_16gb/
    agent/remote_runpod/
```

`models/cache`, `backgrounds/private`, `jobs`, source portraits, generated portraits, model weights other than the user-owned immutable LoRA path, and provider credentials are Git ignored.

## Components and ownership

### Portrait controller

The controller owns:

- JSON schema validation
- path containment and job idempotency
- source checksum and immutable copies
- dependency and workflow validation
- queue and retry policy
- ComfyUI HTTP and WebSocket communication
- evidence and manifest writes
- independent auditor invocation
- candidate selection after audit
- deterministic final processing
- DDS conversion and validation
- optional integration handoff
- machine-readable output and exit code

It must never approve a candidate by itself.

### Project-owned ComfyUI nodes

Implement one package named `comfyui-hoi4-portrait-nodes`. It should provide narrow nodes with explicit, serializable outputs:

- `HOI4SourceDecodeAndHash`
- `HOI4SubjectInventory`
- `HOI4SelectSubject`
- `HOI4PortraitCrop`
- `HOI4MonochromeClassify`
- `HOI4ConditionalColorizationGate`
- `HOI4ConservativeRestorationGate`
- `HOI4MaskBundle`
- `HOI4MaskAudit`
- `HOI4BackgroundResolve`
- `HOI4ForegroundComposite`
- `HOI4PromptInput`
- `HOI4AutopromptClient`
- `HOI4PromptValidate`
- `HOI4EvidenceSave`

The exact class names may change only before the first workflow lock. Once locked, workflow and API contracts treat them as stable identifiers.

The nodes must not execute arbitrary shell commands, download unlisted URLs, read outside allowlisted roots, or write outside the job root.

### Model graph

The graph uses:

- Krea 2 Turbo model loader
- Krea 2 Qwen3-VL encoder loaded as `krea2`
- Qwen image VAE
- Krea 2 identity edit LoRA and its two custom nodes
- the immutable HOI4 style LoRA
- KSampler using the qualified recipe
- VAE decode
- optional approved colorization, matting, and upscale nodes

### Independent auditor

The auditor runs as a separate process or custom subagent. It receives candidate files after graph execution. It must have a different process id and audit identity from the producer. It cannot access the producer's candidate score, rank, selected candidate, or aesthetic preference.

### DDS converter

The standalone converter is a project library and CLI. It does not run as a manual Photoshop step. Chaos Redux integration may call the repository converter after verifying parity. All routes use the same validation oracle.

## Job state machine

```text
RECEIVED
  -> VALIDATING_INPUT
  -> PRESERVING_SOURCE
  -> RESOLVING_DEPENDENCIES
  -> PREPROCESSING
  -> PROMPTING or PROMPT_VALIDATION
  -> GENERATING
  -> COLLECTING_CANDIDATES
  -> INDEPENDENT_AUDIT
  -> SELECTING
  -> FINAL_PROCESSING
  -> DDS_VALIDATION
  -> SUCCEEDED
```

Any state can enter `FAILED`, `BLOCKED`, or `CANCELED`. `NEEDS_REVIEW` is terminal for autonomous execution and never continues to DDS or integration.

## Evidence root

Every job uses:

```text
jobs/<job_id>/
  input.json
  output.json
  source/
    original/
    decoded_master/
    selected_subject/
  provenance/
  intermediates/
    crop/
    monochrome/
    colorization/
    restoration/
    composite/
  masks/
    person/
    face/
    hair_hat_accessory/
    background/
    boundary/
  prompts/
  candidates/
    attempt_00/
    attempt_01/
  comparisons/
    native/
    enlarged_4x/
    masks/
    references/
  final/
  audit/
  logs/
  manifest.json
  history.jsonl
```

`history.jsonl` is append-only. The manifest records every file checksum and the operation that produced it.

## Reproducibility

A job is reproducible when it records:

- exact source bytes and decoded pixel hash
- crop coordinates and transform matrix
- all deterministic preprocessing parameters
- model repository, revision, filename, size, and checksum
- custom-node package commit and node class schema hash
- workflow UI and API JSON checksum
- prompt and validation result
- seed and candidate index
- sampler, scheduler, steps, CFG, denoise, reference strength, grounding resolution, adapter order, LoRA strengths, and mask route
- ComfyUI, PyTorch, Python, OS, driver, MPS or CUDA, and hardware versions
- final audit threshold ids and calibration dataset ids

A seed does not guarantee bit-identical output across different hardware or kernels. The manifest must distinguish `configuration_reproducible` from `bitwise_reproducible`.

## Graph reuse

The graph builder has one canonical stage definition and four profile overlays. A profile overlay can change:

- autoprompter presence
- model variant
- working resolution
- candidate count
- tiled processing
- audit preview count
- UI notes and exposed controls

It cannot remove a mandatory gate, rename an output contract, or change evidence semantics.
