# Coding-agent installation prompt

Install this repository into the existing ComfyUI checkout supplied by the user.

Do not replace or reinstall ComfyUI.

1. Find the existing ComfyUI folder and its Python environment.
2. Use `hoi4_portraits_local_nvidia_16gb` for a Windows PC with a 12–16 GB NVIDIA GPU.
3. Use `hoi4_portraits_full_power_gpu` for RunPod.
4. On Windows, run:

   ```text
   powershell -ExecutionPolicy Bypass -File scripts/install_windows.ps1 -ComfyUIRoot "<COMFYUI_ROOT>" -Profile hoi4_portraits_local_nvidia_16gb
   ```

5. On RunPod, run:

   ```text
   bash scripts/install_runpod.sh "<COMFYUI_ROOT>"
   ```

6. Start the matching script in `scripts/`.
7. Tell the user where the workflow was installed and how to open it.
