# Mask component prefix qualification — 2026-07-29

Status: **PASS_STRUCTURAL_COMPONENTS_ALTERNATIVE_COMPARISON_BLOCKED**

The live ComfyUI process was restarted after the custom-node update and the
non-generative prefix of `human_local_mac_16gb` was executed through the
background guard. The run passed source intake, subject selection, conservative
preprocessing, the new complete mask contract, and the approved-background
composite guard. Krea loading and sampling were intentionally not run in this
prefix check.

The service returned seven checked components: person alpha, hard interior,
face, hair/hat boundary, accessory attention, background, and boundary ring.
The selected face was fully contained by the person mask, and the guard found
zero interior pixel changes in 363,271 eroded foreground pixels.

Hair/hat and accessory outputs are explicitly structural attention masks, not
semantic classifiers. The planning requirement to compare BiRefNet against an
approved alternative remains a qualification blocker.

Machine-readable evidence: [`mask_component_execution_2026-07-29.json`](mask_component_execution_2026-07-29.json).
