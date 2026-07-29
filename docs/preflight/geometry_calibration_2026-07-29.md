# Geometry calibration evidence

- Status: **GEOMETRY_EVIDENCE_MEASURED_PRODUCTION_BLOCKED**
- Calibration ID: `loc-daguerreotype-geometry-2026-07-29`
- Source collection: [Library of Congress Daguerreotypes Collection](https://www.loc.gov/collections/daguerreotypes/about-this-collection/)

This is preprocessing-invariance evidence using a pinned YuNet-selected face crop before MediaPipe landmarking. It does not modify the tracked threshold file and cannot authorize a portrait, PNG, DDS, or mod integration output.

- Fixtures: `50`; exactly-one-face: `44`
- Measurements: `175`; private manifest: `PASS`

| Signal | Count | P95 | P99 | Maximum |
| --- | ---: | ---: | ---: | ---: |
| `landmark_normalized_error` | 175 | 0.012320056179475288 | 0.02243965139519266 | 0.03135627319991576 |
| `pose_delta_yaw_degrees` | 175 | 1.4713990079575003 | 1.99893909726533 | 2.2230746411865265 |
| `pose_delta_pitch_degrees` | 175 | 1.3789875986343119 | 3.031438567081186 | 4.964682395047204 |
| `pose_delta_roll_degrees` | 175 | 0.6645364669575153 | 1.5830176580580155 | 4.248678949142786 |
| `expression_distance` | 175 | 0.05692535229479473 | 0.06998442287746623 | 0.08757547256585073 |
| `asymmetry_change` | 175 | 0.01266802871557901 | 0.02396310367947704 | 0.05112607220647673 |

## Proposed operating point (not approved)

- Basis: `observed_p99_preprocessing_invariance; not an approval`
- Landmark limit: `0.02243965139519266`
- Region limits: `{"eyes": 0.018898316387462758, "jaw": 0.02608663675461458, "mouth": 0.021529395652012524, "nose": 0.027566860174825535}`
- Pose limits: `{"pitch": 3.031438567081186, "roll": 1.5830176580580155, "yaw": 1.99893909726533}`
- Expression limit: `0.06998442287746623`
- Asymmetry limit: `0.02396310367947704`
- Approved: **False**

## Blockers

- these measurements cover preprocessing invariance only; source-specific generated-candidate acceptance is still required
- hairline, facial-hair, accessory, foreground-mask, and HOI4-style thresholds require separate labeled evidence
- the tracked production threshold file remains unchanged and fail-closed

Source images and biometric-derived landmarks remain private under the ignored fixture/job roots.
