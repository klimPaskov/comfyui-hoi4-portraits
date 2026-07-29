# Getting started

## Requirements

- Current ComfyUI
- NVIDIA GPU with 12–16 GB VRAM for the local profile, or a RunPod GPU
- Python 3.12 or the Python environment bundled with ComfyUI
- Git
- Enough disk space for the selected workflow's models; the complete RunPod setup needs roughly 75 GB

## Automated setup

```powershell
git clone https://github.com/klimPaskov/comfyui-hoi4-portraits.git
cd comfyui-hoi4-portraits
.\scripts\install_windows.ps1 -ComfyUIRoot "C:\path\to\ComfyUI" -Profile hoi4_portraits_local_nvidia_16gb
```

Start ComfyUI:

```powershell
.\scripts\start_windows.ps1 -ComfyUIRoot "C:\path\to\ComfyUI" -Workflow hoi4_portraits_local_nvidia_16gb
```

Open `Workflows > hoi4_portraits`, then select `hoi4_portraits_local_nvidia_16gb`.

## Human workflow

1. Create a job file based on [`job_input.example.json`](examples/job_input.example.json).
2. Set the job file path in the first workflow node.
3. Confirm the source portrait and background previews.
4. In the portrait-description node, choose **Create automatically** or **Use my description**.
5. Queue the workflow.
6. Review the final preview beside the Save Image node.

## Agent workflow

Agent workflows read their portrait description from the job file. Use `hoi4_portraits_agent_no_input_local_nvidia_16gb` with [`prompt_job_input.example.json`](examples/prompt_job_input.example.json) to generate a portrait without an input image.

## Prompt workflow

Open `hoi4_portraits_no_input_local_nvidia_16gb` to create a leader without an input image. Leave the first node on **Create a random portrait** and add an optional brief, or choose **Use my prompt**. Change the seed to create another portrait.

## Prepare an old photo

Source-image workflows prepare full-body, group, faded, and black-and-white photos automatically. Open `hoi4_portraits_prepare_portrait_for_hoi4` when you want Qwen restoration and optional colorization without running portrait generation. Use `hoi4_portraits_prepare_portrait_basic` for cropping and simple adjustments without an enhancement model.

1. Choose the image.
2. Set the face number to `0` for the largest detected face, or try `1`, `2`, and so on for another person.
3. Choose normal, wide, or tight framing.
4. Review the tighter crop before continuing.
5. Choose whether Qwen should colorize monochrome sources or preserve the existing color treatment.
6. Review the Qwen restoration, Real-ESRGAN refinement, and final image beside the Save node.

The full-power preparation workflow colorizes monochrome and sepia inputs by default. Switch the restoration node to **Restore without changing color** when you want to preserve black and white.

## Memory presets

The local workflow includes visible 16 GB, 12 GB, and 8 GB model options. The included 16 GB option is the default; the smaller options are placeholders for compatible GGUF models.
