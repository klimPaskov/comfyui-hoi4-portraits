# Test Matrix and Acceptance Criteria

## Fixture policy

Use a private acceptance set for real-person identity tests and a redistributable CI set made from synthetic subjects, consented subjects, or public-domain sources with clear rights. Never commit private real-person fixtures or derived portraits.

Every fixture records source class, rights, checksum, selected subject, expected branches, and expected outcome.

## Required fixture set

| Fixture | Required branch or risk | Expected evidence |
| --- | --- | --- |
| clear color portrait | baseline, skip colorization | crop, masks, prompt, candidates, audit |
| black-and-white archival portrait | colorization gate | monochrome measurements, original and colorized derivative |
| very low-resolution portrait | conservative upscale | A/B restoration and identity comparison |
| compressed image | artifact handling | compression detector and denoise branch |
| cluttered background | matting | boundary overlay and leakage report |
| off-center person | crop placement | source-coordinate crop evidence |
| full-body source | person-to-face crop | person box, face box, head-and-shoulders result |
| three-quarter head angle | pose preservation | yaw and expression comparison |
| glasses | thin accessory preservation | glasses mask and visual gate |
| hat or military cap | crop and boundary | full hat coverage and no invented insignia |
| facial hair | identity marker | facial-hair agreement |
| visible medals or jewelry | no invention or removal | accessory checklist and source comparison |
| uneven lighting | identity under lighting change | embedding and landmarks across processed source |
| partial damage or scratches | restoration restraint | damage-preservation or safe cleanup evidence |
| multiple people | deterministic selection | face inventory, selector, ambiguity failure test |

Add fixtures for scars, strong asymmetry, distinctive nose, unusual eye spacing, older subjects, varied skin tones, civilian clothing, commander uniforms, and operative framing because the identity edit model reports a risk of geometry regression.

## Unit tests

### Source and provenance

- exact byte copy
- SHA-256 correctness
- EXIF rotation cases
- decode failure
- decompression limit
- path traversal rejection
- rights-field validation

### Crop

- exact 26:35 ratio
- coordinate round-trip
- no negative coordinates after padding
- hat and shoulder inclusion
- face and person association
- deterministic multi-face indexing

### Monochrome

- true grayscale
- sepia scan
- weak color tint
- low saturation color image
- uncertain case
- no colorization on color input

### Prompt

- exact prefix
- one-line rule
- name leak
- prohibited style or background term
- unsupported nationality, ideology, role, medal, or insignia
- no content rewrite by cleaner

### Masks and composite

- alpha range
- connected components
- face containment
- hair boundary
- interior pixel equality at 100 percent
- boundary leakage
- no foreground mutation

### Schemas and exit codes

- valid and invalid examples for every schema branch
- every failure maps to one documented exit code
- no success payload lacks required final fields

### DDS

- known header fixture
- dimensions
- channel masks
- file size 131168 under the locked uncompressed profile
- alpha cases
- independent decode
- pixel equality

## Integration tests

- empty project bootstrap in a temporary root
- custom-node imports
- model lock restoration with a local test mirror of official files
- checksum mismatch
- missing model
- missing node
- workflow UI import
- API JSON queue
- WebSocket progress
- interruption
- history retrieval
- model unload
- local MCP stdio
- remote gateway auth
- output authorization
- RunPod persistent volume restart

## Workflow policy tests

For each of the four workflow JSON files:

- JSON parses
- node ids are unique
- required groups exist in order
- no missing node placeholder
- all model references resolve
- all evidence outputs connect
- mandatory gates cannot be bypassed
- human graph contains exactly one approved autoprompter route
- agent graph contains no autoprompter node, VLM client, or prompt fallback
- local and full-power graph stage topology matches
- UI controls match the profile allowlist

## Identity experiment acceptance

Use the required architecture matrix from `03_shared_processing_pipeline.md`.

For each route, report:

- total candidates
- overall PASS rate
- identity FAIL rate
- geometry FAIL rate by facial region
- accessory FAIL rate
- mask FAIL rate
- style PASS rate among identity PASS candidates
- median and tail runtime
- peak memory
- repeated-seed variance

A route is eligible only when it passes all hard thresholds and no tested identity stratum falls below its minimum acceptance rate. Select by identity margin first.

## Autoprompter acceptance

Set locked targets after a pilot set. At minimum, production requires:

- 100 percent exact trigger after bounded retry
- 100 percent one-line structural compliance after bounded retry
- zero person's-name leaks
- zero accepted unsupported nationality, ideology, role, medal, or insignia claims in the acceptance set
- deterministic rejection of prohibited background, lighting, style, palette, image-quality, and composition content

## Local acceptance

- clean install on the detected Mac
- all four workflows load
- local human and local agent graphs execute the target fixtures
- no manual node repair
- no unhandled OOM
- two consecutive full jobs pass without restarting the machine
- staged unloading works
- measured runtime and thermal report exists
- identity and style gates equal the remote standard

If local Krea generation cannot pass, mark this acceptance section failed and produce the infeasibility report. Do not weaken the gates.

## Remote acceptance

- clean Pod from empty volume
- authenticated upload
- asynchronous submit
- progress polling or streaming
- cancellation
- output download and checksum
- persistence across Pod restart
- no raw ComfyUI exposure
- cost cap and idle shutdown
- 48 GB and 80 GB benchmark or a documented availability blocker

## Security tests

- missing token
- invalid token
- expired token
- wrong caller output access
- oversized upload
- polyglot or malformed file
- path traversal in filename and job id
- arbitrary workflow submission attempt
- URL fetch attempt
- command injection strings
- log secret redaction
- manifest secret scan
- Git history secret scan

## Mod integration acceptance

The portrait pipeline stops at a production handoff. Parent integration tests:

- accepted DDS copied to exact gameplay path
- character or portrait definition updated
- sprite or GFX reference updated
- no duplicate real-person ownership
- live consumer resolves
- game loads without relevant error
- screenshot or equivalent runtime evidence
- rollback restores previous file set

## Completion checklist

A release is blocked when any of these remain:

- missing source-reading item
- unresolved background
- style LoRA checksum or compatibility absent
- unpinned dependency
- missing license review
- missing workflow load evidence
- uncalibrated identity threshold
- producer self-approval
- failed DDS round trip
- local profile claimed without local test
- public unauthenticated ComfyUI
- integration applied without live repository inspection
