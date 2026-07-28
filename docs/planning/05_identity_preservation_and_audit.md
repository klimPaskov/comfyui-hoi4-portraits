# Identity Preservation and Independent Audit

## Principle

Identity is a set of non-compensable gates. The system can rank artistic quality only after a candidate has preserved the subject.

The audit compares the immutable source master, exact crop, processed reference, generated candidate, final-size rendering, masks, and approved HOI4 references. It never evaluates only the final image in isolation.

## Audit independence

The producer and auditor must differ in all of these fields:

- process id
- role id
- output authority
- candidate-ranking access

The auditor may be a read-only `portrait_identity_auditor` subagent or a separate local service. It receives candidates in randomized order and does not receive the producer's preferred result. It cannot modify candidate files.

The auditor writes `portrait_audit.schema.json`. Only the controller can select a candidate, and only among auditor PASS records.

## Calibration before production

No universal face threshold is accepted from memory. Build a calibration set with consented, public-domain, synthetic, or otherwise legally usable portraits. Include:

- same person across resolution, crop, colorization, and conservative restoration
- same person after approved HOI4 style conversion
- visually similar different people
- age and gender-presentation variation
- glasses, hats, facial hair, scars, medals, jewelry, and strong asymmetry
- frontal and three-quarter views
- varied skin tones and photographic eras

Split calibration identities from acceptance identities.

For each metric, choose thresholds to target:

- false accept rate at or below 0.1 percent for the calibrated different-person set
- false reject rate at or below 5 percent for the calibrated same-person stylized set

If a model cannot meet both targets across the test strata, replace or supplement it. Do not loosen the identity threshold to make the pipeline appear successful.

Lock the result in `config/identity_thresholds/<id>.json`. Null or missing values block production.

## Layered audit

### 1. Provenance gate

PASS requires:

- attributed source or user-provided authorization
- immutable source checksum
- decoded-master checksum
- crop coordinates and crop checksum
- complete model and workflow lineage
- candidate and comparison checksums
- auditor identity and date

### 2. Face detection and association gate

The candidate must contain one face associated with the selected person. Extra generated faces, duplicated facial regions, or a face associated with background art fail.

### 3. Face embedding gate

Use a pinned, calibrated SFace model as one signal. Compute embeddings from several deterministic face crops and use the worst accepted comparison, not only the best crop. Record detector boxes, alignment transform, embedding vectors or protected hashes, and similarity.

Embedding PASS is necessary and insufficient.

### 4. Landmark and facial-proportion gate

MediaPipe or another pinned landmark model measures normalized geometry. Compare:

- inter-eye distance
- eye width and height
- brow-to-eye relationship
- nose length and width
- philtrum and mouth width
- jaw width and contour
- chin length and shape
- face length-to-width ratio
- left-right asymmetry

Normalize by stable facial dimensions and account for head pose. Use region-specific thresholds so one average cannot hide a changed nose or eye spacing.

### 5. Head direction and expression gate

Compare yaw, pitch, roll, gaze direction where reliable, mouth openness, smile or frown blendshapes, brow position, and eye openness. A style conversion may simplify texture. It may not change the person's expression or head direction beyond the calibrated tolerance.

### 6. Hairline and facial-hair gate

Use face and hair masks plus an independent visual checklist. Reject:

- receded or advanced hairline
- changed parting or silhouette
- invented or removed beard, moustache, sideburns, or stubble
- hidden hat boundary becoming hair

### 7. Accessory and identity-marker gate

Check glasses, hats, jewelry, medals, visible insignia, scars, moles, and other source-visible markers. The result can simplify painterly detail while preserving presence, approximate placement, and recognizable shape. Invented decorations or removed glasses fail.

### 8. Foreground and mask gate

Inspect:

- interior foreground equality before generation
- boundary leakage
- missing hair or hat pixels
- background halo
- transparent holes
- generated background painted into the person
- person pixels copied into background

### 9. Style gate

Compare against the approved role-specific HOI4 portrait reference set. PASS requires a genuine painted conversion, correct framing, value structure, restrained detail, and final-size readability. A photograph with only a filter fails. The style gate never rescues identity.

Use a validated style classifier or fixed VLM rubric plus human-readable evidence. Calibrate its threshold on approved HOI4 references and non-HOI4 negatives. Record the exact reference-set version.

### 10. Native and enlarged review

Create deterministic sheets:

- source, crop, processed source, candidate, and final 156 by 210 at native scale
- the same set at 4x nearest-neighbor
- face crops at a common scale
- edge and mask overlays
- source and candidate landmark overlays
- approved HOI4 role references without mixing their faces into identity metrics

## Hard verdict policy

- Any hard-gate FAIL means overall FAIL.
- Any hard-gate UNCERTAIN means overall UNCERTAIN.
- Overall PASS requires every hard gate PASS.
- Style scores, aesthetic scores, or producer preference cannot override this policy.
- A final PNG or DDS cannot exist for FAIL or UNCERTAIN jobs, except quarantined diagnostic files under `candidates/` and `audit/`.

## Retry policy

The controller may retry at most the job limit. A retry chooses the next safer preset:

1. increase reference fidelity within the tested range
2. reduce style LoRA strength
3. switch from single pass to identity-first two pass
4. lower style-pass denoise
5. reduce resolution if source bleed or duplication occurred
6. switch to full identity adapter when a reduced adapter failed
7. preserve more original clothing through a subject mask route

Every retry records the failed candidate ids, failure reasons, changed parameters, and new seeds. The controller stops early when the remaining preset ladder cannot address the failure.

## Candidate selection

A candidate can enter the selection pool only with overall PASS. Rank by:

1. worst-region geometry margin above threshold
2. embedding margin above threshold
3. pose and expression margin
4. accessory preservation
5. mask quality
6. style score
7. final-size readability

This order ensures style remains subordinate to likeness.

## Privacy

Face embeddings and landmarks are biometric-derived data. Store them only inside the private job root, apply the same retention policy as source photographs, and do not send them to third-party services unless the job explicitly authorizes that service and records the data flow.
