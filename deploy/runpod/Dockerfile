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
    PORTRAIT_PREPROCESSING_PORT=8790 \
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

COPY . /opt/portrait-project/

COPY deploy/runpod/install_runtime.sh /usr/local/sbin/hoi4-portrait-install-runtime
COPY deploy/runpod/entrypoint.sh /usr/local/sbin/hoi4-portrait-entrypoint
COPY deploy/runpod/readiness.py /usr/local/sbin/hoi4-portrait-readiness.py
COPY deploy/runpod/healthcheck.sh /usr/local/sbin/hoi4-portrait-healthcheck
RUN chmod 0755 /usr/local/sbin/hoi4-portrait-*

HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 CMD ["/usr/local/sbin/hoi4-portrait-healthcheck"]

ENTRYPOINT ["/usr/local/sbin/hoi4-portrait-entrypoint"]
