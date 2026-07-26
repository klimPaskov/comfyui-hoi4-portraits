# Four Workflow Specifications

## Shared graph contract

All four workflows implement the same production stages and output the same named artifacts. They are generated from one graph specification and differ through profile overlays. Each graph uses the group labels in `workflows/workflow_delivery_contract.md`.

The graph ends with candidate and evidence outputs. Independent audit, final selection, final PNG, and DDS remain controller operations so the producer graph cannot self-approve.

## Shared useful controls

Human graphs expose:

- source image
- subject face index after inventory
- optional source bounding box
- optional crop override with recorded coordinates
- monochrome mode: automatic, force skip, force run with review flag
- restoration level: none, conservative, qualified enhanced
- approved background registry id
- prompt preview and manual replacement
- seed mode and fixed seed field
- candidate count within profile maximum
- output job id

They do not expose dependency paths, audit bypass, final DDS bypass, identity thresholds, or arbitrary file-system paths.

Agent graphs receive all values from job JSON and expose no manual production controls.

## 1. `human_local_mac_16gb`

### Purpose

Interactive local graph for a 16 GB Apple Silicon Mac. It includes the local autoprompter and clean previews. It attempts real local Krea 2 generation only after the local capability suite passes.

### Profile defaults

- Working and generation canvas: 832 by 1120, 0.932 megapixels
- Candidate count: 2
- Retry limit controlled outside graph: 2
- Krea edit: 8 to 10 steps during normal use, 12 only when the measured memory and runtime budget permits
- CFG: 1.0
- Sampler baseline: Euler
- Scheduler baseline: simple
- Denoise: full for one-pass route, qualified low-denoise value for second pass
- Identity adapter: r64 or r128 only after non-inferiority testing, otherwise full adapter with offload
- Autoprompter: Qwen3-VL 4B Instruct official GGUF Q4_K_M plus matching vision `mmproj`, run in a staged sidecar

### Model order

1. Run deterministic preprocessing.
2. Load autoprompter sidecar, create and validate the prompt, then terminate it and verify memory release.
3. Load matting or colorization models only when needed, save outputs, unload them, and verify memory release.
4. Load Krea 2 model stack and generate candidates.
5. Unload the Krea stack before enlarged comparisons and local audit.

### Visual organization

Use left-to-right groups with one preview at source, crop, color/restoration, mask, composite, prompt, and candidate output. Notes explain only non-obvious controls. The graph opens with all optional expensive branches bypassed until automatic gates enable them.

### Failure behavior

If Krea 2 cannot execute locally after the documented recovery ladder, show and save `LOCAL_GENERATION_UNAVAILABLE`. Do not queue a remote job from inside the graph and call it local. The desktop application or controller may separately offer remote submission.

## 2. `human_full_power_gpu`

### Purpose

Interactive full-quality graph on a rented high-memory NVIDIA GPU. It preserves the local graph's organization and controls.

### Profile defaults

- Working and generation canvas: 1196 by 1610, 1.926 megapixels
- Candidate count: 6
- Krea edit: 10 steps default, 8 to 12 exposed
- CFG: 1.0
- Sampler and scheduler baseline: Euler and simple
- Identity adapter: full v1.2 by default after qualification
- Autoprompter: Qwen3-VL 8B Instruct full or officially supported reduced precision
- Optional autoprompter benchmark: 32B in a staged service on 80 GB or larger hardware
- Full-resolution mask refinement and stronger comparison sheets
- No extra creative freedom that lowers the identity gate

### Quality additions

- More candidates, not unbounded candidates
- full identity adapter
- higher `grounding_px` qualification
- full-power style and identity experiment route
- optional SAM 2 or another approved mask refiner only when it improves thin boundaries
- expanded audit views at native, 4x, and 8x

### Parity rule

Any behavior fix made to the local graph must appear here through the shared graph specification. This graph cannot become a separate creative workflow.

## 3. `agent_local_mac_16gb`

### Purpose

Non-interactive local agent graph. It has no autoprompter node, no VLM sidecar call, and no fallback that writes a prompt.

### Inputs

- validated source upload path
- selected subject parameters
- validated prompt
- approved background registry id and checksum
- workflow settings resolved from the local profile
- job id and evidence root

### Outputs

- processed source and crop metadata
- monochrome and colorization report
- masks and mask audit
- approved composite
- candidate images
- candidate generation metadata
- graph execution log

### Contract

The controller exports API-format workflow input values and queues the graph through MCP. The graph never waits for human selection. Ambiguity exits before generation.

### Profile defaults

Match `human_local_mac_16gb` except autoprompt is absent and candidate paths are returned only through structured outputs.

## 4. `agent_remote_runpod`

### Purpose

Non-interactive full-power agent graph running inside the pinned RunPod deployment.

### Inputs and outputs

Use the same agent contract as local. Source upload, prompt, status, cancellation, and output download happen through the authenticated project gateway or MCP adapter. Raw ComfyUI is inaccessible from the public network.

### Profile defaults

Match `human_full_power_gpu` except autoprompt is absent. Candidate count and retry limit come from the validated job and remain within the profile maximum.

### Remote requirements

- source upload checksum verification
- idempotency key equal to job id plus input hash
- asynchronous job creation
- structured progress by shared stage name
- cancellation that calls ComfyUI interrupt and records partial outputs
- authorized output download with checksum
- persistent model cache under `/workspace`
- cleanup policy for source and generated data
- cost and idle-shutdown controls

## Workflow graph validation

Each workflow must pass:

1. JSON syntax validation.
2. UI import into the pinned ComfyUI frontend.
3. API-format conversion.
4. missing-node check against `/object_info`.
5. missing-model check against model inventory routes.
6. graph-policy check proving the agent graphs have no autoprompter classes.
7. graph-policy check proving all mandatory evidence outputs are connected.
8. one fixture run for the target profile.
9. checksum registration in the workflow manifest.

A workflow with a red placeholder node, disconnected mandatory output, unknown widget, or manual repair requirement is not delivered.
