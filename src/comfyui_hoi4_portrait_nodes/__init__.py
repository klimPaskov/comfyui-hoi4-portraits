"""Project-owned ComfyUI nodes.

The node pack contains orchestration and guard nodes only. It does not ship
models, source portraits, backgrounds, or secrets. All filesystem reads are
restricted to the project/job roots and all production promotion remains in
the controller after independent auditing.
"""

from __future__ import annotations

import sys
from pathlib import Path

_project_src = Path(__file__).resolve().parents[1]
if str(_project_src) not in sys.path:
    sys.path.insert(0, str(_project_src))

from .nodes import (
    HOI4AutopromptClient,
    HOI4ConservativePrep,
    HOI4EvidenceExport,
    HOI4ForegroundMask,
    HOI4HumanControls,
    HOI4HeadShouldersCrop,
    HOI4JobInput,
    HOI4JobSource,
    HOI4MaskAndBackgroundGuard,
    HOI4KreaModelLoadBarrier,
    HOI4PromptInput,
    HOI4SourceGuard,
    HOI4SubjectSelect,
)

NODE_CLASS_MAPPINGS = {
    "HOI4JobInput": HOI4JobInput,
    "HOI4HumanControls": HOI4HumanControls,
    "HOI4JobSource": HOI4JobSource,
    "HOI4SourceGuard": HOI4SourceGuard,
    "HOI4SubjectSelect": HOI4SubjectSelect,
    "HOI4HeadShouldersCrop": HOI4HeadShouldersCrop,
    "HOI4ConservativePrep": HOI4ConservativePrep,
    "HOI4ForegroundMask": HOI4ForegroundMask,
    "HOI4MaskAndBackgroundGuard": HOI4MaskAndBackgroundGuard,
    "HOI4KreaModelLoadBarrier": HOI4KreaModelLoadBarrier,
    "HOI4PromptInput": HOI4PromptInput,
    "HOI4AutopromptClient": HOI4AutopromptClient,
    "HOI4EvidenceExport": HOI4EvidenceExport,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    key: value.replace("HOI4", "HOI4 ").replace("Input", "Input") for key, value in {
        "HOI4JobInput": "Job contract and profile",
        "HOI4HumanControls": "Human review controls",
        "HOI4JobSource": "Job source loader",
        "HOI4SourceGuard": "Source provenance guard",
        "HOI4SubjectSelect": "Subject selector",
        "HOI4HeadShouldersCrop": "Head and shoulders crop",
        "HOI4ConservativePrep": "Conservative source preparation",
        "HOI4ForegroundMask": "Pinned foreground mask analysis",
        "HOI4MaskAndBackgroundGuard": "Mask and approved background guard",
        "HOI4KreaModelLoadBarrier": "Release completed models before Krea sampling",
        "HOI4PromptInput": "Agent job-contract prompt",
        "HOI4AutopromptClient": "Human exact autoprompter client",
        "HOI4EvidenceExport": "Evidence export",
    }.items()
}

WEB_DIRECTORY = None
