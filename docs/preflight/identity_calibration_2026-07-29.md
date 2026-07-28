# Identity calibration evidence

- Status: **BLOCKED_FACE_CALIBRATION_INCOMPLETE**
- Calibration ID: `loc-daguerreotype-face-embedding-2026-07-29`
- Source class: `public_domain_primary_archive`
- Source collection: [Library of Congress Daguerreotypes Collection](https://www.loc.gov/collections/daguerreotypes/about-this-collection/)

This is an aggregate calibration measurement. It does not modify the tracked threshold file and cannot authorize a portrait, PNG, DDS, or mod integration output.

## Measured set

- Fixture images: `50`
- Exactly-one-face fixtures: `46`
- Rejected fixtures: `4`
- Private manifest: `PASS` (50 declared / 50 observed)
- Same-person variant scores: `183`
- Different-person pairs: `1035` / `1000` required

## Observed SFace distribution

| Distribution | Minimum | P05/P99.9 | Median | Maximum |
| --- | ---: | ---: | ---: | ---: |
| Same-person variants | 0.518024990144113 | 0.9274091219101137 | 0.9764529401926332 | 1.0000000319389528 |
| Different-person pairs | — | 0.4647333824512428 | 0.15404127465257034 | 0.4804377850061883 |

Candidate operating point: `0.4804377850061883`; simultaneous target demonstrated: **True**.

## Blockers

- landmark, pose, expression, hair/accessory, mask, and style thresholds require separate calibrated evidence
- the tracked production threshold file remains unchanged and fail-closed

The production threshold record remains `config/identity_thresholds.json` with `fail_closed: true` and null acceptance values.

Source images and biometric vectors remain private under the ignored fixture/job roots.
