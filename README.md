# HOI4 Portrait Workflows for ComfyUI

Turn portrait photos into Hearts of Iron IV-style leader portraits with ComfyUI. Full-power source workflows restore and colorize difficult photos with Qwen Image Edit 2511 before Krea 2 Turbo applies the HOI4 style. The 16 GB workflows use Real-ESRGAN preparation to keep memory use lower.

> 🎥 **YouTube tutorial: coming soon.** The video link will be added here.

[Download the latest package](https://github.com/klimPaskov/comfyui-hoi4-portraits/releases). ComfyUI is installed separately; the included setup scripts add the workflows, required nodes, and model files to an existing ComfyUI installation.

## Workflows

| Workflow | Use | Prompt source |
| --- | --- | --- |
| [`hoi4_portraits_local_nvidia_16gb`](workflows/human/local_nvidia_16gb/hoi4_portraits_local_nvidia_16gb.json) | 12–16 GB NVIDIA GPU, Real-ESRGAN preparation | Automatic or manual |
| [`hoi4_portraits_agent_local_nvidia_16gb`](workflows/agent/local_nvidia_16gb/hoi4_portraits_agent_local_nvidia_16gb.json) | 12–16 GB NVIDIA GPU, Real-ESRGAN preparation | Job file |
| [`hoi4_portraits_full_power_gpu`](workflows/human/full_power_gpu/hoi4_portraits_full_power_gpu.json) | RunPod GPU, Qwen restoration | Automatic or manual |
| [`hoi4_portraits_agent_full_power_gpu`](workflows/agent/full_power_gpu/hoi4_portraits_agent_full_power_gpu.json) | RunPod GPU, Qwen restoration | Job file |
| [`hoi4_portraits_no_input_local_nvidia_16gb`](workflows/human/no_input_local_nvidia_16gb/hoi4_portraits_no_input_local_nvidia_16gb.json) | 12–16 GB NVIDIA GPU, no input image | Random builder or manual |
| [`hoi4_portraits_no_input_full_power_gpu`](workflows/human/no_input_full_power_gpu/hoi4_portraits_no_input_full_power_gpu.json) | RunPod GPU, no input image | Random builder or manual |
| [`hoi4_portraits_agent_no_input_local_nvidia_16gb`](workflows/agent/no_input_local_nvidia_16gb/hoi4_portraits_agent_no_input_local_nvidia_16gb.json) | 12–16 GB NVIDIA GPU, no input image | Job file |
| [`hoi4_portraits_agent_no_input_full_power_gpu`](workflows/agent/no_input_full_power_gpu/hoi4_portraits_agent_no_input_full_power_gpu.json) | RunPod GPU, no input image | Job file |

Every source-image workflow automatically finds the subject and crops to a head-and-shoulders portrait. Full-power workflows then use Qwen Image Edit 2511 to repair damage, recover detail, and colorize monochrome or sepia sources when needed; Real-ESRGAN performs the final refinement. The 16 GB workflows use Real-ESRGAN alone. Human workflows include large previews and can switch between automatic and manual descriptions. Agent workflows receive their portrait description from the job JSON.

> Agent workflows are included for future automation. They are not currently practical through ComfyUI Cloud because Cloud does not yet provide a dependable way to install and run the required custom nodes.

## Windows setup

1. Install ComfyUI.
2. Clone this repository.
3. Run the installer from PowerShell:

```powershell
.\scripts\install_windows.ps1 `
  -ComfyUIRoot "C:\path\to\ComfyUI" `
  -Profile hoi4_portraits_local_nvidia_16gb
```

Start the workflow:

```powershell
.\scripts\start_windows.ps1 `
  -ComfyUIRoot "C:\path\to\ComfyUI" `
  -Workflow hoi4_portraits_local_nvidia_16gb
```

The setup script installs the nodes and models in their correct folders and adds the workflows to ComfyUI.

## RunPod setup

Open a terminal in a RunPod ComfyUI template and paste the command below. It installs all included workflows and downloads Qwen Image Edit 2511, Krea 2 Turbo, the encoders, the style LoRA, and the other required files. It does not install or replace ComfyUI.

```bash
bash -lc 'set -e; P=/workspace/comfyui-hoi4-portraits; test -d "$P/.git" || git clone https://github.com/klimPaskov/comfyui-hoi4-portraits.git "$P"; "$P/scripts/install_runpod.sh" /workspace/ComfyUI'
```

Then start ComfyUI:

```bash
/workspace/comfyui-hoi4-portraits/scripts/start_runpod.sh /workspace/ComfyUI
```

Open `Workflows > hoi4_portraits` in ComfyUI to choose any installed workflow.

See the [RunPod guide](docs/runpod.md) for folder locations and SSH access.

## Workflow overview

![Complete human workflow](docs/assets/workflow_hoi4_portraits_local_nvidia_16gb.png)

The first row loads the source, selects the person, crops the portrait, and prepares it automatically:

![Input, crop, and preparation steps](docs/assets/workflow_input_and_preparation.png)

The final row applies the Krea identity reference and HOI4 LoRA, generates the portrait, then shows the same image that will be saved:

![Generation, preview, and save steps](docs/assets/workflow_generation_and_save.png)

### Generate a new leader from a prompt

Enter an optional brief and let the workflow vary the remaining details, or switch the first node to **Use my prompt**. No input image or separate vision autoprompter is used.

Agents can use the matching `hoi4_portraits_agent_no_input_*` workflow with the [no-input job example](docs/examples/prompt_job_input.example.json).

![No-input portrait workflow](docs/assets/workflow_hoi4_portraits_no_input_local_nvidia_16gb.png)

### Prepare a portrait

[`hoi4_portraits_prepare_portrait_for_hoi4`](workflows/human/prepare_portrait/hoi4_portraits_prepare_portrait_for_hoi4.json) is the full-power preparation workflow. It tightly crops the subject, restores and optionally colorizes the photo with Qwen Image Edit 2511, refines it with Real-ESRGAN, and saves an 832 × 1120 PNG. Its first purple node lets you preserve the original color treatment or write custom restoration instructions.

[`hoi4_portraits_prepare_portrait_basic`](workflows/human/prepare_portrait_basic/hoi4_portraits_prepare_portrait_basic.json) is the model-free alternative for cropping, resizing, contrast, and sharpness adjustments.

The examples below show the lighter Real-ESRGAN preparation used in the 16 GB source workflow:

| Difficult source | Prepared portrait |
| --- | --- |
| ![Severely faded seated portrait](docs/assets/examples/preparation_01_before.jpg) | ![Prepared faded portrait](docs/assets/examples/preparation_01_after.png) |
| ![Crowded historical group photograph](docs/assets/examples/preparation_02_before.jpg) | ![Prepared subject from group photograph](docs/assets/examples/preparation_02_after.png) |
| ![Small damaged newspaper portrait](docs/assets/examples/preparation_03_before.jpg) | ![Prepared newspaper portrait](docs/assets/examples/preparation_03_after.png) |

## Portrait examples

| Before | After |
| --- | --- |
| ![Portrait source example 1](docs/assets/examples/inference_01_before.jpg) | ![HOI4 portrait example 1](docs/assets/examples/inference_01_after.png) |
| ![Portrait source example 2](docs/assets/examples/inference_02_before.jpg) | ![HOI4 portrait example 2](docs/assets/examples/inference_02_after.png) |
| ![Portrait source example 3](docs/assets/examples/inference_03_before.jpg) | ![HOI4 portrait example 3](docs/assets/examples/inference_03_after.png) |

## Guides

- [Getting started](docs/getting-started.md)
- [RunPod setup](docs/runpod.md)
- [Workflow guide](docs/workflows.md)
- [Install with a coding agent](docs/setup-with-coding-agent.md)

## License

Project code is MIT licensed. ComfyUI, Krea, Qwen, and model files keep their own licenses. The style LoRA is downloaded from its [Hugging Face page](https://huggingface.co/Hoops-McCann/hoi4-portrait-new-style-lora).
