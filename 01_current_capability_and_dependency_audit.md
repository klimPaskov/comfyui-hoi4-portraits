# Current Capability and Dependency Audit

**Research date:** 2026-07-26

This document separates verified current capabilities from implementation hypotheses. Every current fact below came from official documentation, an official model repository, an original project repository, or a primary model card. The implementation agent must re-open each source because Krea 2 and its identity-edit node stack are recent and changing quickly.

## Capability verdicts

| Surface | Verified current fact | Planning decision | Live gate |
| --- | --- | --- | --- |
| Krea 2 Turbo | ComfyUI documents Krea 2 RAW at 52 steps and Turbo at 8 steps. RAW-trained LoRAs apply to Turbo. Krea 2 supports 1K to 2K output. | Use Turbo for all production generation after compatibility tests. | Confirm the user's LoRA loads against the pinned Turbo model and produces the trigger behavior. |
| Official ComfyUI model files | The current Comfy-Org repository exposes `krea2_turbo_fp8_scaled.safetensors`, `qwen3vl_4b_fp8_scaled.safetensors`, and `qwen_image_vae.safetensors`. | Treat these as the reference full-quality ComfyUI stack. | Resolve exact revisions and SHA-256 before download. |
| Krea 2 model sizes | Observed repository sizes are about 13.1 GB for Turbo FP8, 5.24 GB for the FP8 Qwen encoder, and 254 MB for the VAE. Other observed Turbo variants include BF16 at 26.3 GB, INT8 convrot at about 13.5 GB, MXFP8 at about 13.5 GB, and NVFP4 at about 7.67 GB. | Do not infer platform support from file existence. Each loader, dtype, and device combination needs an execution test. | Verify each candidate format on MPS or CUDA and reject unsupported variants. |
| Krea 2 identity editing | The community `comfyui-krea2edit` project provides `Krea2EditModelPatch` and `Krea2EditGroundedEncode`. Both are required. The edit LoRA is separate from the style LoRA. | Use it as the first implementation candidate, pinned to a tested release or commit. | Run node import, schema, visual, regression, memory, and license tests. |
| Identity edit version | Node package version 1.2.3 was current during research. The model card recommends `krea2_identity_edit_v1_2.safetensors`. | Qualify v1.2 first. | Pin exact node commit and model revision. Do not follow moving `main` in production. |
| Identity edit inputs | `Krea2EditModelPatch` receives a Krea 2 model with the edit LoRA already applied, a VAE-encoded source, optional second source, and recommended raw image plus VAE for `fit`. `Krea2EditGroundedEncode` receives Krea 2 CLIP loaded as `type: krea2`, prompt, image, optional second image, and `grounding_px`. | Match this wiring exactly before adding the style LoRA. | Export actual node object schemas from the pinned ComfyUI instance and lock them. |
| Identity edit settings | The primary model card recommends Turbo at 8 to 12 steps, CFG 1.0, edit LoRA strength 1.0, `fit`, and roughly `ref_boost` 4 as a strong-likeness starting point. It documents a maximum near 2 megapixels. The example workflow uses 10 steps, Euler, simple scheduler, CFG 1, and full denoise. | Use the documented example as experiment baseline. Vary only named dials in the qualification matrix. | Do not declare final defaults before benchmark and audit. |
| Identity limitation | The model card explicitly reports regression toward typical proportions for distinctive facial geometry. | Treat geometry metrics and human-style independent review as mandatory. | Any geometry regression beyond calibrated thresholds fails. |
| Low-memory edit adapter | The model card provides rank-reduced v1.2 variants at about 0.91 GB and 0.46 GB. | Test r64 and r128 locally against full v1.2. | Select a reduced adapter only if identity and style acceptance are statistically non-inferior within the defined margin. |
| ComfyUI Local MCP | The first-party local MCP is in private testing and unavailable without access. Its documented core loop works through `comfy-cli`, but tool behavior may change. | Do not make private access a project dependency. | Use first-party Local MCP only after access, exact tool discovery, and parity tests. |
| ComfyUI Cloud MCP | The public MCP route targets Comfy Cloud. | It does not satisfy local Mac or RunPod ownership requirements by itself. | Optional only when the user chooses Comfy Cloud. |
| ComfyUI server API | Official docs expose REST routes for prompt queueing, upload, inventory, history, queue, interrupt, free, and system stats, plus WebSocket progress events. | Build a narrow project-owned MCP adapter around these verified routes. | Generate route and message tests against the pinned server. |
| macOS support | Comfy Desktop supports macOS 13 or later on Apple Silicon M1 or later. ComfyUI also supports manual local installation. PyTorch uses the MPS backend for GPU acceleration on Apple Silicon. | Prefer a reproducible `comfy-cli` or manual workspace for automation. Desktop may be an optional human launcher. | Inspect the real Mac before selecting install mode. |
| ComfyUI Manager | Current docs say Manager is built into current releases for most setups and can be enabled with `--enable-manager`. The registry offers versioned custom nodes and security scanning. | Enable Manager for inventory and human maintenance. Pin non-registry nodes directly by commit during bootstrap. | Record Manager version and configuration. Do not lower security to install arbitrary URLs. |
| Local autoprompter | Qwen publishes official Qwen3-VL 4B Instruct GGUF weights with FP16, Q8_0, and Q4_K_M plus vision `mmproj`. | Use the official 4B Q4_K_M route through a pinned llama.cpp sidecar for the local human graph. | Verify image input, exact instruction following, latency, memory, and prompt validation. |
| Full-power autoprompter | Qwen publishes 8B and larger vision-language models and official GGUF variants. | Qualify the 8B full precision or official quantized model as the default. Test 32B as a benchmark candidate. | Use the smallest model that passes the hallucination and format suite. |
| Matting | BiRefNet has an official repository and current ComfyUI support. | Use BiRefNet as the first foreground matte candidate. | Verify license, exact weights, native node class, mask quality, and Mac memory. |
| Colorization | DDColor has an official project and paper. | Use it only after monochrome classification and only as a conditioning derivative. | Reject unsupported color detail and retain the monochrome identity master. |
| Upscaling | Real-ESRGAN has an official repository. | Keep it optional and conservative. Deterministic Lanczos is the baseline. | Reject any mode that changes facial geometry or identity markers. |
| Face analysis | OpenCV Zoo publishes YuNet face detection and SFace recognition. MediaPipe publishes face detection and face landmark tasks. | Use YuNet plus SFace for one calibrated embedding layer and MediaPipe for landmarks, pose, expression, and crop geometry. | Pin exact models and licenses, calibrate thresholds, and record demographic performance limitations. |
| RunPod storage and secrets | RunPod documents `/workspace` as the persistent mount default, account secrets, secret references in environment variables, and custom Pod templates. | Put models, locks, caches, and durable job evidence under `/workspace`. | Verify volume attachment and no secret leakage. |
| RunPod exposure | RunPod states that exposed HTTP or TCP services become public, require authentication, and the HTTP proxy has a 100-second timeout. | Run raw ComfyUI on loopback. Expose an authenticated asynchronous gateway only. | Penetration-test auth, input limits, cancellation, and output authorization. |
| RunPod GPU classes | Current GPU inventory includes 24 GB, 32 GB, 48 GB, 80 GB, 94 GB, 141 GB, and larger classes. | Use 48 GB as cost-qualified full power and 80 GB as reference full power. | Benchmark actual availability, price, peak VRAM, runtime, and quality before selecting a default. |

## Primary source locations

- ComfyUI Krea 2 tutorial: `https://docs.comfy.org/tutorials/image/krea/krea-2`
- ComfyUI Local MCP: `https://docs.comfy.org/agent-tools/local`
- ComfyUI Cloud MCP: `https://docs.comfy.org/agent-tools/mcp`
- ComfyUI server routes: `https://docs.comfy.org/development/comfyui-server/comms_routes`
- ComfyUI server overview: `https://docs.comfy.org/development/comfyui-server/comms_overview`
- ComfyUI macOS: `https://docs.comfy.org/installation/desktop/macos`
- ComfyUI custom nodes: `https://docs.comfy.org/installation/install_custom_node`
- ComfyUI Manager: `https://docs.comfy.org/manager/install`
- Krea 2 edit nodes: `https://github.com/lbouaraba/comfyui-krea2edit`
- Krea 2 identity model: `https://huggingface.co/conradlocke/krea2-identity-edit`
- Qwen 4B GGUF: `https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct-GGUF`
- Qwen 8B GGUF: `https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct-GGUF`
- RunPod GPU types: `https://docs.runpod.io/references/gpu-types`
- RunPod ports: `https://docs.runpod.io/pods/configuration/expose-ports`
- RunPod secrets: `https://docs.runpod.io/pods/templates/secrets`
- RunPod environment variables: `https://docs.runpod.io/pods/templates/environment-variables`

## Dependency selection rules

1. Use official ComfyUI Core nodes where they provide the required operation.
2. Use one narrow project-owned custom-node pack for deterministic project logic.
3. Use the Krea 2 edit node pack only for its two documented Krea edit nodes.
4. Do not install broad node packs to obtain one small utility.
5. Pin Git dependencies to commits and model repositories to immutable revisions.
6. Record every direct and transitive Python dependency in the lock.
7. Reject unverified mirrors, repacks, and filenames without provenance.
8. Treat GGUF, FP8, INT8, MXFP8, NVFP4, NF4, and CPU offload as separate capabilities. One supported format does not imply another.
9. Do not use a Krea 2 GGUF or NF4 model unless an official or primary source and a working pinned loader exist at implementation time.
10. Preserve the user's style LoRA unchanged. Never rewrite its metadata or save an optimized copy over the original path.

## Current blockers

### Style LoRA

The LoRA itself was not present in the planning environment. Implementation must record:

- SHA-256
- file size
- safetensors metadata
- tensor names and ranks
- base-model identifier if embedded
- trigger token behavior
- loading success on RAW and Turbo
- output comparison at strengths selected for the experiment matrix

A failed compatibility test blocks production. It does not authorize another base model.

### Approved portrait background

No exact background file or license record was available. This blocks a production job. The implementation must resolve the background through `config/background_registry.json` using this order:

1. An approved project-owned source with explicit redistribution permission.
2. A canonical Chaos Redux reference with source and rights records.
3. A local installed-game asset copied into a Git-ignored private directory when redistribution is not allowed.

The resolver must record the source file, owning GFX or catalog definition, dimensions, checksum, attribution, rights rule, and runtime copy. There is no generated fallback.

### Live target repositories

The Mac did not contain the live Chaos Redux repository and no generic agentic HOI4 repository URL was available. The integration files in this package are proposed against the uploaded project snapshots. The implementation agent must inspect each live repository before applying them.
