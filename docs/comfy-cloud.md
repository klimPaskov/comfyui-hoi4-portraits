# Comfy Cloud and MCP

The workflows use Comfy Cloud's available model and node catalog. No project
installation is required beyond the workflow files and the LoRA.

## Import the custom LoRA

Comfy Cloud cannot upload a model directly from your local disk through a
workflow. Import it from its hosted source:

1. Open **Models** in the Comfy Cloud sidebar.
2. Choose **Import**.
3. Paste the download or file-page URL for [`hoi4_portraits_flux2_klein_9b_lora_000002500.safetensors`](https://huggingface.co/Hoops-McCann/hoi4-portraits-flux2-klein-9b-lora/blob/main/hoi4_portraits_flux2_klein_9b_lora_000002500.safetensors).
4. Select model type **LoRA** and target folder `loras`.
5. Wait for the exact filename to appear in `LoraLoaderModelOnly`.

Model import requires a Comfy Cloud Creator or Pro plan.
The base FLUX.2 Klein 9B stack, RealESRGAN, and BiRefNet are present in the
Cloud catalog.

The processing workflow does not use the project LoRA, so this import is only
needed for the source and text-to-image workflows.

## Open a workflow

Use the editor-format `.json` file when opening or dragging a workflow into
Comfy Cloud. Use the `.api.json` counterpart only for MCP/API execution.

For source workflows, upload:

- a source named `source_portrait.jpg`, or select your uploaded filename in the loader;
- one background from [`backgrounds/`](../backgrounds/) if replacement is enabled.

Background replacement is off by default, so a background file is optional
unless you enable background replacement.

Keep denoise and the LoRA loader at `1.00`. Each source candidate begins with
the identity default shown in the workflow. Keep it unchanged or append one
deliberate requested edit; editing one candidate prompt does not affect the
other two. For text-to-image, begin with `hoi4_portrait,` and use a concise
general person description. Do not add game/style, background, lighting, or
rendering language.

In either source workflow, set the bounding box around the head and shoulders
and check the crop preview before queueing. The crop controls are available in
Comfy Cloud.

## MCP validation

The included API graphs can be checked without creating a GPU job:

```text
Use Comfy Cloud MCP to dry-run workflows/hoi4_portrait_flux2_klein_9b_source.api.json. Do not submit a generation and do not spend credits.
```

Before LoRA import, the preflight can report the filename as a catalog
advisory. Import the LoRA, select the exact file in the loader, and save the
workflow before generating.

## MCP execution

1. Upload source/background media with the Cloud file upload flow.
2. Replace the `LoadImage.image` values in the API graph with the returned filenames.
3. For a source graph, set the background replacement boolean to `true` only
   when background replacement is wanted. Leave it `false` otherwise.
4. Submit the API-format graph.
5. Wait for the returned prompt ID to reach a terminal state before claiming success.
6. Retrieve the output only after the job reports completion. A source run
   returns three candidate master/game-size pairs; review them and choose the
   candidate you want to install.

The workflows contain no paid partner/API nodes. Normal Comfy Cloud compute
and subscription limits still apply.

## Cloud checks

All three API graphs pass Comfy Cloud MCP `dry_run` preflight. The project LoRA
must be imported into the Cloud model library before generation. Cloud GPU
checks cover the source, processing, text-to-image, and final background paths
with a compatible catalog LoRA at zero strength. A Creator or Pro plan is
required for the project LoRA import.

Official references:

- [Import models into Comfy Cloud](https://docs.comfy.org/cloud/import-models)
- [FLUX.2 Klein workflows and model files](https://docs.comfy.org/tutorials/flux/flux-2-klein)
- [Comfy Cloud API reference](https://docs.comfy.org/development/cloud/api-reference)
