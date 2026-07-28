# Identity and Style Comparison

- Status: **BLOCKED_NO_REAL_CANDIDATES**
- Reason: No comparison sheet or candidate ranking is produced without a production-authorized source fixture, live generation runtime, calibrated thresholds, and independent audit evidence.
- Matrix: `krea2_identity_style_factorial_v1`

No candidate comparison was generated. The absence of a sheet is intentional while the hard gates are blocked.

## Required selection order

identity_gates → geometry_gates → accessories → mask → style → runtime → reproducibility

## Blockers

- Identity/style thresholds are still calibration placeholders; no production candidate may be accepted.
- Krea 2 source-specific eight-step execution and the immutable style-LoRA experiment matrix remain blocked: the detected 16 GB Mac exhausted practical memory/offload headroom after the FP8/MPS dtype workaround, and calibrated audit thresholds are still required.

## Metrics

All values remain `null` until real candidates and independent audits exist.
