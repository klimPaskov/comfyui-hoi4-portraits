# RunPod setup

Use a private Pod with persistent storage and a ComfyUI template.

## Fast path

Start a Pod that already includes ComfyUI, then paste this single command. The command does not install or replace ComfyUI.

```bash
bash -lc 'set -e; P=/workspace/comfyui-hoi4-portraits; test -d "$P/.git" || git clone https://github.com/klimPaskov/comfyui-hoi4-portraits.git "$P"; "$P/scripts/install_runpod.sh" /workspace/ComfyUI'
```

If your template stores ComfyUI elsewhere, replace `/workspace/ComfyUI` with the directory containing `main.py`. The installer also detects `/workspace/ComfyUI/comfyui`, `/comfyui`, and `/opt/ComfyUI` when no path is supplied.

## What the command installs

| Asset | Installed folder |
| --- | --- |
| Qwen Image Edit 2511 FP8-mixed model | `models/diffusion_models/` |
| Qwen 2.5-VL image encoder | `models/text_encoders/` |
| Krea 2 Turbo diffusion model | `models/diffusion_models/` |
| Krea text/vision encoder | `models/text_encoders/` |
| Krea VAE | `models/vae/` |
| Krea identity adapter | `models/loras/` |
| HOI4 style LoRA | `loras/` |
| Full-power human autoprompter | `models/autoprompter/` |
| Face, mask, and restoration models | `models/preprocessing/` |
| Real-ESRGAN portrait enhancer | `models/upscale_models/` |
| Project custom nodes | `<ComfyUI>/custom_nodes/hoi4_portrait_nodes/` |
| Krea Edit custom nodes | `<ComfyUI>/custom_nodes/comfyui-krea2edit/` |
| All included workflows | `<ComfyUI>/user/default/workflows/hoi4_portraits/` |

The installer downloads the Qwen restoration and Krea portrait-generation model sets, then registers their folders automatically. No manual model movement is needed. Allow roughly 75 GB of free persistent storage for the complete setup.

## Expanded commands

The one-liner performs these steps:

```bash
git clone https://github.com/klimPaskov/comfyui-hoi4-portraits.git \
  /workspace/comfyui-hoi4-portraits

/workspace/comfyui-hoi4-portraits/scripts/install_runpod.sh \
  /workspace/ComfyUI
```

An `HF_TOKEN` is optional for the public model sources, but may help with Hugging Face rate limits. Add it through the Pod's environment-variable settings before running the installer.

## Start ComfyUI

```bash
/workspace/comfyui-hoi4-portraits/scripts/start_runpod.sh \
  /workspace/ComfyUI
```

The start script launches ComfyUI and the services used by the source-portrait workflow. Open `Workflows > hoi4_portraits` to choose any workflow installed by the setup command.

## Open the interface securely

Use RunPod SSH credentials to create an authenticated tunnel:

```bash
ssh -L 8188:127.0.0.1:8188 -p <SSH_PORT> root@<POD_HOST>
```

Then open `http://127.0.0.1:8188` in your browser and choose a workflow from the installed `hoi4_portraits` folder:

- `hoi4_portraits_full_power_gpu` restores an input with Qwen, then converts it into an HOI4 portrait.
- `hoi4_portraits_agent_full_power_gpu` runs the same source-image route from a job file.
- `hoi4_portraits_no_input_full_power_gpu` creates a new fictional leader from text controls.
- `hoi4_portraits_agent_no_input_full_power_gpu` creates a new leader from a no-input job file.
- `hoi4_portraits_prepare_portrait_for_hoi4` crops, restores, colorizes when needed, and refines a photo with Qwen and Real-ESRGAN.
- `hoi4_portraits_prepare_portrait_basic` crops and adjusts a photo without loading the enhancement model.
