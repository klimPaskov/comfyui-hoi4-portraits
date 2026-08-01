#!/usr/bin/env python3
"""Download and checksum-verify the models used by the workflows."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


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


def _download(entry: dict[str, Any], destination: Path, *, verify_only: bool) -> str:
    if _verify(destination, entry):
        return "verified"
    if destination.exists():
        raise RuntimeError(f"existing file failed checksum verification: {destination}")
    if verify_only:
        raise RuntimeError(f"required model is missing: {destination}")
    token = _hf_token() if "huggingface.co" in entry["url"] else None
    if entry.get("requires_huggingface_auth") and not token:
        raise RuntimeError(
            "FLUX.2 Klein 9B is gated. Accept its Hugging Face agreement, run `hf auth login` or set HF_TOKEN, then retry."
        )
    headers = {"User-Agent": "comfyui-hoi4-portraits/2.0"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_name(f".{destination.name}.part")
    request = urllib.request.Request(entry["url"], headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=120) as response, partial.open("wb") as output:
            downloaded = 0
            total = int(entry["size_bytes"])
            while chunk := response.read(8 * 1024 * 1024):
                output.write(chunk)
                downloaded += len(chunk)
                if downloaded % (256 * 1024 * 1024) < len(chunk):
                    print(f"  {entry['filename']}: {downloaded / total:.0%}", flush=True)
        if partial.stat().st_size != int(entry["size_bytes"]) or _sha256(partial) != entry["sha256"]:
            raise RuntimeError(f"downloaded file failed checksum verification: {entry['filename']}")
        partial.replace(destination)
    except (OSError, urllib.error.URLError) as exc:
        partial.unlink(missing_ok=True)
        raise RuntimeError(f"failed to download {entry['filename']}: {exc}") from exc
    return "downloaded"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--comfyui-root", required=True, type=Path)
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--only", action="append", help="Download only this exact filename; repeat as needed")
    args = parser.parse_args(argv)
    comfy_root = args.comfyui_root.expanduser().resolve()
    if not (comfy_root / "main.py").is_file():
        parser.error("--comfyui-root must point to a ComfyUI checkout containing main.py")
    manifest = json.loads((ROOT / "models.json").read_text(encoding="utf-8"))
    selected = set(args.only or [])
    results = []
    try:
        for entry in manifest["models"]:
            if selected and entry["filename"] not in selected:
                continue
            destination = comfy_root / "models" / entry["directory"] / entry["filename"]
            print(f"Checking {entry['name']}...")
            status = _download(entry, destination, verify_only=args.verify_only)
            results.append({"filename": entry["filename"], "path": str(destination), "status": status})
    except RuntimeError as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc), "completed": results}, indent=2), file=sys.stderr)
        return 1
    print(json.dumps({"status": "PASS", "models": results}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
