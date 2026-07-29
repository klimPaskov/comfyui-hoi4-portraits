# Workflow guide

## Convert an existing portrait

The source-portrait workflows use these visible stages:

1. Job and source
2. Subject selection
3. Crop and source preparation
4. Color, restoration, mask, and background
5. Human autoprompt or agent job-file prompt
6. Krea 2 identity edit
7. HOI4 style LoRA
8. Portrait generation
9. Large previews and save

The background selector defaults to **Keep current background**. Choose **Scientist laboratory** or **Operative background** to use either local game background. Each option has its own preview.

Local workflows target 12–16 GB NVIDIA GPUs. The RunPod setup includes the source-photo, prompt-only, and portrait-preparation workflows. The agent full-power workflow remains available in the repository for automated jobs.

The local graph includes visible 12 GB and 8 GB GGUF placeholders for users who want to add smaller compatible models.

## Prepare a difficult source photo

Every source-image workflow automatically crops to head and shoulders, uses DDColor for black-and-white photos, and applies light contrast and sharpness before generation.

`prepare_portrait_for_hoi4` offers that preparation as a separate utility and stops before Krea and the HOI4 style LoRA.

The default choice keeps the source background. The optional scientist and operative choices use `tools/art/scientists_BG.png` and `tools/art/portrait_operative_background.png` from your installed copy of Hearts of Iron IV. The installer copies them locally when the game is found; the game assets are not included in the download.

The workflow has four stages:

1. Choose and preview the photo.
2. Find a face and crop to head and shoulders.
3. Colorize black-and-white images and apply light enhancement.
4. Preview and save the prepared portrait.

Color treatment defaults to **Automatic**. Existing color photos keep their original color. Because historical colors are estimated, review uniforms, ribbons, and skin tones before using the image.

## Generate a fictional leader

The prompt workflows do not need an input image. Choose the character controls, enter an optional brief, and change the seed for a new leader.

1. Create a fictional portrait idea
2. Load Krea 2 Turbo
3. Apply the HOI4 style LoRA
4. Generate the portrait
5. Preview and save

The prompt builder is text-only and runs without a separate language or vision model.

The matching `agent_prompt_local_nvidia_16gb` and `agent_prompt_full_power_gpu` workflows receive the complete prompt from a job file and contain no prompt builder. Start with [`prompt_job_input.example.json`](examples/prompt_job_input.example.json).

## Agent workflows

The agent JSON workflows are included for future automation. ComfyUI Cloud does not currently provide a dependable way to install and run their required custom nodes, so these workflows are not currently practical through Cloud.
