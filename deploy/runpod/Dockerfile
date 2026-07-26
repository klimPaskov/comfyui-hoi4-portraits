# syntax=docker/dockerfile:1.7
# This image intentionally fails closed until image_lock.json and the runtime
# profile lock contain resolved versions and hashes.
FROM nvidia/cuda:12.8.1-cudnn-runtime-ubuntu22.04@sha256:59e0e4376a0f16d10b03d3a14344b80a866a1674cb4948cb318291387ac05010

ARG IMAGE_LOCK_STATUS=BLOCKED_UNRESOLVED_RUNTIME_LOCK
ARG SYSTEM_PACKAGES=

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORTRAIT_PROJECT_ROOT=/workspace/hoi4-portraits/project \
    PORTRAIT_MODEL_ROOT=/workspace/hoi4-portraits/models \
    PORTRAIT_JOB_ROOT=/workspace/hoi4-portraits/jobs \
    COMFYUI_HOST=127.0.0.1 \
    COMFYUI_PORT=8188 \
    PORTRAIT_GATEWAY_HOST=0.0.0.0 \
    PORTRAIT_GATEWAY_PORT=8765 \
    PORTRAIT_PROFILE=agent_remote_runpod \
    PORTRAIT_MAX_ACTIVE_JOBS=1

WORKDIR /opt/portrait-project

# Do not let an accidentally unreviewed Docker build install a floating
# Python, apt package, model, or dependency set.
RUN test "$IMAGE_LOCK_STATUS" = "RESOLVED" \
    && test -n "$SYSTEM_PACKAGES" \
    && apt-get update \
    && printf '%s\n' "$SYSTEM_PACKAGES" | xargs apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/* \
    && python3 --version

COPY pyproject.toml checksums.sha256 README.md /opt/portrait-project/
COPY 00_*.md 01_*.md 02_*.md 03_*.md 04_*.md 05_*.md 06_*.md 07_*.md 08_*.md 09_*.md 10_*.md 11_*.md 12_*.md 13_*.md 14_*.md 15_*.md 16_*.md 17_*.md 18_*.md 19_*.md 20_*.md 21_*.md /opt/portrait-project/
COPY config /opt/portrait-project/config
COPY dependencies /opt/portrait-project/dependencies
COPY manifests /opt/portrait-project/manifests
COPY mcp /opt/portrait-project/mcp
COPY prompts /opt/portrait-project/prompts
COPY schemas /opt/portrait-project/schemas
COPY scripts /opt/portrait-project/scripts
COPY src /opt/portrait-project/src
COPY workflows /opt/portrait-project/workflows
COPY deploy/runpod /opt/portrait-project/deploy/runpod

COPY deploy/runpod/install_runtime.sh /usr/local/sbin/hoi4-portrait-install-runtime
COPY deploy/runpod/entrypoint.sh /usr/local/sbin/hoi4-portrait-entrypoint
COPY deploy/runpod/readiness.py /usr/local/sbin/hoi4-portrait-readiness.py
COPY deploy/runpod/healthcheck.sh /usr/local/sbin/hoi4-portrait-healthcheck
RUN chmod 0755 /usr/local/sbin/hoi4-portrait-*

HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 CMD ["/usr/local/sbin/hoi4-portrait-healthcheck"]

ENTRYPOINT ["/usr/local/sbin/hoi4-portrait-entrypoint"]
