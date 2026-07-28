# Mac preflight

The detected machine is an Apple Silicon Mac with 16 GiB unified memory:
macOS 26.5.2, arm64, 10 CPU cores, PyTorch 2.11.0, and MPS available.

The loopback services and pinned artifacts are installed and checksum-verified.
Raw ComfyUI remains bound to `127.0.0.1`; the user-facing server is on port
8188 and the isolated CPU qualification server is on port 8189.

The hardware capability gate passes, but the locked Krea 2 FP8 production graph
does not pass live MPS generation. The official NVFP4 artifact also fails the
Apple-MPS dequantization path. A CPU-only NVFP4 route is available for private
diagnostic execution, but its heavy swap behavior and missing calibrated audit
thresholds prevent production acceptance.

See [local Krea capability](local_krea_infeasible.md) and the [acceptance
report](../acceptance/acceptance_report.md) for the measured failures and
fail-closed promotion policy.
