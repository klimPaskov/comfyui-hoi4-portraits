# Risks, Blockers, and Fallbacks

## No silent fallback rule

A fallback is accepted only when it preserves Krea 2, the identity gate, provenance, independent review, and output contracts. Replacing Krea 2, generating a new face, skipping the auditor, or using an arbitrary background is not a fallback.

## Risk register

| Risk | Evidence | Mitigation | Blocking condition |
| --- | --- | --- | --- |
| Krea 2 cannot run on 16 GB MPS | model files exceed physical memory before activations | staged loading, verified offload, supported reduced format, one candidate at a time | all approved variants fail |
| FP8 or other Krea format lacks MPS kernel support | file availability does not prove platform support | live loader and execution test | unsupported operation or unusable output |
| identity edit geometry regression | model card reports typical-proportion drift | regional landmarks, calibration, full adapter, higher reference fidelity, two-pass route | geometry hard gate fails |
| style LoRA incompatible with Turbo | LoRA file unavailable during planning | checksum, metadata, RAW and Turbo test | cannot load or trigger correctly |
| adapter order unsupported | live model chain may restrict order | inspect actual node schemas and test only supported graphs | required comparison impossible, record limitation |
| mask route unsupported by Krea nodes | edit nodes do not promise arbitrary masks | use deterministic composite and qualified inpaint or protected style route only if supported | no safe route for required boundary preservation |
| approved background missing | no exact asset available | resolver from project or installed game | registry remains unresolved |
| autoprompter invents role or insignia | VLM uncertainty | exact validator, metadata allowlist, independent claim verification, retry | unsupported claim remains |
| colorizer invents uniform colors | generative colorization | keep monochrome identity master, structure gate, no claim authority | geometry or accessory change |
| restoration genericizes face | common face restoration risk | classical baseline, no GFPGAN or CodeFormer default | identity gate worsens |
| SFace threshold bias or weak stylized performance | one embedding cannot cover all identities | calibrated strata, landmarks, independent review, alternate model evaluation | target FAR and FRR not achieved |
| current custom node changes | node package is very recent | pin commit, schema hash, regression suite | import or output regression |
| first-party local MCP unavailable | private test | project-owned adapter over official API | no verified API route for required operation |
| public RunPod exposure | exposed ports become public | loopback ComfyUI, authenticated gateway, rate limit | raw ComfyUI reachable publicly |
| RunPod proxy timeout | 100-second HTTP limit | asynchronous 202 plus status polling | long synchronous endpoint only |
| license restriction | Krea community terms and source-image rights | legal review and local-copy-only assets | use or redistribution not permitted |
| live repo diverges from snapshots | uploaded files are not the Windows working copy | inspect live files and regenerate patches | direct replacement without review |
| producer self-approval | autonomy pressure can collapse roles | separate process and schema-enforced auditor identity | same process or ranking access |
| DDS precedent differs | converter unavailable during planning | inspect current repo and vanilla headers | byte contract cannot be verified |

## Approved fallback ladder

### Local generation

1. full identity adapter with offload
2. r128 after quality test
3. r64 after quality test
4. lower qualified resolution
5. remove optional ML upscale
6. stop local generation and use remote workflow as a separately labeled route

### Generation quality

1. increase reference fidelity within tested bounds
2. reduce style strength
3. use identity-first two pass
4. lower second-pass denoise
5. use full identity adapter
6. remote full-power rerun
7. fail or request review

### Background

1. redistributable project source
2. canonical project private source
3. installed-game local copy
4. block

### MCP

1. first-party Local MCP after access and parity
2. project-owned local adapter
3. project-owned remote gateway and adapter
4. block if ComfyUI API changes prevent safe operation

## Forbidden substitutions

- another base model in place of Krea 2
- face swap
- generated substitute for a real person
- unverified Krea GGUF or NF4
- unverified mirror
- random generated background
- manual Photoshop DDS
- producer-selected image without independent PASS
- remote job described as local generation
- model weights or secrets in Git
