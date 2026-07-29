# RunPod setup

Use a private Pod with persistent storage and an existing current ComfyUI installation. The scripts never download or replace ComfyUI.

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
| Project custom nodes | `<ComfyUI>/custom_nodes/hoi4_portrait_nodes/` |
| Krea Edit custom nodes | `<ComfyUI>/custom_nodes/comfyui-krea2edit/` |
| Human full-power workflow | `<ComfyUI>/user/default/workflows/hoi4_portraits/human_full_power_gpu.json` |

Every external artifact is revision-pinned and checksum-verified. `extra_model_paths.yaml` is updated with a marked HOI4 block, so no manual file movement or model-folder navigation is needed.

## Expanded commands

The one-liner performs these steps:

```bash
git clone https://github.com/klimPaskov/comfyui-hoi4-portraits.git \
  /workspace/comfyui-hoi4-portraits

/workspace/comfyui-hoi4-portraits/scripts/install_runpod.sh \
  /workspace/ComfyUI
```

An `HF_TOKEN` is optional for the public model sources, but may help with Hugging Face rate limits:

```bash
export HF_TOKEN="hf_..."
```

## Start ComfyUI and the sidecars

```bash
/workspace/comfyui-hoi4-portraits/scripts/start_runpod.sh \
  /workspace/ComfyUI
```

The start script launches preprocessing and the full-power human autoprompter, then binds ComfyUI to `127.0.0.1:8188`. The RunPod installer copies no agent or local workflow into the RunPod workflow menu.

## Open the interface securely

Use RunPod SSH credentials to create an authenticated tunnel:

```bash
ssh -L 8188:127.0.0.1:8188 -p <SSH_PORT> root@<POD_HOST>
```

Then open `http://127.0.0.1:8188` in your browser and choose `human_full_power_gpu` from the installed `hoi4_portraits` folder. Do not expose port 8188 directly to the internet.

## Re-running setup

Re-running the installer is safe when installed files match their locks. It stops instead of overwriting a different custom-node tree, workflow, model, LoRA, or marked model-path block.
