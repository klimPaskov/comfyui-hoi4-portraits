# Getting started

## Requirements

- Current ComfyUI
- NVIDIA GPU with 12–16 GB VRAM for the local profile, or a RunPod GPU
- Python 3.12 or the Python environment bundled with ComfyUI
- Git
- Enough disk space for the Krea model, encoder, VAE, identity adapter, autoprompter, and style LoRA

## Automated setup

```powershell
git clone https://github.com/klimPaskov/comfyui-hoi4-portraits.git
cd comfyui-hoi4-portraits
.\scripts\install_windows.ps1 -ComfyUIRoot "C:\path\to\ComfyUI" -Profile local_nvidia_16gb
```

Start ComfyUI:

```powershell
.\scripts\start_windows.ps1 -ComfyUIRoot "C:\path\to\ComfyUI" -Workflow local_nvidia_16gb
```

Open `Workflows > hoi4_portraits`, then select `local_nvidia_16gb`.

## Human workflow

1. Create a job file based on [`job_input.example.json`](examples/job_input.example.json).
2. Set the job file path in the first workflow node.
3. Confirm the source portrait and background previews.
4. Enter a manual prompt or use the built-in autoprompter.
5. Queue the workflow.
6. Review the final preview beside the Save Image node.

## Agent workflow

Agent workflows read their portrait description from the job file. Use `agent_prompt_local_nvidia_16gb` with [`prompt_job_input.example.json`](examples/prompt_job_input.example.json) to generate a portrait without an input image.

## Prompt workflow

Open `prompt_local_nvidia_16gb` to create a fictional leader without an input image. Choose the portrait controls, add an optional character brief, and queue the workflow. Change the seed to create another portrait.

## Prepare an old photo

Source-image workflows prepare full-body, group, faded, and black-and-white photos automatically. Open `prepare_portrait_for_hoi4` only when you want the prepared PNG without running portrait generation.

1. Choose the image.
2. Set the face number to `0` for the largest detected face, or try `1`, `2`, and so on for another person.
3. Choose normal, wide, or tight framing.
4. Leave color treatment on **Automatic** to colorize black-and-white photos and keep existing color photos unchanged.
5. Review the prepared portrait beside the Save node.

## Memory presets

The local workflow includes visible 16 GB, 12 GB, and 8 GB model options. The included 16 GB option is the default; the smaller options are placeholders for compatible GGUF models.
