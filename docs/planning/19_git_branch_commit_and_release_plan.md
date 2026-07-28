# Git, Branch, Commit, and Release Plan

## Standalone repository

Initialize the project on a branch named:

`feat/autonomous-hoi4-portrait-pipeline`

Suggested commit sequence:

1. `chore: initialize portrait pipeline project and contracts`
2. `feat: add deterministic intake crop mask and provenance nodes`
3. `feat: add Krea 2 workflow graph builder and four profiles`
4. `feat: add controller job API and ComfyUI MCP adapter`
5. `feat: add independent portrait audit and calibration tools`
6. `feat: add deterministic PNG and DDS finalization`
7. `feat: add RunPod deployment and authenticated gateway`
8. `test: add fixture matrix and acceptance suites`
9. `docs: add capability benchmarks and integration packages`

Keep commits bounded and runnable. Do not combine model download artifacts with source commits.

## Branch safety

- no force push
- no history rewrite after review starts
- no commit with failing secret scan
- no commit with model weights or real-person job data
- no merge until all mandatory acceptance gates pass or explicitly documented profile blockers are approved

## Releases

Release artifacts contain:

- source archive
- dependency and model lock metadata
- four workflow UI JSON files
- four workflow API JSON files
- schemas
- container recipe and digest reference
- integration packages
- checksums
- license and notice files
- benchmark and acceptance summary

Release artifacts exclude:

- Krea weights
- Qwen weights
- identity adapter weights
- user style LoRA
- private background
- source photos
- generated portraits
- audit embeddings
- credentials
- RunPod volume contents

## Versioning

Use semantic versioning for the standalone project. Version these separately in manifests:

- controller API
- MCP tool contract
- workflow graph specification
- each workflow JSON
- project node pack
- dependency lock
- model lock
- identity thresholds
- style thresholds
- background registry

A threshold change is a reviewed calibration change and invalidates prior production comparisons unless explicitly migrated.

## Pull requests for integrations

Chaos Redux and generic integrations use dedicated branches and draft pull requests. Each pull request states:

- source snapshot or live commit used
- new files
- modified routing files
- ownership changes
- validation run
- unavailable runtime tests
- rollback

## Release acceptance report

Create `docs/releases/<version>/acceptance.md` with:

- profile status
- fixture totals
- identity and style results
- local capability result
- remote result
- DDS result
- security result
- license result
- known blockers
- exact workflow and dependency checksums
