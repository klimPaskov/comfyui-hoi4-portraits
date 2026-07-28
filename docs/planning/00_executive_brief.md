# Executive Brief

## Goal

Build a reproducible standalone project at `/Users/klimpaskov/Documents/Projects/comfyui-hoi4-portraits` that can accept a usable photograph of one real person and produce a recognizable 156 by 210 HOI4 portrait plus a validated DDS and complete audit package.

## Operational identity standard

The system cannot promise mathematically absolute identity preservation. It can enforce an operational standard:

- Identity is a hard pass or fail gate.
- A high style score cannot compensate for likeness failure.
- No single embedding score can approve a portrait.
- Every metric threshold comes from a locked calibration set and versioned threshold file.
- Any missing, failed, or uncertain mandatory signal fails closed.
- The producer cannot approve the final likeness.
- Failed jobs do not create a final DDS, copy files into a mod, or report completion.

## Recommended system shape

The production system has five layers:

1. A project controller validates jobs, creates evidence folders, calls ComfyUI, records versions, and enforces the state machine.
2. A project-owned ComfyUI custom-node pack performs deterministic image intake, subject selection, crop calculation, monochrome classification, mask validation, compositing, prompt validation, and evidence export.
3. ComfyUI Core plus pinned model and custom-node dependencies perform colorization, conservative restoration, matting, Krea 2 editing, style conversion, and image decoding.
4. A separate audit process evaluates identity, facial geometry, pose, expression, hair, accessories, masks, style, and provenance without seeing the producer's preferred candidate.
5. A deterministic converter writes and validates the HOI4 DDS only after audit PASS.

## Krea 2 decision

Krea 2 Turbo is the required production base, subject to live compatibility testing. The user's style LoRA was trained on Krea 2 RAW. Current official ComfyUI documentation states that RAW-trained LoRAs apply to Turbo. Identity editing requires a separate edit adapter and two custom nodes. The style LoRA alone is not an image editor and is not an identity mechanism.

Implementation must benchmark these routes:

- identity edit only
- identity edit plus style LoRA at several strengths
- both supported adapter application orders
- one-pass edit and style conversion
- two-pass identity edit followed by a low-denoise style pass
- subject-mask and face-mask routes when supported by the live graph
- local memory-reduced and full-power model variants

The selected route is the best route that passes identity first, then mask and provenance, then style and runtime criteria.

## Four workflows

The graph family produces four standalone JSON files:

| Workflow | Autoprompter | Target | Default candidates | Working canvas |
| --- | --- | --- | ---: | --- |
| `human_local_mac_16gb` | yes | 16 GB Apple Silicon Mac | 2 | 832 by 1120 |
| `human_full_power_gpu` | yes | 48 GB or 80 GB NVIDIA | 6 | 1196 by 1610 |
| `agent_local_mac_16gb` | no | same 16 GB Mac | 2 | 832 by 1120 |
| `agent_remote_runpod` | no | authenticated RunPod | 6 | 1196 by 1610 |

The canvases use the final 26:35 portrait ratio and stay below the identity-edit model's documented 2 megapixel ceiling.

## Local Mac position

The local plan is a real local-generation attempt. It is not a disguised remote workflow. The implementation must measure the machine and test Krea 2 on MPS with only verified formats and loaders. The file-size budget shows that fully resident FP8 weights exceed 16 GB before activations, so staged loading or offload is mandatory. Full local generation may still prove infeasible. In that case:

- report the objective failure and evidence
- keep local intake, crop, masking, autoprompt, audit, DDS validation, and remote job submission useful
- do not mark the local generation acceptance test as passed
- use the remote workflow as the documented fallback

## Remote position

Use a pinned RunPod Pod template or container with persistent `/workspace` storage. Run ComfyUI on loopback. Expose only an authenticated project gateway. Submit jobs asynchronously because RunPod documents a 100-second HTTP proxy timeout. A 48 GB GPU is the cost-qualified default class. An 80 GB GPU is the reference full-power class. A 24 GB GPU is an experimental reduced profile, not the full-power definition.

## Independent review

The independent auditor receives source evidence, processed reference, masks, candidates, and provenance. It does not receive the producer's ranking or selected candidate. It returns per-candidate PASS, FAIL, or UNCERTAIN verdicts. The controller can select only among candidates with PASS across all hard gates.

## Final deliverables from implementation

- the four loadable workflow JSON files
- a clean standalone Git project
- model and custom-node locks with checksums
- local and RunPod bootstrap automation
- local and remote MCP invocation
- deterministic source evidence and job manifests
- calibrated audit thresholds
- final PNG and validated DDS
- a Chaos Redux portable integration package
- a generic agentic HOI4 integration package
- benchmark, acceptance, licensing, and capability reports
