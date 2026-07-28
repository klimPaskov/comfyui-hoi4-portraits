# Identity and Style Comparison

- Status: **BLOCKED_DIAGNOSTIC_CANDIDATES_NOT_PRODUCTION_AUTHORIZED**
- Reason: Diagnostic candidates were observed, but no comparison ranking or production winner is produced until calibrated thresholds and independent all-PASS audits authorize them.
- Matrix: `krea2_identity_style_factorial_v1`

No production comparison ranking was generated. Diagnostic candidates, when present, remain quarantined while the hard gates are blocked.

## Required selection order

identity_gates → geometry_gates → accessories → mask → style → runtime → reproducibility

## Blockers

- Calibration evidence exists but does not yet demonstrate the required approved identity/style threshold set; no production candidate may be accepted.
- Krea 2 source-specific production acceptance and the immutable style-LoRA experiment matrix remain blocked: the default MPS routes fail, the CPU fallback completed only one heavily-swapping run, and calibrated audit thresholds plus independent audit evidence are still required.

## Metrics

All values remain `null` until real candidates and independent audits exist.
