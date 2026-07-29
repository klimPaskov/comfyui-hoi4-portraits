from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Iterable


def project_root(start: str | Path | None = None) -> Path:
    if start is None:
        start = Path.cwd()
    path = Path(start).resolve()
    for candidate in (path, *path.parents):
        if (candidate / "docs" / "schemas" / "portrait_job_input.schema.json").is_file():
            return candidate
    raise FileNotFoundError("project root with docs/schemas/ was not found")


def sha256_file(path: str | Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def tree_sha256(root: str | Path) -> str:
    """Hash a source tree deterministically by relative path and file bytes."""

    root_path = Path(root).resolve()
    digest = hashlib.sha256()
    files = [
        path for path in root_path.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts and path.suffix not in {".pyc", ".pyo"}
    ]
    for path in sorted(files, key=lambda item: item.relative_to(root_path).as_posix()):
        digest.update(path.relative_to(root_path).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(bytes.fromhex(sha256_file(path)))
        digest.update(b"\0")
    return digest.hexdigest()


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def atomic_json_write(path: str | Path, value: Any) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, indent=2, ensure_ascii=False) + "\n"
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=destination.parent, delete=False) as tmp:
        tmp.write(payload)
        temporary = Path(tmp.name)
    os.replace(temporary, destination)


def sanitize_public_paths(value: Any, root: str | Path) -> Any:
    """Redact host-local paths before writing checked-in public evidence.

    Runtime preflight objects intentionally retain absolute paths for local
    diagnostics.  Their checked-in reports must remain portable and must not
    disclose the operator's home directory or external checkout layout.
    """

    root_text = str(Path(root).resolve())

    def clean(item: Any) -> Any:
        if isinstance(item, dict):
            return {key: clean(child) for key, child in item.items()}
        if isinstance(item, list):
            return [clean(child) for child in item]
        if isinstance(item, tuple):
            return [clean(child) for child in item]
        if not isinstance(item, str):
            return item
        text = item.replace(root_text, "<project-root>")
        text = re.sub(r"(?<![A-Za-z0-9_])/(?:Users|home)/[^\s\"'<>]+", "<local-path>", text)
        text = re.sub(r"(?<![A-Za-z0-9_])[A-Za-z]:/[^\s\"'<>]+", "<local-path>", text)
        return text

    return clean(value)


def relative_safe_path(root: str | Path, path: str | Path) -> Path:
    root_path = Path(root).resolve()
    target = (root_path / path).resolve() if not Path(path).is_absolute() else Path(path).resolve()
    try:
        target.relative_to(root_path)
    except ValueError as exc:
        raise ValueError(f"path escapes allowed root: {path}") from exc
    return target


def is_sha256(value: object) -> bool:
    return isinstance(value, str) and bool(re.fullmatch(r"[a-f0-9]{64}", value))


def scan_text_for_secrets(text: str) -> list[str]:
    findings: list[str] = []
    patterns: Iterable[tuple[str, str]] = (
        (r"(?i)runpod[_-]?api[_-]?key\s*[:=]\s*[^\s]+", "RUNPOD_API_KEY"),
        (r"(?i)hf[_-]?token\s*[:=]\s*[^\s]+", "HF_TOKEN"),
        (r"(?i)github[_-]?token\s*[:=]\s*[^\s]+", "GITHUB_TOKEN"),
        (r"(?i)bearer\s+[A-Za-z0-9._-]{12,}", "BEARER_TOKEN"),
        (r"(?i)sk-[A-Za-z0-9]{12,}", "OPENAI_KEY"),
    )
    for pattern, label in patterns:
        if re.search(pattern, text):
            findings.append(label)
    return findings
