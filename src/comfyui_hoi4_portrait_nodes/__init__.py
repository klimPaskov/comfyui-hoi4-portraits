"""Project-owned ComfyUI nodes.

The node pack contains orchestration and guard nodes only. It does not ship
models, source portraits, backgrounds, or secrets. All filesystem reads are
restricted to the project/job roots and all production promotion remains in
the controller after independent auditing.
"""

from __future__ import annotations

import sys
from pathlib import Path

_node_root = Path(__file__).resolve().parent
_project_src_candidates = (_node_root.parent, _node_root)
_project_src = next((candidate for candidate in _project_src_candidates if (candidate / "portrait_pipeline").is_dir()), _node_root.parent)
if str(_project_src) not in sys.path:
    sys.path.insert(0, str(_project_src))

from .nodes import (
    HOI4AutopromptClient,
    HOI4BundledBackground,
    HOI4ConservativePrep,
    HOI4EvidenceExport,
    HOI4ForegroundMask,
    HOI4HumanControls,
    HOI4HeadShouldersCrop,
    HOI4JobInput,
    HOI4PromptJobInput,
    HOI4JobSource,
    HOI4MaskAndBackgroundGuard,
    HOI4FinishPreparedPortrait,
    HOI4KreaModelLoadBarrier,
    HOI4PortraitCrop,
    HOI4PromptInput,
    HOI4RandomPortraitPrompt,
    HOI4SourceGuard,
    HOI4SubjectSelect,
    HOI4UseColorWhenNeeded,
)

NODE_CLASS_MAPPINGS = {
    "HOI4JobInput": HOI4JobInput,
    "HOI4PromptJobInput": HOI4PromptJobInput,
    "HOI4HumanControls": HOI4HumanControls,
    "HOI4JobSource": HOI4JobSource,
    "HOI4SourceGuard": HOI4SourceGuard,
    "HOI4SubjectSelect": HOI4SubjectSelect,
    "HOI4HeadShouldersCrop": HOI4HeadShouldersCrop,
    "HOI4ConservativePrep": HOI4ConservativePrep,
    "HOI4ForegroundMask": HOI4ForegroundMask,
    "HOI4MaskAndBackgroundGuard": HOI4MaskAndBackgroundGuard,
    "HOI4PortraitCrop": HOI4PortraitCrop,
    "HOI4UseColorWhenNeeded": HOI4UseColorWhenNeeded,
    "HOI4FinishPreparedPortrait": HOI4FinishPreparedPortrait,
    "HOI4KreaModelLoadBarrier": HOI4KreaModelLoadBarrier,
    "HOI4PromptInput": HOI4PromptInput,
    "HOI4RandomPortraitPrompt": HOI4RandomPortraitPrompt,
    "HOI4AutopromptClient": HOI4AutopromptClient,
    "HOI4BundledBackground": HOI4BundledBackground,
    "HOI4EvidenceExport": HOI4EvidenceExport,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    key: value.replace("HOI4", "HOI4 ").replace("Input", "Input") for key, value in {
        "HOI4JobInput": "Portrait workflow settings",
        "HOI4PromptJobInput": "Load portrait description",
        "HOI4HumanControls": "Input portrait & portrait options",
        "HOI4JobSource": "Load input portrait",
        "HOI4SourceGuard": "Check input portrait",
        "HOI4SubjectSelect": "Select the subject",
        "HOI4HeadShouldersCrop": "Crop the portrait",
        "HOI4ConservativePrep": "Prepare the portrait",
        "HOI4ForegroundMask": "Separate person from background",
        "HOI4MaskAndBackgroundGuard": "Add approved background",
        "HOI4PortraitCrop": "Crop to head and shoulders",
        "HOI4UseColorWhenNeeded": "Choose color treatment",
        "HOI4FinishPreparedPortrait": "Finish prepared portrait",
        "HOI4KreaModelLoadBarrier": "Prepare generation",
        "HOI4PromptInput": "Use portrait description",
        "HOI4RandomPortraitPrompt": "Create a fictional portrait idea",
        "HOI4AutopromptClient": "Create portrait description",
        "HOI4BundledBackground": "HOI4 portrait background",
        "HOI4EvidenceExport": "Prepare portrait for saving",
    }.items()
}

WEB_DIRECTORY = None
