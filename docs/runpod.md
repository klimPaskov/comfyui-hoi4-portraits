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

The installer downloads the Krea model set and registers every model folder automatically. No manual model movement is needed. Allow roughly 45 GB of free persistent storage for the complete setup.

Qwen Image Edit is available as an optional separate preparation workflow. It is not downloaded during the standard setup:

```bash
/workspace/comfyui-hoi4-portraits/scripts/install_runpod_qwen.sh \
  /workspace/ComfyUI
```

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

- `hoi4_portraits_full_power_gpu` restores an input with Krea Edit, then reuses Krea to convert it into an HOI4 portrait.
- `hoi4_portraits_no_input_full_power_gpu` creates a new fictional leader from text controls.
- `hoi4_portraits_prepare_portrait_for_hoi4` crops, restores, and colorizes when needed with Krea Edit.
- `hoi4_portraits_prepare_portrait_basic` crops and adjusts a photo without loading the enhancement model.

After installing the optional Qwen package, `hoi4_portraits_prepare_portrait_qwen` provides the larger Qwen restoration route.

Matching agent workflows are included for future automation, but they currently have no practical use because ComfyUI does not yet provide a reliable MCP connection for running them.
