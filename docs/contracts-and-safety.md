# Contracts and safety

The schemas are normative JSON contracts. Do not add fields casually or pass a UI-only object where an API contract is required.

## Normative schemas

- [`portrait_job_input.schema.json`](../schemas/portrait_job_input.schema.json)
- [`portrait_job_output.schema.json`](../schemas/portrait_job_output.schema.json)
- [`portrait_audit.schema.json`](../schemas/portrait_audit.schema.json)
- [`visual_audit_evidence.schema.json`](../schemas/visual_audit_evidence.schema.json) (private, hash-bound visual evidence)
- [`visual_reference_set.schema.json`](../schemas/visual_reference_set.schema.json) (private, rights-attested role references)
- [`portrait_benchmark_report.schema.json`](../schemas/portrait_benchmark_report.schema.json)
- [`portrait_comparison_report.schema.json`](../schemas/portrait_comparison_report.schema.json)

## Production audit gates

The independent auditor must recompute and PASS every hard gate:

`face_embedding`, `landmarks`, `facial_proportions`, `asymmetry`, `head_direction`, `expression`, `hairline`, `facial_hair`, `accessories`, `foreground_integrity`, `mask_boundary`, `style`, and `provenance`.

The auditor is read-only, receives randomized candidate order, cannot see producer ranking, and must use a calibrated threshold ID. Synthetic acceptance fixtures are test-only and cannot authorize production DDS.

Hairline, facial-hair, accessory, and style gates consume only an independent private visual-audit record. The record must bind the exact source and candidate hashes, the qualified auditor process, the pinned model artifact, and the approved role-specific reference-set manifest. Missing, malformed, contradictory, uncalibrated, or non-independent evidence remains `UNCERTAIN`. This consumer never creates scores or approves thresholds.

## Exit-code families

| Code | Meaning |
| ---: | --- |
| 0 | Success |
| 10–14 | Invalid input, source, subject, or provenance |
| 15 | Background unresolved |
| 20–23 | Dependency, model, node, or workflow failure |
| 30–32 | Runtime, generation, or cancellation failure |
| 40–43 | No eligible candidate or audit uncertainty |
| 50–51 | DDS or integration blocked |
| 60 | Remote authentication or transport failure |
| 70 | Internal error |

The complete enum is in [`src/portrait_pipeline/constants.py`](../src/portrait_pipeline/constants.py). A blocked result is evidence of an unavailable or unproven gate, never a successful generation claim.

## Privacy and transport

Raw ComfyUI listens only on loopback. Remote calls require the project gateway token, job ownership headers, bounded uploads, SHA-256 metadata, idempotency keys, and path containment. Secrets and private media stay outside Git.
