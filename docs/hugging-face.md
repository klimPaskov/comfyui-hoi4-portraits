# Hugging Face model access

The installer downloads the gated distilled FLUX.2 Klein 9B checkpoint (full or FP8) from Hugging Face. The GGUF variant is not gated. Complete these steps once for the Hugging Face account whose token will be used by the installer.

## 1. Accept the FLUX.2 agreement

1. Sign in to Hugging Face.
2. Open [black-forest-labs/FLUX.2-klein-9B](https://huggingface.co/black-forest-labs/FLUX.2-klein-9B).
3. Review and accept the model agreement on that page.

If you install the FP8 variant, also accept [black-forest-labs/FLUX.2-klein-9b-fp8](https://huggingface.co/black-forest-labs/FLUX.2-klein-9b-fp8).

The installer cannot download the checkpoint until the account has access. Review the model page and its license before using the weights.

## 2. Create a read-only token

1. Open [Create a new read token](https://huggingface.co/settings/tokens/new?tokenType=read).
2. Give the token a clear name, such as `comfyui-hoi4`.
3. Keep the role set to **Read**, then create and copy the token.

A write token is not required. Treat the token like a password: do not place it inside a workflow, commit it to Git, include it in screenshots, or share it.

## 3. Use the token locally

Authenticate with the Hugging Face CLI:

```bash
hf auth login
```

Paste the read-only token when prompted. Alternatively, supply it only to the shell running the installer:

```bash
export HF_TOKEN="hf_..."
python -m pip install -r scripts/requirements-download.txt
python scripts/download_models.py --comfyui-root /path/to/ComfyUI --variant fp8
```

## 4. Use the token on RunPod

Add `HF_TOKEN` to the pod environment or export it in a Jupyter terminal before running the installation command:

```bash
export HF_TOKEN="hf_..."
```

The installer reads the token from the process environment. It does not save the token in this repository or in a workflow.

If the model download returns `401` or `403`, confirm that the token belongs to the same account that accepted the FLUX.2 Klein agreement and that the token still has read access.
