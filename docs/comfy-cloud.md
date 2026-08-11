# Comfy Cloud

The workflows run in Comfy Cloud. Before opening one, import the bundled
`hoi4_portraits` custom-node folder in the Builder environment and restart it.
The GGUF model variant is not available in Cloud (Cloud uses the standard
model files); use the full or FP8 variant there.

## Import the LoRA

Comfy Cloud cannot upload a model from your local disk through a workflow.
Import it from its hosted source:

1. Open **Models** in the Comfy Cloud sidebar.
2. Choose **Import**.
3. Paste the URL for
   [`hoi4_portrait_flux2_klein_9b_lora_000002500.safetensors`](https://huggingface.co/Hoops-McCann/hoi4-portraits-flux2-klein-9b-lora/blob/main/hoi4_portrait_flux2_klein_9b_lora_000002500.safetensors).
   Import [`adonis_base.safetensors`](https://huggingface.co/n8te0/adonis_flux2klein/blob/main/adonis_base.safetensors),
   [`adonis_refine.safetensors`](https://huggingface.co/n8te0/adonis_flux2klein/blob/main/adonis_refine.safetensors),
   and [`adonis_post.safetensors`](https://huggingface.co/n8te0/adonis_flux2klein/blob/main/adonis_post.safetensors)
   when you want restoration.
4. Select model type **LoRA** and target folder `loras`.
5. Wait for the exact filenames to appear in the model library, then select
   them on the separate visible style, Adonis Base, and Adonis Post LoRA loaders.
   Refine is downloaded for the supported alternative first pass but is not
   selected by the default workflow.

Model import requires a Comfy Cloud Creator or Pro plan. The FLUX.2 Klein 9B
stack, RealESRGAN, and BiRefNet are present in the Cloud catalog.

The processing workflow does not use the project LoRA, so this import is only
needed for the source, text-to-image, and batch workflows.

## Run a workflow

1. Open the workflow JSON file in Comfy Cloud.
2. For the source, processing, and batch workflows, upload your photos and
   select them in the loaders. Upload one background from
   [`backgrounds/`](../backgrounds/) only if you enable background
   replacement (it is off by default).
3. The upload card already shows the source; compare the prepared result in
   the portrait row below. **Face zoom** defaults to `0.90`; lower values keep
   more of the body. **Preserve
   hat/headwear** defaults to `true`. Turn off **Toggle face processing** to
   keep a full multi-person composition. Adonis Base and Post run before styling.
4. Keep the source prompt exactly as
   `make this portrait hoi4_portrait style` and append only deliberate
   changes. The text-to-image workflow uses the example prompt
   `hoi4_portrait style, an Irish middle-aged man with neatly combed dark
   hair, wearing a plain civilian jacket.`
5. Queue the workflow. A source run returns three candidates; download the
   156×210 output you want and the 1024×1365 master.

The workflows contain no paid partner nodes. Normal Comfy Cloud compute and
subscription limits still apply.

Learn more:

- [Import models into Comfy Cloud](https://docs.comfy.org/cloud/import-models)
- [FLUX.2 Klein workflows and model files](https://docs.comfy.org/tutorials/flux/flux-2-klein)
