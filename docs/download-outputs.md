# Download RunPod outputs

Generated files are in `/workspace/hoi4-portrait-runpod/output`.

## 1. Direct folder download with SCP

SCP is preferred when SSH access is working because it downloads the folder directly without creating an archive. Find the current public IP and SSH port in the pod's **Connect** menu. Run this command on your local computer in Windows PowerShell, not inside RunPod:

```powershell
scp -r -P <SSH_PORT> -i "$HOME\.ssh\id_ed25519" root@<RUNPOD_IP>:/workspace/hoi4-portrait-runpod/output "$HOME\Downloads\"
```

This creates `C:\Users\<USERNAME>\Downloads\output`. The `-r` option recursively downloads the complete folder. Do not hardcode an IP address or SSH port because RunPod's IPs and port mappings may change after restarting or recreating a pod.

### If SCP asks for a password

This usually means SSH key authentication is not working for the current pod. If JupyterLab access is working, run this in the RunPod terminal to temporarily configure password-based SSH:

```bash
wget https://raw.githubusercontent.com/justinwlin/Runpod-SSH-Password/main/passwordrunpod.sh
chmod +x passwordrunpod.sh
./passwordrunpod.sh
```

Then download from Windows PowerShell without the key argument:

```powershell
scp -r -P <SSH_PORT> root@<RUNPOD_IP>:/workspace/hoi4-portrait-runpod/output "$HOME\Downloads\"
```

Enter the password configured on the pod when prompted. PowerShell does not display password characters while they are typed. Disable temporary password authentication afterward if the pod will remain running.

## 2. Archive the output as `.tar.gz`

This is useful when you prefer downloading one file through JupyterLab. From the RunPod terminal, run:

```bash
cd /workspace/hoi4-portrait-runpod
tar -czf output.tar.gz output
```

This creates `/workspace/hoi4-portrait-runpod/output.tar.gz`. Download it from the JupyterLab file browser. On Windows, extract it with:

```powershell
mkdir "$HOME\Downloads\output_extracted"
tar -xzf "$HOME\Downloads\output.tar.gz" -C "$HOME\Downloads\output_extracted"
```

Verify the archive downloaded completely before deleting the original RunPod output. To check it on Windows, run:

```powershell
tar -tzf "$HOME\Downloads\output.tar.gz"
```

If this reports truncation or an unexpected end-of-file error, the archive download is incomplete; download it again.

## 3. Manual download through JupyterLab

Open the JupyterLab file browser and navigate to `/workspace/hoi4-portrait-runpod/`. Download individual files directly. For a whole directory, create `output.tar.gz` first and download that single archive. If your JupyterLab installation supports direct folder downloads, you can use that option, but it is not available in every environment.

Do not delete `/workspace/hoi4-portrait-runpod/output` immediately after starting a download. First verify that the local folder or archive contains the expected files, and keep the RunPod copy until the transfer is confirmed. Never put real passwords, private SSH keys, IP addresses, or personal credentials into this documentation.
