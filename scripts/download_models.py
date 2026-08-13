#!/usr/bin/env python3
"""Download and integrity-verify the models used by the workflows."""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RETRY_DELAYS_SECONDS = (15, 30, 60, 120, 120, 120)
XET_RETRY_DELAYS_SECONDS = (2, 5, 10)
XET_MIN_SIZE_BYTES = 64 * 1024 * 1024

# Hugging Face reads these variables when the client is imported. High-performance
# Xet saturates available network, CPU, and SSD/NVMe bandwidth.
os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "120")
os.environ.setdefault("HF_XET_HIGH_PERFORMANCE", "1")

_XET_SESSION: Any | None = None
_XET_SESSION_LOCK = threading.Lock()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _hf_token() -> str | None:
    token = os.environ.get("HF_TOKEN", "").strip()
    if token:
        return token
    hf_home = Path(os.environ.get("HF_HOME", Path.home() / ".cache" / "huggingface"))
    try:
        return (hf_home / "token").read_text(encoding="utf-8").strip() or None
    except OSError:
        return None


def _verify(path: Path, entry: dict[str, Any]) -> bool:
    return (
        path.is_file()
        and path.stat().st_size == int(entry["size_bytes"])
        and _sha256(path) == entry["sha256"]
    )


def _download_from_hub(entry: dict[str, Any], destination: Path, token: str | None) -> Path | None:
    try:
        from huggingface_hub import hf_hub_download
    except ImportError:
        return None
    marker = f"/resolve/{entry['revision']}/"
    remote_filename = entry["url"].split(marker, 1)[1]
    try:
        return Path(
            hf_hub_download(
                repo_id=entry["source"],
                filename=remote_filename,
                revision=entry["revision"],
                token=token,
                local_dir=destination.parent,
            )
        )
    except Exception as exc:
        raise RuntimeError(f"accelerated Xet download failed for {entry['filename']}: {exc}") from exc


def _remote_filename(entry: dict[str, Any]) -> str:
    marker = f"/resolve/{entry['revision']}/"
    try:
        return urllib.parse.unquote(entry["url"].split(marker, 1)[1])
    except IndexError as exc:
        raise RuntimeError(f"invalid Hugging Face URL for {entry['filename']}") from exc


def _xet_session() -> Any:
    global _XET_SESSION
    with _XET_SESSION_LOCK:
        if _XET_SESSION is None:
            try:
                from hf_xet import XetSession
            except ImportError as exc:
                raise RuntimeError("high-performance Xet support is unavailable") from exc
            _XET_SESSION = XetSession()
        return _XET_SESSION


def _download_group_from_hub(jobs: list[tuple[dict[str, Any], Path]], token: str | None) -> None:
    """Download every selected file from one repository through one concurrent Xet group."""

    try:
        from hf_xet import XetFileInfo
    except ImportError as exc:
        raise RuntimeError("high-performance Xet support is unavailable") from exc
    sources = {str(entry["source"]) for entry, _ in jobs}
    revisions = {str(entry["revision"]) for entry, _ in jobs}
    if len(sources) != 1 or len(revisions) != 1:
        raise RuntimeError("an Xet download group must use one repository revision")
    source = next(iter(sources))
    revision = next(iter(revisions))
    missing = [entry["filename"] for entry, _ in jobs if not entry.get("xet_hash")]
    if missing:
        raise RuntimeError(f"Xet metadata is unavailable for {source}: {', '.join(missing)}")
    first_url = urllib.parse.urlsplit(jobs[0][0]["url"])
    endpoint = f"{first_url.scheme}://{first_url.netloc}"
    refresh_url = f"{endpoint}/api/models/{source}/xet-read-token/{revision}"
    headers = {"User-Agent": "comfyui-hoi4-portraits/1.0.0"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    partials = [(destination.with_name(f".{destination.name}.xet-part"), entry, destination) for entry, destination in jobs]
    for partial, _, _ in partials:
        partial.unlink(missing_ok=True)
    progress_lock = threading.Lock()
    last_progress = 0.0

    def show_progress(report: Any, _: Any) -> None:
        nonlocal last_progress
        now = time.monotonic()
        with progress_lock:
            if now - last_progress < 5 and int(report.total_bytes_completed) < int(report.total_bytes):
                return
            last_progress = now
            total = max(int(report.total_bytes), 1)
            completed = int(report.total_bytes_completed)
            rate = float(report.total_transfer_bytes_completion_rate or 0)
            print(f"  {source}: {completed / total:.0%} at {rate / (1024 * 1024):.1f} MB/s", flush=True)

    try:
        with _xet_session().new_file_download_group(
            token_refresh_url=refresh_url,
            token_refresh_headers=headers,
            custom_headers={"User-Agent": headers["User-Agent"]},
            progress_callback=show_progress,
            progress_interval_ms=500,
        ) as group:
            for partial, entry, _ in partials:
                group.start_download_file(XetFileInfo(entry["xet_hash"], int(entry["size_bytes"])), str(partial))
        for partial, entry, destination in partials:
            if not _verify(partial, entry):
                raise RuntimeError(f"downloaded file failed integrity validation: {entry['filename']}")
            partial.replace(destination)
    except Exception as exc:
        for partial, _, _ in partials:
            partial.unlink(missing_ok=True)
        if isinstance(exc, RuntimeError):
            raise
        raise RuntimeError(f"high-performance Xet download failed for {source}: {exc}") from exc


def _download_group_from_hub_with_retries(
    jobs: list[tuple[dict[str, Any], Path]],
    token: str | None,
    *,
    sleep_fn=time.sleep,
) -> None:
    attempts = len(XET_RETRY_DELAYS_SECONDS) + 1
    source = str(jobs[0][0]["source"])
    for attempt in range(1, attempts + 1):
        try:
            _download_group_from_hub(jobs, token)
            return
        except RuntimeError as exc:
            if attempt == attempts or not _retryable_download_error(exc):
                raise
            delay = _retry_after_seconds(exc, XET_RETRY_DELAYS_SECONDS[attempt - 1])
            print(f"  {source}: Xet is temporarily rate-limited; retrying in {delay}s ({attempt}/{attempts - 1}).", flush=True)
            sleep_fn(delay)
    raise AssertionError("unreachable")


def _download_via_http(entry: dict[str, Any], destination: Path, headers: dict[str, str]) -> None:
    partial = destination.with_name(f".{destination.name}.part")
    offset = partial.stat().st_size if partial.exists() else 0
    request_headers = dict(headers)
    if offset:
        request_headers["Range"] = f"bytes={offset}-"
    request = urllib.request.Request(entry["url"], headers=request_headers)
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            resumed = offset > 0 and getattr(response, "status", None) == 206
            downloaded = offset if resumed else 0
            mode = "ab" if resumed else "wb"
            total = int(entry["size_bytes"])
            with partial.open(mode) as output:
                while chunk := response.read(8 * 1024 * 1024):
                    output.write(chunk)
                    downloaded += len(chunk)
                    if downloaded % (256 * 1024 * 1024) < len(chunk):
                        print(f"  {entry['filename']}: {downloaded / total:.0%}", flush=True)
    except (OSError, urllib.error.URLError) as exc:
        raise RuntimeError(f"resumable HTTPS download failed for {entry['filename']}: {exc}") from exc
    if partial.stat().st_size != int(entry["size_bytes"]) or _sha256(partial) != entry["sha256"]:
        raise RuntimeError(f"downloaded file failed integrity validation: {entry['filename']}")
    partial.replace(destination)


def _download(entry: dict[str, Any], destination: Path, *, verify_only: bool, use_xet: bool = True) -> str:
    if _verify(destination, entry):
        return "verified"
    if destination.exists():
        raise RuntimeError(f"existing file failed integrity validation: {destination}")
    if verify_only:
        raise RuntimeError(f"required model is missing: {destination}")
    token = _hf_token() if "huggingface.co" in entry["url"] else None
    if entry.get("requires_huggingface_auth") and not token:
        raise RuntimeError(
            "FLUX.2 Klein 9B is gated. Accept its Hugging Face agreement, run `hf auth login` or set HF_TOKEN, then retry."
        )
    headers = {"User-Agent": "comfyui-hoi4-portraits/1.0.0"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    destination.parent.mkdir(parents=True, exist_ok=True)
    if use_xet and "huggingface.co" in entry["url"] and int(entry["size_bytes"]) >= XET_MIN_SIZE_BYTES:
        try:
            downloaded_path = _download_from_hub(entry, destination, token)
        except RuntimeError as exc:
            if not _retryable_download_error(exc):
                raise
            print(f"  {entry['filename']}: Xet is rate-limited; switching to resumable HTTPS.", flush=True)
        else:
            if downloaded_path is not None:
                if downloaded_path != destination:
                    downloaded_path.replace(destination)
                if not _verify(destination, entry):
                    raise RuntimeError(f"downloaded file failed integrity validation: {entry['filename']}")
                return "downloaded"
    _download_via_http(entry, destination, headers)
    return "downloaded"


def _retryable_download_error(exc: BaseException) -> bool:
    """Return whether another attempt can recover without user intervention."""

    current: BaseException | None = exc
    while current is not None:
        if isinstance(current, urllib.error.HTTPError) and (
            current.code == 429 or 500 <= current.code <= 599
        ):
            return True
        if isinstance(current, (TimeoutError, ConnectionError, urllib.error.URLError)):
            return True
        current = current.__cause__
    message = str(exc).casefold()
    return any(
        marker in message
        for marker in (
            "429",
            "too many requests",
            "rate limit",
            "timed out",
            "timeout",
            "connection reset",
            "temporary failure",
            "server error",
            "status client error (5",
        )
    )


def _retry_after_seconds(exc: BaseException, fallback: int) -> int:
    current: BaseException | None = exc
    while current is not None:
        if isinstance(current, urllib.error.HTTPError):
            value = current.headers.get("Retry-After") if current.headers else None
            if value and value.isdecimal():
                return max(fallback, min(int(value), 300))
        current = current.__cause__
    return fallback


def _download_with_retries(
    entry: dict[str, Any],
    destination: Path,
    *,
    verify_only: bool,
    use_xet: bool = True,
    sleep_fn=time.sleep,
) -> str:
    attempts = len(RETRY_DELAYS_SECONDS) + 1
    for attempt in range(1, attempts + 1):
        try:
            return _download(entry, destination, verify_only=verify_only, use_xet=use_xet)
        except RuntimeError as exc:
            if verify_only or attempt == attempts or not _retryable_download_error(exc):
                raise
            delay = _retry_after_seconds(exc, RETRY_DELAYS_SECONDS[attempt - 1])
            print(
                f"  {entry['filename']}: Hugging Face is rate-limiting the download; "
                f"retrying in {delay}s ({attempt}/{attempts - 1}).",
                flush=True,
            )
            sleep_fn(delay)
    raise AssertionError("unreachable")


def _selected_model_entries(
    manifest: dict[str, Any],
    selected: set[str],
    selected_variants: set[str],
    selected_quants: set[str],
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for entry in manifest["models"]:
        if selected and entry["filename"] not in selected:
            continue
        variant = str(entry.get("variant", "shared"))
        if selected_variants:
            if variant == "shared":
                pass
            elif variant not in selected_variants:
                continue
            elif (
                variant == "gguf"
                and selected_quants
                and str(entry.get("quant", "")) not in selected_quants
            ):
                continue
        entries.append(entry)
    return entries


def _group_jobs_by_source(
    jobs: list[tuple[dict[str, Any], Path]],
) -> list[list[tuple[dict[str, Any], Path]]]:
    """Batch one revision per repository so its files can share one Xet token."""

    grouped: dict[tuple[str, str], list[tuple[dict[str, Any], Path]]] = {}
    for entry, destination in jobs:
        key = (
            str(entry.get("source") or entry["url"].split("/resolve/", 1)[0]),
            str(entry.get("revision", "")),
        )
        grouped.setdefault(key, []).append((entry, destination))
    return list(grouped.values())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--comfyui-root", required=True, type=Path)
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--only", action="append", help="Download only this exact filename; repeat as needed")
    parser.add_argument(
        "--variant",
        action="append",
        choices=["full", "fp8", "gguf"],
        help=(
            "Which FLUX.2 Klein 9B variant(s) to install: full (BF16), fp8, or gguf. "
            "Repeat for multiple. Shared support models, including all four LoRAs, are always included."
        ),
    )
    parser.add_argument(
        "--gguf-quants",
        default="",
        help=(
            "Comma-separated GGUF quantizations to install, e.g. Q4_K_M,Q5_K_M. "
            "Only used with --variant gguf. Defaults to every listed quantization."
        ),
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Parallel repository groups (default: 4); files from each repository share one concurrent Xet group.",
    )
    args = parser.parse_args(argv)
    comfy_root = args.comfyui_root.expanduser().resolve()
    if not (comfy_root / "main.py").is_file():
        parser.error("--comfyui-root must point to a ComfyUI checkout containing main.py")
    manifest = json.loads((ROOT / "models.json").read_text(encoding="utf-8"))
    selected = set(args.only or [])
    selected_variants = set(args.variant or [])
    selected_quants = {item.strip() for item in args.gguf_quants.split(",") if item.strip()}
    if args.workers < 1:
        parser.error("--workers must be at least 1")
    jobs = []
    for entry in _selected_model_entries(manifest, selected, selected_variants, selected_quants):
        destination = comfy_root / "models" / entry["directory"] / entry["filename"]
        jobs.append((entry, destination))

    results: list[dict[str, str]] = []
    result_lock = threading.Lock()
    try:
        def run_group(group: list[tuple[dict[str, Any], Path]]) -> None:
            xet_jobs: list[tuple[dict[str, Any], Path]] = []
            direct_jobs: list[tuple[dict[str, Any], Path]] = []
            for entry, destination in group:
                print(f"Checking {entry['name']}...", flush=True)
                if _verify(destination, entry):
                    with result_lock:
                        results.append({"filename": entry["filename"], "path": str(destination), "status": "verified"})
                    continue
                if destination.exists():
                    raise RuntimeError(f"existing file failed integrity validation: {destination}")
                if args.verify_only:
                    raise RuntimeError(f"required model is missing: {destination}")
                token = _hf_token() if "huggingface.co" in entry["url"] else None
                if entry.get("requires_huggingface_auth") and not token:
                    raise RuntimeError("FLUX.2 Klein 9B is gated. Accept its Hugging Face agreement, run `hf auth login` or set HF_TOKEN, then retry.")
                destination.parent.mkdir(parents=True, exist_ok=True)
                if "huggingface.co" in entry["url"] and int(entry["size_bytes"]) >= XET_MIN_SIZE_BYTES:
                    xet_jobs.append((entry, destination))
                else:
                    direct_jobs.append((entry, destination))

            if xet_jobs:
                token = _hf_token()
                try:
                    _download_group_from_hub_with_retries(xet_jobs, token)
                except RuntimeError as exc:
                    print(f"  {xet_jobs[0][0]['source']}: Xet unavailable ({exc}); using resumable HTTPS.", flush=True)
                    for entry, destination in xet_jobs:
                        _download_with_retries(entry, destination, verify_only=False, use_xet=False)
                for entry, destination in xet_jobs:
                    with result_lock:
                        results.append({"filename": entry["filename"], "path": str(destination), "status": "downloaded"})

            for entry, destination in direct_jobs:
                status = _download_with_retries(entry, destination, verify_only=False)
                with result_lock:
                    results.append({"filename": entry["filename"], "path": str(destination), "status": status})

        groups = _group_jobs_by_source(jobs)
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(args.workers, len(groups) or 1)) as executor:
            futures = [executor.submit(run_group, group) for group in groups]
            for future in concurrent.futures.as_completed(futures):
                future.result()
    except RuntimeError as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc), "completed": results}, indent=2), file=sys.stderr)
        return 1
    result_order = {entry["filename"]: index for index, (entry, _) in enumerate(jobs)}
    results.sort(key=lambda item: result_order[item["filename"]])
    print(json.dumps({"status": "PASS", "models": results}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
