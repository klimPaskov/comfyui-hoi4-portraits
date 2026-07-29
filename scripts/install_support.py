from __future__ import annotations

import os
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from portrait_pipeline.constants import ExitCode
from portrait_pipeline.util import relative_safe_path, sha256_file

ROOT = Path(__file__).resolve().parents[1]


class InstallError(RuntimeError):
    def __init__(self, code: ExitCode, message: str):
        super().__init__(message)
        self.code = code


def _artifact_url(entry: dict[str, Any], filename: str) -> str:
    source_url = str(entry.get("source_url", ""))
    if "/tree/" in source_url:
        source_path = str(entry.get("source_relative_path", filename))
        source_url = source_url.replace("/tree/", "/resolve/", 1).rstrip("/") + "/" + urllib.parse.quote(source_path, safe="/")
    return source_url


def _huggingface_token() -> str | None:
    token = os.environ.get("HF_TOKEN")
    if token:
        return token.strip() or None
    token_path_value = os.environ.get("HF_TOKEN_PATH")
    token_path = Path(token_path_value).expanduser() if token_path_value else Path.home() / ".cache" / "huggingface" / "token"
    try:
        return token_path.read_text(encoding="utf-8").strip() or None
    except OSError:
        return None


def _download_verified(
    url: str,
    destination: Path,
    expected_size: int | None,
    expected_sha256: str,
    actions: list[dict[str, Any]],
) -> None:
    def display_path(path: Path) -> str:
        try:
            return str(path.resolve().relative_to(ROOT.resolve()))
        except ValueError:
            return str(path)

    if destination.is_file():
        if destination.stat().st_size == expected_size and sha256_file(destination) == expected_sha256:
            actions.append({"action": "download_available", "path": display_path(destination)})
            return
        raise InstallError(ExitCode.MODEL_CHECKSUM_MISMATCH, f"downloaded file does not match: {display_path(destination)}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    token = _huggingface_token() if urllib.parse.urlparse(url).hostname == "huggingface.co" else None
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"} if token else {})
    temporary: Path | None = None
    try:
        with urllib.request.urlopen(request, timeout=120) as response, tempfile.NamedTemporaryFile(
            "wb", dir=destination.parent, prefix=f".{destination.name}.", suffix=".download", delete=False
        ) as handle:
            temporary = Path(handle.name)
            size = 0
            while chunk := response.read(1024 * 1024):
                handle.write(chunk)
                size += len(chunk)
        if (expected_size is not None and size != expected_size) or sha256_file(temporary) != expected_sha256:
            raise InstallError(ExitCode.MODEL_CHECKSUM_MISMATCH, f"downloaded file does not match: {display_path(destination)}")
        os.replace(temporary, destination)
        temporary = None
        actions.append({"action": "download_complete", "path": display_path(destination)})
    except urllib.error.HTTPError as exc:
        raise InstallError(ExitCode.DEPENDENCY_MISSING, f"download returned HTTP {exc.code}") from exc
    except (OSError, urllib.error.URLError) as exc:
        raise InstallError(ExitCode.DEPENDENCY_MISSING, "download was unavailable") from exc
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def _restore_project_owned_files(model_lock: dict[str, Any], actions: list[dict[str, Any]]) -> None:
    for entry in model_lock.get("project_owned_immutable_files", []):
        path_value = entry.get("path")
        if not isinstance(path_value, str):
            raise InstallError(ExitCode.DEPENDENCY_MISSING, "style LoRA download information is incomplete")
        destination = relative_safe_path(ROOT, path_value)
        _download_verified(
            str(entry.get("source_url", "")),
            destination,
            int(entry.get("size_bytes")),
            str(entry.get("sha256", "")),
            actions,
        )


def _restore_models(
    model_lock: dict[str, Any],
    profile: str,
    actions: list[dict[str, Any]],
    workflow_ids: set[str] | None = None,
) -> None:
    workflow_profiles = workflow_ids or {
        "local_nvidia_16gb": {
            "human_local_nvidia_16gb",
            "agent_local_nvidia_16gb",
            "human_prompt_local_nvidia_16gb",
        },
        "full_power_gpu": {
            "human_full_power_gpu",
            "agent_full_power_gpu",
            "human_prompt_full_power_gpu",
        },
    }[profile]
    for entry in model_lock.get("models", []):
        if not entry.get("mandatory") or not workflow_profiles.intersection(entry.get("profiles", [])):
            continue
        destination_root = ROOT / str(entry.get("destination_folder", "models"))
        shard_hashes = entry.get("shard_sha256")
        if isinstance(shard_hashes, dict):
            shard_sizes = entry.get("shard_size_bytes", {})
            for filename, expected_sha in sorted(shard_hashes.items()):
                _download_verified(_artifact_url(entry, filename), destination_root / filename, shard_sizes.get(filename), str(expected_sha), actions)
        else:
            filename = str(entry.get("filename", ""))
            _download_verified(_artifact_url(entry, filename), destination_root / filename, entry.get("size_bytes"), str(entry.get("sha256", "")), actions)
        for runtime_file in entry.get("runtime_files", []):
            filename = str(runtime_file.get("filename", ""))
            _download_verified(
                _artifact_url(runtime_file, filename),
                destination_root / filename,
                runtime_file.get("size_bytes"),
                str(runtime_file.get("sha256", "")),
                actions,
            )


def _restore_preprocessing_models(lock: dict[str, Any], actions: list[dict[str, Any]]) -> None:
    for entry in lock.get("dependencies", []):
        if not entry.get("mandatory"):
            continue
        _download_verified(
            str(entry.get("artifact_url", "")),
            relative_safe_path(ROOT, str(entry.get("destination_path", ""))),
            entry.get("artifact_size_bytes"),
            str(entry.get("artifact_sha256", "")),
            actions,
        )


def _restore_preprocessing_source_artifacts(lock: dict[str, Any], actions: list[dict[str, Any]]) -> None:
    for entry in lock.get("dependencies", []):
        source_artifacts = entry.get("source_artifacts", {})
        if not entry.get("mandatory") or not source_artifacts.get("runtime_required"):
            continue
        for source_file in source_artifacts.get("files", []):
            _download_verified(
                str(source_file.get("artifact_url", "")),
                relative_safe_path(ROOT, str(source_file.get("destination_path", ""))),
                source_file.get("size_bytes"),
                str(source_file.get("sha256", "")),
                actions,
            )
