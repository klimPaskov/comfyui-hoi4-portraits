# Workflow guide

## Convert an existing portrait

The source-portrait workflows use these visible stages:

1. Job and source
2. Subject selection
3. Tight head-and-shoulders crop
4. Qwen restoration on full power, or Real-ESRGAN preparation on 16 GB
5. Automatic description, manual description, or agent job-file prompt
6. Krea 2 identity edit
7. HOI4 style LoRA
8. Portrait generation
9. Large previews and save

The background selector defaults to **Keep current background**. Choose **Scientist laboratory** or **Operative background** to use either local game background. Each option has its own preview.

In a human workflow, use **Create automatically** in the portrait-description node or switch it to **Use my description** and type the prompt below it.

Local workflows target 12–16 GB NVIDIA GPUs. The RunPod setup installs the source-photo, no-input, agent, and portrait-preparation workflows.

The local graph includes visible 12 GB and 8 GB GGUF placeholders for users who want to add smaller compatible models.

## Prepare a portrait

Every source-image workflow automatically crops tightly around the face and shoulders. Full-power workflows use Qwen Image Edit 2511 to repair damage, recover natural detail, and colorize monochrome or sepia photos when needed. Real-ESRGAN then performs a final 2× refinement. The 16 GB workflows use Real-ESRGAN alone and preserve the source colors.

`hoi4_portraits_prepare_portrait_for_hoi4` offers the complete Qwen restoration route as a separate utility and stops before Krea and the HOI4 style LoRA. It is the recommended preparation workflow on a full-power GPU.

`hoi4_portraits_prepare_portrait_basic` is the lightweight alternative. It crops, resizes, and applies small contrast and sharpness adjustments without loading an enhancement model.

The default choice keeps the source background. The optional scientist and operative choices use `tools/art/scientists_BG.png` and `tools/art/portrait_operative_background.png` from your installed copy of Hearts of Iron IV. The installer copies them locally when the game is found; the game assets are not included in the download.

The complete preparation workflow has six stages:

1. Choose and preview the photo.
2. Find a face and crop to head and shoulders.
3. Choose automatic color restoration, original-color restoration, or custom instructions.
4. Restore the crop with Qwen Image Edit 2511.
5. Refine and enlarge it with Real-ESRGAN.
6. Preview and save the prepared portrait.

The basic preparation workflow does not load Qwen or Real-ESRGAN. It is useful when the source already has enough detail.

The examples in the main README use a severely faded full-body portrait, a crowded group photograph, and a small newspaper image. Very damaged sources can still retain grain, printing patterns, or uncertain colors after preparation.

## Generate a fictional leader

The no-input workflows do not need an input image. The first node can create a varied prompt from an optional brief and the character controls, or use a complete prompt written by you.

1. Choose random generation or write your own prompt
2. Load Krea 2 Turbo
3. Apply the HOI4 style LoRA
4. Generate the portrait
5. Preview and save

The prompt builder is text-only and runs without a separate language or vision model.

The matching `hoi4_portraits_agent_no_input_local_nvidia_16gb` and `hoi4_portraits_agent_no_input_full_power_gpu` workflows receive the complete prompt from a job file and contain no prompt builder. Start with [`prompt_job_input.example.json`](examples/prompt_job_input.example.json).

## Agent workflows

The agent JSON workflows are included for future automation. ComfyUI Cloud does not currently provide a dependable way to install and run their required custom nodes, so these workflows are not currently practical through Cloud.
