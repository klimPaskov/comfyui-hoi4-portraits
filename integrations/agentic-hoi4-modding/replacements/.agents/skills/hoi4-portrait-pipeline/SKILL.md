---
name: hoi4-portrait-pipeline
description: Use when producing, independently auditing, converting, or handing off a real-person Hearts of Iron IV country-leader, commander, or operative portrait through the standalone ComfyUI Krea 2 pipeline.
---

# HOI4 Portrait Pipeline

Use this skill for autonomous identity-preserving real-person portrait production after an attributed source master and exact source crop have been approved.

This skill is repository-neutral. Discover the repository's asset, provenance, character, GFX, and DDS conventions before integration. Update an existing equivalent portrait workflow instead of creating a duplicate.

The default standalone project location is:

`/Users/klimpaskov/Documents/Projects/comfyui-hoi4-portraits`

Treat that as a configuration default, not proof that the current session can access it.

## Ownership

A source-research step owns the real photograph, attribution, rights notes, immutable source checksum, exact crop, crop equality evidence, and subject-ownership search.

The portrait producer owns preprocessing, masks, approved background composition, Krea 2 identity editing, HOI4 LoRA styling, candidates, comparisons, production evidence, and final PNG/DDS only after independent PASS.

The portrait auditor is read-only and owns candidate-level identity, style, mask, and provenance verdicts. It cannot generate, edit, rank, or select candidates.

The parent repository agent owns final selection among independently eligible candidates, file placement, character and GFX wiring, live consumer validation, and completion claims.

## Fail-closed intake

Require:

- immutable source master and SHA-256
- source attribution or user authorization
- exact crop and SHA-256
- crop coordinates and decoded-pixel equality evidence
- unambiguous selected subject
- identity classification and real-person flag
- intended role
- prompt beginning exactly with `hoi4_portrait,`
- prompt without the person's name
- approved background registry id, path, checksum, provenance, and redistribution rule
- workflow profile
- candidate and retry limits
- calibrated identity and style threshold ids
- seed policy
- final PNG and DDS paths
- exact job and handoff paths

Stop when any requirement is missing, stale, contradictory, or unverified. Do not generate a substitute person, random background, or untracked crop.

## Workflow profiles

The standalone project delivers:

- `human_local_mac_16gb`
- `human_full_power_gpu`
- `agent_local_mac_16gb`
- `agent_remote_runpod`

Human workflows contain the approved autoprompter. Agent workflows contain no autoprompter and require a parent-supplied prompt.

A remote generation fallback must remain identified as remote. Do not report it as local execution.

## Stable job contract

Use the standalone schemas:

- `schemas/portrait_job_input.schema.json`
- `schemas/portrait_job_output.schema.json`
- `schemas/portrait_audit.schema.json`

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

The person's name may exist in provenance and integration metadata. It must not appear in the model prompt.

## Source evidence

Preserve the original source and exact crop as immutable inputs. Every decoded, orientation-corrected, colorized, restored, upscaled, masked, composited, generated, resized, or converted file is a new derivative with its own parent links and checksum.

Colorization runs only when the source is genuinely monochrome or nearly monochrome. It cannot establish unsupported uniform, medal, ribbon, insignia, jewelry, or decoration colors.

Restoration and upscale must preserve identity. Aggressive face restoration that replaces facial structure with a generic synthetic face is forbidden.

## Background replacement

Use only an approved registry asset. Record its exact source, local path, checksum, provenance, and redistribution rule.

Remove or replace the original background through segmentation, matting, or background-only processing. Preserve foreground alpha and masks. Protected foreground interior pixels must remain unchanged before the generative stage.

Do not silently generate a background substitute.

## Krea 2 route

The style LoRA is an immutable input at:

`/Users/klimpaskov/Documents/Projects/comfyui-hoi4-portraits/loras/hoi4_portrait_new_style_lora.safetensors`

Record its checksum. Never overwrite, merge, or resave it in place.

Use Krea 2 Turbo only after live compatibility verification. Treat the current identity-edit adapter or LoRA as a separate dependency. The HOI4 style LoRA alone does not provide identity retention or image editing.

Before selecting a production graph, compare:

1. identity edit without the style LoRA
2. identity edit with several bounded style strengths
3. both adapter or LoRA orders when supported
4. one-pass identity and style conversion
5. two-pass identity edit plus low-denoise style conversion
6. face or subject mask routes when supported
7. reference, edit, sampler, step, and denoise ranges
8. memory-reduced and full-power settings

Select by measured likeness, style, mask, reproducibility, and resource results.

Face swapping and subject replacement are forbidden.

## Identity gate

Reject:

- changed facial geometry
- changed eye spacing or shape
- changed nose, mouth, jaw, or chin
- lost asymmetry
- beautification, symmetrization, or genericization
- age or gender-presentation drift
- changed hairline or facial hair
- unjustified expression or head-direction drift
- added or removed glasses, hats, or accessories
- invented medals, jewelry, insignia, decorations, clothing, or hidden detail
- lost scars or visible markers
- mask leakage or boundary damage
- a filtered photograph without a genuine HOI4 painted conversion
- missing provenance

Identity is non-compensable. Style and visual appeal cannot compensate for identity FAIL or UNCERTAIN.

## Independent audit

A separate auditor process reviews candidates in randomized order without producer ranking.

The audit combines:

- calibrated face-embedding evidence when appropriate
- landmarks and facial proportions
- asymmetry
- head direction and expression
- hairline, facial hair, accessories, and visible markers
- native 156x210 review
- at least 4x enlarged nearest-neighbour review
- mask-boundary review
- style comparison against the correct approved HOI4 role references
- provenance validation

A candidate is eligible only when every mandatory hard gate is PASS. Any UNCERTAIN gate blocks autonomous finalization.

The auditor returns schema-valid candidate records and an unordered set of eligible candidate ids. The parent chooses among eligible candidates.

## Bounded retry

Retries may use only approved safer changes, such as lower edit or style strength, stronger reference conditioning, a more precise approved mask, reduced transformation area, or a measured one-pass or two-pass route change.

Record every failed attempt and changed parameter. Respect the retry ceiling.

## MCP and API

Keep MCP integration inside this skill and the standalone project. Do not create a broad central MCP skill.

Use an existing MCP only after discovering its actual tools and schemas and proving the required surface. Otherwise use the narrow project-owned adapter over the verified ComfyUI HTTP and WebSocket API.

The planned project-owned surface includes health, capabilities, inventory, workflow validation, workflow registration, authenticated upload, submission, status, progress, cancellation, output retrieval, history, and memory release.

Do not assume planned tool names exist until discovered from the installed route.

Reject unauthenticated public ComfyUI, arbitrary graph submission, arbitrary paths, URL-based source fetching, shell arguments from job text, or credentials in workflow JSON, jobs, logs, manifests, or Git.

## DDS

The final portrait is exactly 156x210.

Prefer the repository's verified deterministic converter when one exists. Otherwise use the standalone converter after calibration against current vanilla and repository precedents.

Validate dimensions, header, pixel format, channel masks, alpha, mipmap policy, decode, PNG pixel equivalence, expected size where applicable, final path, and checksum.

Manual Photoshop export is not a dependency.

## Repository integration

Before editing a mod repository:

1. discover current AGENTS and asset rules
2. discover character, portrait, GFX, and file-placement conventions
3. inspect the repository DDS converter and validation rules
4. inspect vanilla precedents for the target portrait role
5. verify the subject is not already owned by another live character
6. verify the accepted DDS checksum
7. copy it to the exact runtime path
8. create or update character and GFX references
9. verify a live in-game consumer
10. record final paths and validation evidence

The portrait pipeline does not claim completion before the live consumer check.

## Two-machine use

Use direct mode only when one session has verified read and write access to both the standalone portrait project and the target repository.

Otherwise exchange a portable checksummed job package and result package. Verify every returned checksum before integration.

## Completion

A real-person portrait is complete only when the source and crop are attributed and immutable, one candidate has an independent all-PASS audit, the final PNG is exactly 156x210, the DDS passes deterministic validation, every artifact is traceable, and the parent confirms a live in-game consumer.
