# Shared Processing Pipeline

## Stage classification

| Stage | Class | Mandatory | Main output | Failure behavior |
| --- | --- | --- | --- | --- |
| `source_intake` | deterministic | yes | immutable source and decoded master | fail closed |
| `person_and_face_analysis` | deterministic ML analysis | yes | subject inventory and selected face | fail on no face or ambiguity |
| `crop_and_pose_normalization` | deterministic | yes | exact 26:35 crop | fail on unusable crop |
| `black_and_white_detection` | deterministic classifier | yes | monochrome verdict and confidence | uncertain skips colorization and warns |
| `conditional_colorization` | generative restoration | conditional | colorized conditioning derivative | skip or fail when harmful |
| `restoration_and_upscale` | deterministic plus optional ML | yes as a stage, optional operations | conservative processed reference | revert harmful operation |
| `subject_matting_and_mask_validation` | ML plus deterministic audit | yes | person, face, accessory, and background masks | fail on leakage or missing coverage |
| `hoi4_background_composite` | deterministic | yes | approved composite | fail unless foreground integrity is exact |
| `prompt_input_or_autoprompt` | VLM for human, direct input for agent | yes | validated `hoi4_portrait,` prompt | fail on format or claim validation |
| `krea_2_identity_edit` | generative | yes | identity-conditioned latent route | fail on dependency or execution error |
| `hoi4_lora_stylization` | generative | yes | HOI4 styled candidate | fail if LoRA compatibility is absent |
| `candidate_generation` | generative orchestration | yes | bounded candidate set | retry within limit |
| `identity_and_quality_evaluation` | deterministic ML plus independent review | yes | per-candidate audit | fail or uncertain rejects candidate |
| `candidate_selection` | deterministic policy | yes | one audited candidate | fail when none pass |
| `final_156x210_processing` | deterministic | yes | final PNG | fail on dimensions or alpha |
| `dds_conversion` | deterministic | yes after audit | validated DDS | fail on any byte or pixel check |
| `manifest_and_audit_export` | deterministic | yes | complete evidence package | fail on missing record |

## 1. Source intake

1. Copy the original file bytes to `source/original/` without modification.
2. Record source path, source URL or user-provided status, attribution, archive, date, rights notes, byte size, MIME type, and SHA-256.
3. Decode once with a pinned library and apply EXIF orientation to a separate decoded master.
4. Record original orientation metadata and the exact orientation transform.
5. Save the decoded master losslessly and record a decoded pixel hash over width, height, mode, and pixel bytes.
6. Reject unsupported formats, corrupt decodes, zero dimensions, decompression bombs, extreme dimensions, or embedded payloads that violate input policy.
7. Never overwrite the original.

## 2. Person and face analysis

Use YuNet for face proposals and a person detector or segmentation model for body proposals. Use MediaPipe Face Landmarker for landmarks and head pose after face selection.

### Single-person automatic selection

Automatic selection is allowed when exactly one valid face is associated with exactly one person region and its confidence clears the calibrated selection threshold.

### Multiple-person rule

Agent jobs must provide one of:

- `bbox_xyxy`
- `face_index` from a prior subject inventory response
- a deterministic `subject_hint` that resolves to one candidate under a locked rule

Human workflows display a face contact sheet with stable indices and allow the user to select one index. The graph remains unchanged.

If several candidates remain plausible, return exit code 12 and `AMBIGUOUS_SUBJECT`. Never pick the largest or most central face silently.

### Face quality gate

Reject a face when the crop cannot preserve the eyes, nose, mouth, jaw, and enough head boundary for a portrait audit. Occlusion, severe blur, and tiny faces may be recoverable through conservative upscale, but the original still needs enough structure for identity comparison.

## 3. Crop and pose normalization

The crop is head-and-shoulders at the exact final aspect ratio of 26:35.

The crop algorithm uses:

- selected face landmarks
- person bounding box
- hair and hat extent from the person mask
- source-visible shoulder extent
- head direction
- target role

It computes the crop in original decoded-master coordinates, then records `left`, `top`, `right`, `bottom`, padding, and any canvas fill. It must avoid cutting hats, hair, medals, glasses, or visible shoulders when source pixels exist.

Pose normalization means metadata correction, crop placement, and optional small camera-roll correction. It does not frontalize the face, change expression, mirror the subject, rotate the head, or reconstruct hidden facial areas. Any geometric transform is recorded as a matrix and must preserve the crop pixel relationship.

## 4. Black-and-white detection

Classify in linear sRGB and CIELAB using a calibrated combination of:

- median and percentile chroma
- saturation distribution
- channel correlation
- proportion of pixels outside a neutral tolerance
- scanner tint and sepia detection

Return `MONOCHROME`, `COLOR`, or `UNCERTAIN` with component measurements. Classification thresholds live in a versioned file.

- `MONOCHROME`: colorization may run.
- `COLOR`: colorization is bypassed.
- `UNCERTAIN`: colorization is bypassed, a warning is recorded, and the human workflow may request review. Autonomous jobs continue with the original unless the profile policy says the source is unusable.

## 5. Conditional colorization

DDColor is the first candidate, subject to live license and integration verification.

Rules:

- The monochrome crop remains the identity master.
- The colorized image is a conditioning derivative.
- Do not infer nationality, medal type, ribbon color, insignia, uniform branch, jewelry material, or eye color from the colorized result.
- Preserve luminance edges and face landmarks within calibrated tolerances.
- Run a structure comparison against the monochrome input.
- Reject colorization that changes facial features, creates decorations, paints over glasses, or alters clothing geometry.
- Save model, revision, checksum, seed if any, and every parameter.

## 6. Restoration and upscale

Apply operations from safest to strongest:

1. lossless decode and color management
2. mild deterministic denoise for compression noise when measured
3. conservative deblur only when blur is detected and edge ringing remains below threshold
4. Lanczos resize to the working canvas
5. optional Real-ESRGAN or another approved model only after A/B identity comparison

GFPGAN, CodeFormer, and other face reconstruction systems are disabled by default because they can replace identity geometry with a learned generic face. Enabling one requires an explicit experiment, a documented user decision, and separate acceptance thresholds.

Every optional operation must produce an A/B comparison. The controller uses the least invasive branch that reaches generation readiness.

## 7. Subject matting and masks

Create:

- person alpha matte
- hard interior person mask
- face mask
- hair and hat boundary mask
- accessory attention mask for glasses, facial hair, jewelry, medals, and visible insignia
- background mask
- boundary ring

BiRefNet is the first matte candidate. The implementation must compare it with at least one approved alternative on hair, hats, glasses, shoulder edges, and low-resolution sources.

Mask validation checks:

- selected face lies inside person mask
- no disconnected foreground island beyond allowed size
- no holes through face or clothing
- hair and hat coverage
- glasses and thin-accessory coverage where visible
- alpha bounds and finite values
- background leakage ratio
- boundary continuity

## 8. Approved background composite

The background comes only from `background_registry.json` with approved status and matching checksum.

Composite the processed foreground using its alpha over the background. The operation must not retouch the person.

Hard foreground-integrity test:

- Erode the hard person mask to remove the antialiased boundary ring.
- Compare every pixel inside the eroded interior between the processed foreground and the composite.
- Required equality is 100 percent before generation.
- Differences are permitted only in the recorded boundary ring where alpha blending occurs.
- Save a difference image and numeric report.

## 9. Prompt

Human graphs call the autoprompter after crop, orientation correction, conditional colorization, and restoration. Agent graphs receive the prompt from the job contract. Both routes use the same validator and must begin exactly `hoi4_portrait,`.

The person's record name stays in provenance and integration metadata. It is never inserted into the model prompt.

## 10 to 12. Krea identity edit, style LoRA, and candidate generation

### Baseline wiring

Use the pinned Krea 2 Turbo model, Krea Qwen encoder, Qwen VAE, identity edit LoRA, `Krea2EditModelPatch`, `Krea2EditGroundedEncode`, and the official example sampler baseline.

The processed source and background composite are strong references. The implementation must determine whether the best identity route uses the pre-background or post-background image as the edit reference. It must never use face swap or replace the person.

### Required architecture experiment

Run a factorial experiment with repeated seeds on an approved calibration fixture set.

| Axis | Required values |
| --- | --- |
| identity adapter | absent, full v1.2, r128, r64 where profile permits |
| style LoRA | absent, low, medium, high strengths selected from preliminary safe range |
| adapter order | identity then style, style then identity when the live model chain supports both |
| pass structure | single pass, two pass |
| first-pass reference | processed source, approved composite |
| mask route | no generation mask, person mask, face-protection or subject mask when supported |
| `ref_boost` | documented strong-likeness baseline plus lower and higher bounded values |
| `grounding_px` | 512, 768, 1024 when the profile can run them |
| steps | 8, 10, 12 |
| CFG | 1.0 for Turbo baseline |
| sampler | Euler with simple scheduler baseline, plus another sampler only when Krea documentation or measured compatibility supports it |
| style-pass denoise | bounded low-denoise sweep, initially 0.10 to 0.30 |
| working resolution | local and full-power canvases |

The full matrix can use a staged design to control cost. Start with screening, remove routes that fail identity, then expand only surviving routes.

### Two-pass route

Pass one performs identity-preserving repaint with the identity adapter and little or no style LoRA. Pass two applies the style LoRA at low denoise while conditioning on the pass-one result and original identity reference. Reject the route if pass two worsens any hard identity gate.

### Candidate budget

- Local default: 2 candidates in one attempt, maximum 2 retries.
- Full power default: 6 candidates in one attempt, maximum 2 retries.
- Each retry must change only a documented safer parameter set.
- A retry cannot hide a failed candidate or overwrite prior evidence.

## 13. Identity and quality evaluation

Evaluation happens outside the producer graph. See `05_identity_preservation_and_audit.md`.

## 14. Candidate selection

Selection order:

1. Remove every candidate with any FAIL or UNCERTAIN hard gate.
2. Remove every candidate with provenance or mask failure.
3. Among remaining candidates, rank by calibrated identity metrics.
4. Apply style and final-size readability ranking only after identity ties are within the allowed equivalence band.
5. Record the rule and all rejected candidate ids.

A candidate with the best artwork but weaker likeness is never selected.

## 15. Final 156 by 210 processing

Use a deterministic transform from the selected working candidate:

- crop only when the generated canvas deviates from 26:35 and the crop does not remove subject evidence
- resize with the locked high-quality filter
- convert to the locked color space
- remove accidental alpha unless the verified HOI4 precedent requires it
- save lossless PNG at exactly 156 by 210
- create native and 4x nearest-neighbor comparison sheets

No sharpening or face restoration is allowed after audit unless that operation was part of the audited candidate path.

## 16. DDS conversion

Conversion begins only after independent PASS. See `14_dds_export_and_validation.md`.

## 17. Manifest and audit export

The final manifest includes every source, transform, model, node, workflow, prompt, seed, candidate, comparison, threshold, verdict, final file, and checksum. Missing required evidence changes the job to `FAILED` or `BLOCKED` even when an image appears usable.
