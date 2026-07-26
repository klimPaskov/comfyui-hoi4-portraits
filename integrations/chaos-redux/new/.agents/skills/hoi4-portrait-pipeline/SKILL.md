---
name: hoi4-portrait-pipeline
description: Use when producing, auditing, converting, or handing off a real-person Hearts of Iron IV country-leader, commander, or operative portrait through the standalone ComfyUI Krea 2 pipeline.
---

# HOI4 Portrait Pipeline

Use this skill for identity-preserving production of real-person HOI4 portraits after the source photograph and exact crop have been approved.

Use it together with:

- `AGENTS.md` for repository-wide rules
- `chaos-redux-event-assets` for source classification, provenance, reference families, runtime paths, manifests, and requirement-to-runtime coverage
- `chaos-redux-subagents` for producer and auditor routing
- `chaosx_asset_source_researcher` for attributed source research and exact crop evidence
- `chaosx_hoi4_portrait_pipeline` for production jobs
- `chaosx_portrait_identity_auditor` for independent read-only review

The standalone implementation project normally lives at:

`/Users/klimpaskov/Documents/Projects/comfyui-hoi4-portraits`

Do not assume the Chaos Redux session can access that Mac path. Run the topology preflight before direct integration. Use portable job handoffs when the portrait project and live mod repository are on different machines.

## Ownership boundary

The sourced asset researcher owns:

- real-person identity and role research
- source attribution, rights notes, source date, and archive notes
- immutable source bytes and checksum
- subject-ownership search in vanilla and Chaos Redux
- exact head-and-shoulders crop and decoded-pixel equality evidence
- source handoff manifest

The portrait producer owns:

- job validation
- deterministic source preparation after approved crop intake
- conditional black-and-white detection and colorization
- conservative restoration and upscale
- person, face, hair, hat, accessory, and background masks where useful
- approved background resolution and composite evidence
- Krea 2 identity-edit candidate production
- `hoi4_portrait_new_style_lora.safetensors` style application
- candidate evidence, prompts, seeds, model versions, node versions, and comparisons
- final 156x210 PNG and DDS only after a valid independent PASS exists

The identity auditor owns:

- independent likeness, style, mask, and provenance review
- hard-gate verdicts for every candidate
- PASS, FAIL, or UNCERTAIN output through the audit schema

The parent implementation agent owns:

- final candidate acceptance after reviewing the independent audit
- copying the accepted DDS into the mod
- `.gfx`, character, history, event, focus, decision, and other runtime wiring
- live consumer validation
- in-game evidence
- the final completion claim

The producer must never approve its own likeness. The auditor must never generate, edit, rank, or select images.

## Hard gates

Stop with `blocked` or the corresponding pipeline exit code when any required gate fails.

1. Source master exists and its SHA-256 matches the source handoff.
2. Source attribution or user authorization is present.
3. The exact crop and crop evidence exist and match the approved master.
4. The selected subject is unambiguous.
5. The prompt begins exactly with `hoi4_portrait,` and does not contain the person's name.
6. The approved background registry entry resolves to the expected checksum.
7. The style LoRA exists at the locked path and its checksum matches the dependency lock.
8. The chosen workflow loads with no missing-node placeholder.
9. The model and custom-node inventory matches the dependency lock.
10. Calibrated identity and style threshold files exist.
11. A separate auditor identity and process are available.
12. The final DDS converter and validation route are verified against current project and vanilla precedent.

Do not silently substitute another base model, another style LoRA, a generated face, a face-swap route, a random background, a manual Photoshop export, or an unverified converter.

## Four execution profiles

The standalone project provides these workflow IDs:

- `human_local_mac_16gb`
- `human_full_power_gpu`
- `agent_local_mac_16gb`
- `agent_remote_runpod`

Human profiles contain the approved automatic portrait describer. Agent profiles contain no describer and receive the prompt from the parent agent.

Chaos Redux automation normally uses:

- `agent_local_mac_16gb` after a verified local capability pass
- `agent_remote_runpod` for the full-power authenticated remote route

Do not redefine a remote generation job as local generation. If Krea 2 generation is not practical on the detected 16 GB Mac, keep local preprocessing, validation, prompting, and remote submission useful while reporting local generation as infeasible.

## Required parent prompt

Every project subagent must be spawned with `fork_context=false`.

A production prompt must include:

- event or system owner when known
- subject record name for provenance only
- identity classification
- real-person status
- intended role: `country_leader`, `commander`, or `operative`
- immutable source-master path and SHA-256
- exact crop path and SHA-256
- crop-evidence JSON path and SHA-256
- source provenance manifest path
- source-ownership search disposition
- approved background registry id, path, and SHA-256
- prompt beginning with `hoi4_portrait,` and excluding the person's name
- execution profile
- candidate count and retry limit
- identity-threshold and style-threshold ids
- seed policy
- exact standalone project root or authenticated remote route
- exact job id
- exact output stem
- exact final PNG and DDS paths
- exact production handoff path
- forbidden additions, removals, and simplifications
- optional mod root, country tag, character id, sprite name, and gameplay path as parent-owned metadata only

An audit prompt must include:

- job id
- source master
- approved crop or processed source reference
- candidate files in randomized order
- native-size comparison sheet
- enlarged comparison sheet at no less than 4x
- mask-boundary comparison
- manifest path
- calibrated threshold id
- auditor output path
- proof that the auditor is separate from the producer

Do not pass producer preference, candidate ranking, or a claimed winner to the auditor.

## Stable job contract

The normative input schema is owned by the standalone project:

`schemas/portrait_job_input.schema.json`

The normative output schema is:

`schemas/portrait_job_output.schema.json`

The independent audit schema is:

`schemas/portrait_audit.schema.json`

Every job uses:

```text
jobs/<job_id>/
  source/
  provenance/
  intermediates/
  masks/
  prompts/
  candidates/
  comparisons/
  final/
  audit/
  logs/
```

Do not place private source photographs, rejected candidates, face embeddings, model weights, or private backgrounds in the Chaos Redux Git repository.

## Source intake

Treat the source master and exact crop as immutable evidence.

The pipeline may create new decoded, orientation-corrected, colorized, restored, upscaled, masked, or composited derivatives. It must never overwrite the source master or exact crop.

The controller records:

- source checksum
- EXIF orientation handling
- decoded-master checksum
- selected person and face
- crop coordinates and crop evidence
- black-and-white classification
- colorization decision
- restoration and upscale settings
- all masks
- approved background checksum
- every derived artifact checksum

Colorization is conditional. A colorized derivative is not identity evidence and cannot establish uniform, medal, ribbon, insignia, jewelry, or decoration colors that the source does not support.

## Identity-preserving generation

Use Krea 2 Turbo only after live compatibility verification with the style LoRA trained against Krea 2 RAW.

The style LoRA is an immutable input:

`/Users/klimpaskov/Documents/Projects/comfyui-hoi4-portraits/loras/hoi4_portrait_new_style_lora.safetensors`

Record its checksum before the first production run. Never overwrite, rename, merge, or resave it in place.

The implementation experiment must compare:

1. Krea 2 identity edit without the HOI4 style LoRA.
2. Identity edit with the style LoRA at several bounded strengths.
3. Both adapter or LoRA orders when the verified graph permits them.
4. One-pass identity and style conversion.
5. Two-pass identity edit followed by a low-denoise style pass.
6. Masked face or subject routes when supported.
7. Reference strength, edit strength, sampler, step, and denoise ranges.
8. Local memory-reduced and full-power settings.

Select the architecture by calibrated likeness, style, mask, reproducibility, and resource results. Do not select the most artistic image when likeness is weaker.

Face swapping and subject replacement are forbidden. Reject prompts or graphs that request replacing a face, head, eyes, person, or identity.

## Candidate rejection rules

Reject a candidate when it has any of these defects:

- changed facial geometry
- changed eye shape or spacing
- changed nose or mouth shape
- changed jawline or chin
- lost facial asymmetry
- beautification or genericization
- age drift
- gender-presentation drift
- changed hairline
- invented or removed facial hair
- unjustified expression change
- major head-direction drift
- added or removed glasses
- invented or removed hats or accessories
- invented medals, jewelry, insignia, decorations, or hidden details
- genericized clothing
- lost scars or visible identity markers
- foreground or background leakage
- damaged hair, hat, or accessory boundaries
- photographic filtering without a genuine HOI4 painted conversion
- unresolved provenance

Identity is non-compensable. Strong style cannot turn an identity FAIL or UNCERTAIN verdict into PASS.

## Independent audit

The producer writes candidate evidence and stops before finalization when no independent audit exists.

The auditor reviews:

- face-embedding evidence where legally and technically appropriate
- face landmarks
- eye, nose, mouth, jaw, and facial proportions
- visible asymmetry
- head direction and expression
- hairline and facial hair
- accessories and visible markers
- native 156x210 appearance
- at least 4x enlarged nearest-neighbour comparison
- foreground and mask boundaries
- HOI4 style against the correct role reference family
- provenance and artifact lineage

A candidate passes only when every mandatory hard gate is PASS. Any UNCERTAIN hard gate makes the candidate ineligible for autonomous finalization.

The auditor must return the exact audit schema. Free-form approval is not enough.

## Bounded retry

The controller may retry with safer settings only within the job's limit.

A retry may:

- lower edit strength
- lower style LoRA strength
- strengthen the approved reference path
- move to the measured safer adapter order
- use a more precise approved mask
- reduce the transformation surface
- switch from one-pass to two-pass or the reverse when the experiment approved both
- move from the local profile to the remote profile only when the parent requested or allowed that fallback

Every retry records the previous failure, changed parameters, new seed policy, and result.

Do not keep retrying until one score barely clears a threshold.

## MCP and API route

Keep ComfyUI MCP guidance inside this skill. Do not create a central MCP skill.

First discover the live MCP surface. Use an existing first-party or mature route only when its actual tool names and schemas cover health, inventory, workflow validation, upload, queueing, progress, history, output retrieval, cancellation, and structured errors.

The planned project-owned adapter exposes these project-owned tools after implementation:

- `portrait_health`
- `portrait_capabilities`
- `portrait_inventory`
- `portrait_validate_workflow`
- `portrait_import_workflow`
- `portrait_upload_source`
- `portrait_submit_job`
- `portrait_job_status`
- `portrait_watch_job`
- `portrait_cancel_job`
- `portrait_fetch_outputs`
- `portrait_history`
- `portrait_free_memory`

These names are not claims about an existing third-party MCP server. The implementation must use only tool names discovered from the installed route.

The project-owned adapter may wrap the verified ComfyUI HTTP and WebSocket API. It must not accept arbitrary workflow JSON, arbitrary filesystem paths, source-download URLs, shell commands, or unauthenticated remote calls.

## Two-machine integration

### Direct mode

Use direct mode only after proving that one implementation session has read and write access to both the standalone portrait project and the live Chaos Redux repository.

Record:

- machine names
- absolute roots
- transport
- permissions
- credential boundary
- line-ending policy
- rollback method

Read current live files before editing. Do not overwrite newer live files with a planning snapshot.

### Portable mode

When the Mac and Windows repository are separate, use a portable handoff containing:

- normalized input JSON
- source and crop descriptors and checksums
- provenance manifest
- prompt
- workflow and dependency-lock ids
- candidate and retry limits
- output schema
- returned final PNG and DDS descriptors
- independent audit
- comparison sheet
- production manifest
- final checksums

Verify every returned checksum before copying an artifact into Chaos Redux.

## DDS gate

The final portrait is exactly 156x210.

Use the current verified Chaos Redux converter when direct access exists. Otherwise use the standalone deterministic converter whose output has been calibrated against current project and vanilla portrait precedents.

Validate:

- dimensions
- legacy DDS header
- pixel format and channel masks
- alpha behavior
- mipmap policy
- expected file size for the selected uncompressed format
- successful decode
- pixel comparison with the final PNG
- final path
- SHA-256

Reject black output, channel swapping, unexpected transparency, corrupt headers, and unverified compression.

## Runtime handoff

A successful production handoff includes:

- job id and execution profile
- source, crop, and provenance checksums
- prompt and seeds
- workflow and dependency-lock versions
- model and node versions
- candidate paths and checksums
- selected candidate
- independent audit path and verdicts
- comparison-sheet path
- final PNG and DDS paths and checksums
- manifest path
- warnings and blockers
- timing and peak memory when available
- proposed sprite name and final gameplay path

The parent must still verify character ownership, create or update the character and GFX references, copy the DDS, identify a live in-game consumer, and record in-game evidence.

## Completion standard

A real-person portrait package is complete only when:

- the source and exact crop are immutable and attributed
- the prompt and generation route are recorded
- at least one candidate has an independent all-PASS audit
- the final PNG is exactly 156x210
- the DDS passes byte-level and pixel-level validation
- every artifact is connected by checksums and lineage
- the parent wires the accepted DDS to a live consumer
- in-game validation succeeds

A successful ComfyUI queue, attractive candidate, audit score, PNG, or DDS alone is not completion.
