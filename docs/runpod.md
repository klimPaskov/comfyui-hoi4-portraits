# RunPod setup

Use a private Pod with persistent storage and a ComfyUI template.

## Fast path

Open the RunPod terminal and paste this single command:

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
| Black-and-white color model | `custom_nodes/ComfyUI-DDColor/checkpoints/` |
| Project custom nodes | `<ComfyUI>/custom_nodes/hoi4_portrait_nodes/` |
| Krea Edit custom nodes | `<ComfyUI>/custom_nodes/comfyui-krea2edit/` |
| Full-power workflows | `<ComfyUI>/user/default/workflows/hoi4_portraits/` |

The installer registers these folders automatically, so no manual model movement is needed.

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

The start script launches ComfyUI and the services used by the source-portrait workflow.

For the prompt-only workflow:

```bash
/workspace/comfyui-hoi4-portraits/scripts/start_runpod.sh \
  /workspace/ComfyUI prompt_full_power_gpu
```

For an agent prompt-only job:

```bash
/workspace/comfyui-hoi4-portraits/scripts/start_runpod.sh \
  /workspace/ComfyUI agent_prompt_full_power_gpu
```

For the portrait preparation workflow:

```bash
/workspace/comfyui-hoi4-portraits/scripts/start_runpod.sh \
  /workspace/ComfyUI prepare_portrait_for_hoi4
```

## Open the interface securely

Use RunPod SSH credentials to create an authenticated tunnel:

```bash
ssh -L 8188:127.0.0.1:8188 -p <SSH_PORT> root@<POD_HOST>
```

Then open `http://127.0.0.1:8188` in your browser and choose a workflow from the installed `hoi4_portraits` folder:

- `full_power_gpu` converts an input portrait.
- `agent_full_power_gpu` converts an input portrait from a job file.
- `prompt_full_power_gpu` creates a new fictional leader from text controls.
- `agent_prompt_full_power_gpu` creates a new leader from a prompt-only job file.
- `prepare_portrait_for_hoi4` crops, colorizes, and prepares an old photo.
