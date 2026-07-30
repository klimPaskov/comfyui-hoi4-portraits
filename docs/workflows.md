# Workflow guide

## Convert an existing portrait

The source-portrait workflows use these visible stages:

1. Job and source
2. Subject selection
3. Tight head-and-shoulders crop
4. Krea restoration on full power, or Real-ESRGAN preparation on 16 GB
5. Automatic description, manual description, or agent job-file prompt
6. Krea 2 identity edit
7. HOI4 style LoRA
8. Portrait generation
9. Large previews and save

The background selector defaults to **Keep current background**. Choose one of:

- **Scientist laboratory**
- **Operative background**
- **Leader**

All three options are loaded from local `backgrounds/*` assets and each has a dedicated preview node in the workflow.

In a human workflow, use **Create automatically** in the portrait-description node or switch it to **Use my description** and type the prompt below it.

Local workflows target 12–16 GB NVIDIA GPUs. The RunPod setup installs the source-photo, no-input, agent, and portrait-preparation workflows.

The local graph includes visible 12 GB and 8 GB GGUF placeholders for users who want to add smaller compatible models.

## Prepare a portrait

Every source-image workflow automatically crops around the face and shoulders while reserving space above the detected face for hair and headwear. Full-power workflows use Krea Edit to repair damage, recover natural detail, and colorize monochrome or sepia photos when needed, then reuse the same Krea model for HOI4 styling. The 16 GB workflows use Real-ESRGAN preparation and preserve the source colors.

`hoi4_portraits_prepare_portrait_for_hoi4` offers the Krea restoration route as a separate utility and stops before the HOI4 style LoRA. It is the recommended preparation workflow on a full-power GPU.

`hoi4_portraits_prepare_portrait_basic` is the lightweight alternative. It crops, resizes, and applies small contrast and sharpness adjustments without loading an enhancement model.

The default choice keeps the source background. The optional scientist, operative, and leader options use packaged assets from `backgrounds/*`, so no copy from an existing Hearts of Iron IV install is required.

The complete preparation workflow has five stages:

1. Choose and preview the photo.
2. Find a face and crop to head and shoulders.
3. Choose automatic color restoration, original-color restoration, or custom instructions.
4. Restore and enlarge the crop with Krea Edit.
5. Preview and save the prepared portrait.

The basic preparation workflow does not load Krea, Qwen, or Real-ESRGAN. It is useful when the source already has enough detail. The optional `hoi4_portraits_prepare_portrait_qwen` workflow can be added with the separate command in the [RunPod guide](runpod.md).

The examples in the main README use a severely faded full-body portrait, a crowded group photograph, and a small newspaper image. Very damaged sources can still retain grain, printing patterns, or uncertain colors after preparation.

## Generate a fictional leader

The no-input workflows do not need an input image. The first node can create a varied prompt from an optional brief and the character controls, or use a complete prompt written by you.

1. Choose random generation or write your own prompt
2. Load Krea 2 Turbo
3. Apply the HOI4 style LoRA
4. Generate the portrait
5. Preview and save

The prompt builder is text-only and runs without a separate language or vision model.

## Agent workflows

Matching agent workflows are included for every workflow type, but they currently have no practical use because ComfyUI does not yet provide a reliable MCP connection for running them.
