# Identity comparison workflows

Use one source image in every workflow and compare the saved candidates at
full size. The source processing, HOI4 LoRA checkpoint 2250, LoRA strength
`1.00`, denoise `1.00`, prompts, seeds, and sampler branches are identical.
Each comparison uses FLUX.2's canonical empty edit latent while the processed
portrait stays connected as native reference conditioning. The primary source
workflow remains the encoded-source control.

| Workflow | Method | Adjustable identity control |
| --- | --- | --- |
| [`identity_test_native`](../workflows/hoi4_portrait_flux2_klein_9b_source_identity_test_native.json) | Two native FLUX.2 references: original crop and selected processed result | None; baseline |
| [`identity_test_feature_mid`](../workflows/hoi4_portrait_flux2_klein_9b_source_identity_test_feature_mid.json) | Masked feature transfer with the MID profile | Feature-transfer controls |
| [`identity_test_feature_hard`](../workflows/hoi4_portrait_flux2_klein_9b_source_identity_test_feature_hard.json) | Masked feature transfer with the HARD profile | Feature-transfer controls |
| [`identity_test_dx_consistency`](../workflows/hoi4_portrait_flux2_klein_9b_source_identity_test_dx_consistency.json) | DX consistency LoRA V2 | Strength `0.40` |
| [`identity_test_lcs_consistency`](../workflows/hoi4_portrait_flux2_klein_9b_source_identity_test_lcs_consistency.json) | LCS consistency LoRA | Strength `0.50` |
| [`identity_test_sameface`](../workflows/hoi4_portrait_flux2_klein_9b_source_identity_test_sameface.json) | SameFace LoRA | Strength `1.00` |
| [`identity_test_refcontrol_lineart`](../workflows/hoi4_portrait_flux2_klein_9b_source_identity_test_refcontrol_lineart.json) | RefControl lineart first reference plus the ESRGAN identity reference | Strength `0.80`; Canny thresholds |
| [`identity_test_pulid`](../workflows/hoi4_portrait_flux2_klein_9b_source_identity_test_pulid.json) | PuLID Flux2 Klein v2 plus native references | Strength `1.40` |
| [`identity_test_composite`](../workflows/hoi4_portrait_flux2_klein_9b_source_identity_test_composite.json) | Native generation followed by Klein edit compositing | Composite mask and blend controls |

## Test procedure

1. Use the same source file and leave FLUX restoration off for the first pass.
2. Queue every workflow once without editing its defaults.
3. Compare candidate 1 against candidate 1 across workflows, then repeat for
   candidates 2 and 3. Do not compare different sampler branches as if they
   were the same control.
4. Score identity, facing direction, expression, retained objects, HOI4 style
   strength, colour, and facial detail.
5. Adjust only the identity control in a second pass when a method is close but
   too weak or too restrictive.

PuLID uses CUDA face analysis and needs more VRAM than the other tests. The
composite workflow is a post-generation control: it can retain source pixels
but may also weaken a full-image style change. Treat the native workflow as the
baseline for deciding whether an added method provides a real improvement.
