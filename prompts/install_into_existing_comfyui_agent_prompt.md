# Coding-agent setup prompt

Copy everything below into a coding agent that has filesystem and terminal
access on the machine where ComfyUI is already installed.

---

Install the HOI4 portrait workflow package into my **existing** ComfyUI
installation. Do not download, clone, replace, upgrade, or expose ComfyUI
itself. Do not configure ComfyUI MCP. Do not add ControlNet.

Package root:

`<ABSOLUTE_PATH_TO_EXTRACTED_HOI4_PORTRAIT_PACKAGE>`

Existing ComfyUI root:

`<ABSOLUTE_PATH_TO_EXISTING_COMFYUI>`

Target profile (choose one after detecting the machine):

- `local_mac_16gb` for a 16 GB Apple Silicon Mac.
- `local_nvidia_16gb` for a local NVIDIA GPU with at least 16 GB VRAM.

Follow these requirements exactly:

1. Read `README.md`, `docs/getting-started.md`,
   `docs/licensing-and-public-repository.md`,
   `dependencies/models.lock.json`, `dependencies/custom_nodes.lock.json`,
   `dependencies/license_review.json`, and `loras/README.md` before changing
   anything.
2. Verify that the supplied ComfyUI root exists, contains `main.py`, and is
   locally controlled by the user. Preserve its existing configuration and
   unrelated custom nodes.
3. Run the package’s hardware, dependency, topology, license, background,
   source, LoRA, and repository preflights. Stop on an unsupported model
   format, checksum mismatch, missing approved background, missing required
   node, license blocker, or unavailable required capability.
4. Create the package-local Python 3.12 environment and install only the
   hash-pinned project/runtime dependencies. Do not replace the existing
   ComfyUI Python environment or its PyTorch build.
5. Authenticate Hugging Face without writing the token into the package,
   workflow, logs, screenshots, or Git. The private style LoRA source is
   pinned in `dependencies/models.lock.json`.
6. Run:

   ```bash
   PYTHONPATH=src .venv/bin/python scripts/install_into_existing_comfyui.py \
     --comfyui-root "<ABSOLUTE_PATH_TO_EXISTING_COMFYUI>" \
     --profile "<local_mac_16gb_OR_local_nvidia_16gb>"
   ```

   On Windows, use `.venv\Scripts\python.exe` and Windows path syntax.
7. The installer must report `"comfyui_downloaded": false`. It may:
   install the exact pinned `comfyui-krea2edit` revision, copy the
   project-owned node pack, download checksum-locked model/preprocessing
   artifacts into the package, add only the marked HOI4 block to
   `extra_model_paths.yaml`, and copy the six UI workflows to
   `user/default/workflows/hoi4_portraits`.
8. Restart existing ComfyUI on loopback only. Verify live node inventory and
   exact signatures for `Krea2EditModelPatch`, `Krea2EditGroundedEncode`, all
   required `HOI4*` nodes, `CLIPLoader(type=krea2)`, loaders, preview nodes,
   and save nodes.
9. Open the correct human workflow and verify that its final `PreviewImage`
   and `SaveImage` consume the same image. Human workflows must contain the
   exact autoprompter instruction; agent workflows must contain no
   autoprompter and must receive the prompt through the job contract.
10. Do not change locked node controls, model filenames, workflow prompts,
    safety gates, or output promotion rules. Do not use face swapping.
11. Krea Edit is the approved image-conditioned identity/geometry route.
    ControlNet remains excluded unless a separate pinned, licensed,
    identity-first experiment proves a measurable benefit.
12. Run `PYTHONPATH=src .venv/bin/python scripts/run_tests.py`, the live Comfy
    compatibility probe, and `PYTHONPATH=src .venv/bin/python
    scripts/run_acceptance.py`. Report every PASS, FAIL, BLOCKED, SKIPPED, and
    UNCERTAIN gate exactly. Do not call a setup-only or schema-only result a
    successful portrait generation.
13. Do not create a final DDS or mod integration output unless the separate
    auditor returns PASS for identity, geometry, expression, accessories,
    masks, style, and provenance.

Return the exact installed paths, revisions, checksums, live node inventory
result, workflow opened, tests run, acceptance exit code, and every unresolved
blocker.

---
