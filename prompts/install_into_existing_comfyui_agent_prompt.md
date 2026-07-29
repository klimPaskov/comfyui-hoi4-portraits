# Coding-agent installation prompt

Install this repository into the existing ComfyUI checkout supplied by the user.

Do not download, clone, replace, upgrade, or expose ComfyUI itself.

1. Read `README.md`, `docs/getting-started.md`, the selected workflow, all schemas, dependency locks, and `manifests/workflow_manifest.json`.
2. Detect the target NVIDIA GPU, VRAM, Python version, free disk, ComfyUI revision, installed node classes, and model inventory.
3. Select `local_nvidia_16gb` for a 12–16 GB GPU or `full_power_gpu` for RunPod.
4. Stop on a missing node, unsupported model format, unavailable approved background, checksum mismatch, license blocker, insufficient VRAM, or missing authentication.
5. Set `HF_TOKEN` without printing it.
6. Run:

   ```text
   python scripts/install_into_existing_comfyui.py --comfyui-root "<COMFYUI_ROOT>" --profile "<PROFILE>"
   ```

7. Verify the pinned Krea Edit revision, project node pack, model checksums, immutable style LoRA checksum, extra model paths, and all four installed workflow files.
8. Start preprocessing and autoprompter sidecars on loopback for human workflows.
9. Keep raw ComfyUI on loopback. For RunPod, expose only the authenticated project gateway.
10. Run the unit suite and live ComfyUI compatibility probe.
11. Report every failed, skipped, uncertain, or blocked gate. Do not create final DDS or mod wiring without a separate independent-auditor PASS.
