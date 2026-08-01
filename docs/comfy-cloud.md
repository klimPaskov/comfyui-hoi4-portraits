# Comfy Cloud and MCP

The v2 workflows were designed against Comfy Cloud's live model and node
catalog. They use no repository-specific custom nodes.

## Import the custom LoRA

Comfy Cloud cannot upload a model directly from your local disk through a
workflow. Import it from its hosted source:

1. Open **Models** in the Comfy Cloud sidebar.
2. Choose **Import**.
3. Paste the download or file-page URL for [`hoi4_portraits_flux2_klein_9b_lora_000002500.safetensors`](https://huggingface.co/Hoops-McCann/hoi4-portraits-flux2-klein-9b-lora/blob/main/hoi4_portraits_flux2_klein_9b_lora_000002500.safetensors).
4. Select model type **LoRA** and target folder `loras`.
5. Wait for the exact filename to appear in `LoraLoaderModelOnly`.

Model import currently requires a Comfy Cloud Creator or Pro plan.
The base FLUX.2 Klein 9B stack, RealESRGAN, and BiRefNet are present in the
Cloud catalog.

## Open a workflow

Use the editor-format `.json` file when opening or dragging a workflow into
Comfy Cloud. Use the `.api.json` counterpart only for MCP/API execution.

For source workflows, upload:

- a source named `source_portrait.jpg`, or select your uploaded filename in the loader;
- one background from [`backgrounds/`](../backgrounds/) if replacement is enabled.

Background replacement is off by default, so a missing background asset does
not need to execute on the default lazy branch.

## MCP validation

The included API graphs can be checked without creating a GPU job:

```text
Use Comfy Cloud MCP to dry-run workflows/hoi4_portrait_flux2_klein_9b_full_power.api.json. Do not submit a generation and do not spend credits.
```

Expected result before LoRA import: structural validation passes and the LoRA
filename may be reported as a non-blocking catalog advisory. After import,
select the exact file in the loader and save the workflow.

## MCP execution

1. Upload source/background media with the Cloud file upload flow.
2. Replace the `LoadImage.image` values in the API graph with the returned filenames.
3. Submit the API-format graph.
4. Wait for the returned prompt ID to reach a terminal state before claiming success.
5. Retrieve the output only after the job reports completion.

The workflows contain no paid partner/API nodes. Normal Comfy Cloud compute
and subscription limits still apply.

## Current preflight evidence

On 2026-08-01, all three API graphs passed Comfy Cloud MCP `dry_run` preflight.
Cloud GPU runs also completed the ESRGAN-only, full-power, text-to-image, and
final background-compositing paths using a compatible catalog LoRA at zero
strength. The project LoRA remains unavailable on plans without custom model
imports and must be imported on Creator or Pro before style quality can be
validated.

Official references:

- [Import models into Comfy Cloud](https://docs.comfy.org/cloud/import-models)
- [FLUX.2 Klein workflows and model files](https://docs.comfy.org/tutorials/flux/flux-2-klein)
- [Comfy Cloud API reference](https://docs.comfy.org/development/cloud/api-reference)
