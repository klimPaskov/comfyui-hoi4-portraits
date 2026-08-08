# Comfy Cloud and MCP

The workflows use Comfy Cloud's model catalog and require the bundled
`hoi4_portraits` folder in the Builder custom-node environment. Import the
custom-node folder and restart the Builder environment before opening a
workflow. The GGUF variant is not available in Cloud (Cloud uses safetensors);
use the full or FP8 distilled model there.

## Import the custom LoRA

Comfy Cloud cannot upload a model directly from your local disk through a
workflow. Import it from its hosted source:

1. Open **Models** in the Comfy Cloud sidebar.
2. Choose **Import**.
3. Paste the URL for
   [`hoi4_portrait_flux2_klein_9b_lora_000002500.safetensors`](https://huggingface.co/Hoops-McCann/hoi4-portraits-flux2-klein-9b-lora/blob/main/hoi4_portrait_flux2_klein_9b_lora_000002500.safetensors).
   Import [`adonis_base.safetensors`](https://huggingface.co/n8te0/adonis_flux2klein/blob/main/adonis_base.safetensors)
   and `adonis_post.safetensors` when you want optional restoration.
4. Select model type **LoRA** and target folder `loras`.
5. Wait for the exact filename to appear in `LoraLoaderModelOnly`.

Model import requires a Comfy Cloud Creator or Pro plan. The distilled FLUX.2
Klein 9B stack, RealESRGAN, and BiRefNet are present in the Cloud catalog.

The processing workflow does not use the project LoRA, so this import is only
needed for the source, text-to-image, and batch workflows.

## Open a workflow

Use the editor-format `.json` file when opening or dragging a workflow into
Comfy Cloud. Use the `.api.json` counterpart only for MCP/API execution.

For source and batch workflows, upload:

- source images (a `source_portrait.jpg`, or your uploaded filenames);
- one background from [`backgrounds/`](../backgrounds/) if replacement is
  enabled.

Background replacement is off by default. Keep the source prompt exactly as
`make this portrait hoi4_portrait style` and append only deliberate changes.
For text-to-image, use the exact example prompt
`hoi4_portrait style, an Irish middle-aged man with neatly combed dark hair,
wearing a plain civilian jacket.` and edit the person description without
game/style, background, lighting, or rendering language.

In the source, processing, and batch workflows, **Face zoom** defaults to
`0.90`; lower values retain more of the body. **Preserve hat/headwear**
defaults to `true`. Turn off **Toggle face processing** to keep a full
multi-person composition. FLUX restoration opens enabled. Check the
processing previews before queueing.

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
   when background replacement is wanted.
4. Submit the API-format graph.
5. Wait for the returned prompt ID to reach a terminal state before claiming success.
6. Retrieve the output only after the job reports completion. A source run
   returns three candidate master/game-size pairs; the batch graph returns one
   output per input image.

The workflows contain no paid partner/API nodes. Normal Comfy Cloud compute
and subscription limits still apply.

## Cloud checks

All four API graphs pass Comfy Cloud MCP `dry_run` preflight. The project LoRA
must be imported into the Cloud model library before generation. Cloud GPU
checks cover the source, processing, text-to-image, and final background paths
with a compatible catalog LoRA at zero strength.

Official references:

- [Import models into Comfy Cloud](https://docs.comfy.org/cloud/import-models)
- [FLUX.2 Klein workflows and model files](https://docs.comfy.org/tutorials/flux/flux-2-klein)
- [Comfy Cloud API reference](https://docs.comfy.org/development/cloud/api-reference)
