#!/usr/bin/env bash
set -Eeuo pipefail

: "${PORTRAIT_GATEWAY_TOKEN:?PORTRAIT_GATEWAY_TOKEN secret is required}"
: "${PORTRAIT_PROJECT_ROOT:=/workspace/hoi4-portraits/project}"
: "${PORTRAIT_MODEL_ROOT:=/workspace/hoi4-portraits/models}"
: "${PORTRAIT_JOB_ROOT:=/workspace/hoi4-portraits/jobs}"
: "${COMFYUI_HOST:=127.0.0.1}"
: "${COMFYUI_PORT:=8188}"
: "${PORTRAIT_PROFILE:=agent_remote_runpod}"
: "${PORTRAIT_MAX_ACTIVE_JOBS:=1}"
: "${PORTRAIT_MAX_UPLOAD_BYTES:=26214400}"
: "${PORTRAIT_IDLE_SHUTDOWN_MINUTES:=0}"

if [ "$COMFYUI_HOST" != "127.0.0.1" ]; then
  echo "COMFYUI_HOST must remain loopback-only" >&2
  exit 60
fi
if [ "$PORTRAIT_PROFILE" != "agent_remote_runpod" ]; then
  echo "RunPod entrypoint only serves agent_remote_runpod" >&2
  exit 10
fi
if [ "$PORTRAIT_MAX_ACTIVE_JOBS" -lt 1 ] || [ "$PORTRAIT_MAX_ACTIVE_JOBS" -gt 8 ]; then
  echo "PORTRAIT_MAX_ACTIVE_JOBS is outside the bounded range" >&2
  exit 10
fi

mkdir -p "$PORTRAIT_PROJECT_ROOT" "$PORTRAIT_MODEL_ROOT" "$PORTRAIT_JOB_ROOT" \
  /workspace/hoi4-portraits/huggingface-cache /workspace/hoi4-portraits/comfyui-output \
  /workspace/hoi4-portraits/logs /workspace/hoi4-portraits/dependency-locks

if [ ! -f "$PORTRAIT_PROJECT_ROOT/schemas/portrait_job_input.schema.json" ]; then
  if [ -n "$(find "$PORTRAIT_PROJECT_ROOT" -mindepth 1 -maxdepth 1 -print -quit)" ]; then
    echo "persistent project volume is incomplete; refusing an implicit overlay" >&2
    exit 20
  fi
  if [ ! -f "/opt/portrait-project/schemas/portrait_job_input.schema.json" ]; then
    echo "reviewed project payload is missing from the image" >&2
    exit 20
  fi
  cp -a /opt/portrait-project/. "$PORTRAIT_PROJECT_ROOT/"
fi

if [ -e "$PORTRAIT_PROJECT_ROOT/models" ] && [ ! -L "$PORTRAIT_PROJECT_ROOT/models" ]; then
  echo "project models path exists and is not the approved persistent model mount" >&2
  exit 20
fi
if [ ! -e "$PORTRAIT_PROJECT_ROOT/models" ]; then
  ln -s "$PORTRAIT_MODEL_ROOT" "$PORTRAIT_PROJECT_ROOT/models"
fi
if [ -e "$PORTRAIT_PROJECT_ROOT/jobs" ] && [ ! -L "$PORTRAIT_PROJECT_ROOT/jobs" ]; then
  echo "project jobs path exists and is not the approved persistent job mount" >&2
  exit 20
fi
if [ ! -e "$PORTRAIT_PROJECT_ROOT/jobs" ]; then
  ln -s "$PORTRAIT_JOB_ROOT" "$PORTRAIT_PROJECT_ROOT/jobs"
fi

export HF_HOME="/workspace/hoi4-portraits/huggingface-cache"
export HUGGINGFACE_HUB_CACHE="$HF_HOME"
export PYTHONPATH="$PORTRAIT_PROJECT_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"

if ! python3 -c 'import os,sys; from portrait_pipeline.preflight import collect_preflight; report=collect_preflight(os.environ["PORTRAIT_PROJECT_ROOT"], profile=os.environ["PORTRAIT_PROFILE"]); raise SystemExit(0 if report["status"] == "PASS" else 20)'; then
  echo "preflight blocked; no runtime installation or model download will be attempted" >&2
  exit 20
fi

/usr/local/sbin/hoi4-portrait-install-runtime
PYTHON_BIN="/opt/portrait-venv/bin/python"

"$PYTHON_BIN" "$PORTRAIT_PROJECT_ROOT/scripts/bootstrap/bootstrap.py" --profile remote_runpod --restore-from-lock \
  >"/workspace/hoi4-portraits/logs/bootstrap.log" 2>&1

comfy_log="/workspace/hoi4-portraits/logs/comfyui.log"
gateway_log="/workspace/hoi4-portraits/logs/gateway.log"
"$PYTHON_BIN" "$PORTRAIT_PROJECT_ROOT/comfyui/main.py" --listen "$COMFYUI_HOST" --port "$COMFYUI_PORT" >"$comfy_log" 2>&1 &
comfy_pid=$!
gateway_pid=""
cleanup() {
  if [ -n "$gateway_pid" ] && kill -0 "$gateway_pid" 2>/dev/null; then kill "$gateway_pid" 2>/dev/null || true; fi
  if kill -0 "$comfy_pid" 2>/dev/null; then kill "$comfy_pid" 2>/dev/null || true; fi
}
trap cleanup EXIT INT TERM

for _ in $(seq 1 120); do
  if ! kill -0 "$comfy_pid" 2>/dev/null; then
    echo "ComfyUI exited before loopback readiness" >&2
    exit 20
  fi
  if "$PYTHON_BIN" -c 'import json,sys,urllib.request; port=sys.argv[1]; json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/system_stats", timeout=2).read().decode("utf-8"))' "$COMFYUI_PORT" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

"$PYTHON_BIN" -m portrait_pipeline.mcp.gateway --root "$PORTRAIT_PROJECT_ROOT" --host "${PORTRAIT_GATEWAY_HOST:-0.0.0.0}" --port "${PORTRAIT_GATEWAY_PORT:-8765}" >"$gateway_log" 2>&1 &
gateway_pid=$!

for _ in $(seq 1 60); do
  if ! kill -0 "$gateway_pid" 2>/dev/null; then
    echo "project gateway exited before readiness" >&2
    exit 60
  fi
  if "$PYTHON_BIN" /usr/local/sbin/hoi4-portrait-readiness.py >/dev/null 2>&1; then
    touch /workspace/hoi4-portraits/READY
    break
  fi
  sleep 1
done

if [ ! -f /workspace/hoi4-portraits/READY ]; then
  echo "gateway health or inventory did not pass; Pod is not ready" >&2
  exit 20
fi

wait "$gateway_pid"
