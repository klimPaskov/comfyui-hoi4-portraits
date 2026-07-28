# Geometry calibration evidence

- Status: **GEOMETRY_EVIDENCE_MEASURED_PRODUCTION_BLOCKED**
- Calibration ID: `loc-daguerreotype-geometry-2026-07-29`
- Source collection: [Library of Congress Daguerreotypes Collection](https://www.loc.gov/collections/daguerreotypes/about-this-collection/)

This is preprocessing-invariance evidence. It does not modify the tracked threshold file and cannot authorize a portrait, PNG, DDS, or mod integration output.

- Fixtures: `50`; exactly-one-face: `13`
- Measurements: `34`; private manifest: `PASS`

| Signal | Count | P95 | P99 | Maximum |
| --- | ---: | ---: | ---: | ---: |
| `landmark_normalized_error` | 34 | 0.02334887687695485 | 0.034676413226408215 | 0.039996115372979126 |
| `pose_delta_yaw_degrees` | 34 | 2.314404382062515 | 2.9399385224419494 | 3.0149289317116406 |
| `pose_delta_pitch_degrees` | 34 | 3.631389552031094 | 4.760181138345526 | 5.218004387977796 |
| `pose_delta_roll_degrees` | 34 | 2.541824320864782 | 3.1480254262016647 | 3.2848581810299056 |
| `expression_distance` | 34 | 0.09762789601295854 | 0.10865511407847038 | 0.11318815670334849 |
| `asymmetry_change` | 34 | 0.018007726041350283 | 0.0242901952230027 | 0.027320018000801312 |

## Proposed operating point (not approved)

- Basis: `observed_p99_preprocessing_invariance; not an approval`
- Landmark limit: `0.034676413226408215`
- Region limits: `{"eyes": 0.029579011899590103, "jaw": 0.03469606982635951, "mouth": 0.03761443754232472, "nose": 0.048125108089036}`
- Pose limits: `{"pitch": 4.760181138345526, "roll": 3.1480254262016647, "yaw": 2.9399385224419494}`
- Expression limit: `0.10865511407847038`
- Asymmetry limit: `0.0242901952230027`
- Approved: **False**

## Blockers

- these measurements cover preprocessing invariance only; source-specific generated-candidate acceptance is still required
- hairline, facial-hair, accessory, foreground-mask, and HOI4-style thresholds require separate labeled evidence
- the tracked production threshold file remains unchanged and fail-closed

Source images and biometric-derived landmarks remain private under the ignored fixture/job roots.
