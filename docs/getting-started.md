# Getting started

## Requirements

- Current ComfyUI
- NVIDIA GPU with 12–16 GB VRAM for the local profile, or a RunPod GPU
- Python 3.12
- Git
- Optional Hugging Face token to avoid anonymous download rate limits
- Enough disk space for the pinned Krea, encoder, VAE, identity adapter, autoprompter, and style LoRA files

## Automated setup

```powershell
git clone https://github.com/klimPaskov/comfyui-hoi4-portraits.git
cd comfyui-hoi4-portraits
# Optional: $env:HF_TOKEN = "hf_..."
.\scripts\install_windows.ps1 -ComfyUIRoot "C:\path\to\ComfyUI" -Profile local_nvidia_16gb
```

Start ComfyUI with the required loopback sidecars:

```powershell
.\scripts\start_windows.ps1 -ComfyUIRoot "C:\path\to\ComfyUI" -Workflow human_local_nvidia_16gb
```

Open `Workflows`, then select one of the installed `hoi4_portraits` workflows.

## Human workflow

1. Set `job_contract_path` to a contract based on [`job_input.example.json`](examples/job_input.example.json).
2. Confirm the source portrait and approved background previews.
3. Optionally enter a manual prompt override; otherwise the exact built-in autoprompter instruction is used.
4. Queue the workflow.
5. Inspect the final preview beside the Save Image node.
6. Treat the generated image as a candidate until the independent audit passes.

## Agent workflow

The agent workflow reads its prompt only from `portrait_job_input.prompt`. It contains no autoprompter node or instruction.

## Memory presets

The local workflow exposes 16 GB, 12 GB, and 8 GB loader placeholders. Select only a model format proven compatible by the live node/model preflight. Unsupported or missing formats stop the run rather than silently falling back.
