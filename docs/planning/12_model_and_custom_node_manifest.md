# Model and Custom-Node Manifest

## Lock files

Implementation creates:

- `dependencies/dependencies.lock.json`
- `dependencies/models.lock.json`
- `dependencies/custom_nodes.lock.json`
- `dependencies/licenses/<dependency>/`

The templates in `manifests/` define required fields. Locks are generated evidence, reviewed, then committed when their licenses permit metadata distribution. Model weights remain outside Git.

## Required model entries

### Krea 2 Turbo

Record the selected official Comfy-Org or Krea repository, immutable revision, exact filename, dtype, size, SHA-256, loader node, license, and profile use.

Reference candidates observed during planning:

- `krea2_turbo_fp8_scaled.safetensors`
- `krea2_turbo_bf16.safetensors`
- official INT8 convrot variant
- official MXFP8 variant
- official NVFP4 variant

Only the exact files found in the pinned official repository can enter the lock.

### Krea text encoder and VAE

Reference filenames:

- `qwen3vl_4b_fp8_scaled.safetensors`
- `qwen_image_vae.safetensors`

Record loader type `krea2` for the encoder where required by the live node.

### Krea 2 identity edit

Reference candidates:

- `krea2_identity_edit_v1_2.safetensors`
- `krea2_identity_edit_v1_2_r128.safetensors`
- `krea2_identity_edit_v1_2_r64.safetensors`

Planning observed the full v1.2 file at 1.83 GB with SHA-256 `6adf9a69cc9502d286db7b69964d37da7e9cfe4b05b4d004bc275f087d3fd3cf`. Reverify against the pinned Hugging Face revision before use.

### User HOI4 style LoRA

Path:

`loras/hoi4_portrait_new_style_lora.safetensors`

The bootstrap records its checksum and metadata without moving, rewriting, or optimizing the original. It may create a separate read-only symlink or registered model path. A derived copy requires a new filename, lineage, and explicit reason.

### Autoprompter

Local:

- Qwen3-VL-4B-Instruct official GGUF Q4_K_M
- matching official vision `mmproj`

Full power:

- Qwen3-VL-8B-Instruct official source
- optional 32B qualification candidate

### Preprocessing and audit

Resolve and pin exact versions for:

- BiRefNet
- DDColor
- Real-ESRGAN when accepted
- YuNet face detector
- SFace recognition model
- MediaPipe Face Landmarker task asset
- optional mask refinement model
- style-audit model or rubric dependency

## Required custom-node entries

### ComfyUI Core

Record commit, frontend version, and the complete node inventory hash.

### `comfyui-krea2edit`

Record:

- repository
- exact commit
- package version
- Apache-2.0 node-code license
- imported node classes
- node input schema hash
- regression test result
- Krea 2 compatibility result

### Project node pack

Record the local package version and commit. It is part of the standalone project and has no network download behavior.

### Manager

Record whether Manager is embedded in the ComfyUI distribution or separately installed. Record version, registry snapshot, and security configuration.

## License rule

The Krea base and identity adapter use the Krea 2 Community License. Store the license text and a machine-readable review stating:

- permitted local and mod-development use
- redistribution restrictions for weights and derivatives
- commercial threshold and enterprise implications where applicable
- moderation and disclosure obligations
- whether a public RunPod endpoint is allowed under the intended use

Do not summarize a license from memory. Keep the retrieved license file and review date.

## Bootstrap command

The final project exposes one command such as:

```bash
./scripts/bootstrap/bootstrap.sh --profile local_mac_16gb --restore-from-lock
```

The command name can change before release. Its contract cannot. It must restore the environment from locks, verify checksums, install pinned dependencies, enable Manager, validate models and workflows, and produce a capability report without manual file movement.
