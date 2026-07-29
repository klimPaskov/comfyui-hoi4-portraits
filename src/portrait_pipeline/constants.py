from __future__ import annotations

from enum import Enum, IntEnum


class _StringEnum(str, Enum):
    """Python 3.10-compatible equivalent of :class:`enum.StrEnum`."""

    def __str__(self) -> str:
        return self.value


class ExitCode(IntEnum):
    SUCCESS = 0
    INPUT_SCHEMA_INVALID = 10
    SOURCE_INVALID = 11
    AMBIGUOUS_SUBJECT = 12
    FACE_NOT_FOUND_OR_UNUSABLE = 13
    PROVENANCE_MISSING = 14
    BACKGROUND_UNRESOLVED = 15
    DEPENDENCY_MISSING = 20
    MODEL_CHECKSUM_MISMATCH = 21
    NODE_MISSING = 22
    WORKFLOW_INVALID = 23
    OUT_OF_MEMORY = 30
    GENERATION_FAILED = 31
    CANCELED = 32
    IDENTITY_NO_PASSING_CANDIDATE = 40
    STYLE_NO_PASSING_CANDIDATE = 41
    MASK_AUDIT_FAILED = 42
    AUDIT_UNCERTAIN = 43
    DDS_VALIDATION_FAILED = 50
    INTEGRATION_BLOCKED = 51
    REMOTE_AUTH_OR_TRANSPORT_FAILED = 60
    INTERNAL_ERROR = 70


class JobStatus(_StringEnum):
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELED = "CANCELED"
    BLOCKED = "BLOCKED"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class ExecutionProfile(_StringEnum):
    HUMAN_LOCAL_MAC_16GB = "human_local_mac_16gb"
    HUMAN_FULL_POWER_GPU = "human_full_power_gpu"
    AGENT_LOCAL_MAC_16GB = "agent_local_mac_16gb"
    AGENT_FULL_POWER_GPU = "agent_full_power_gpu"
    AGENT_REMOTE_RUNPOD = "agent_remote_runpod"


PROFILE_LIMITS: dict[str, dict[str, int | bool | str]] = {
    ExecutionProfile.HUMAN_LOCAL_MAC_16GB: {
        "candidate_max": 2,
        "retry_max": 2,
        "canvas_width": 832,
        "canvas_height": 1120,
        "autoprompter": True,
        "route": "local_mac",
        "prompt_model": "Qwen/Qwen3-VL-4B-Instruct-GGUF",
    },
    ExecutionProfile.HUMAN_FULL_POWER_GPU: {
        "candidate_max": 6,
        "retry_max": 2,
        "canvas_width": 1196,
        "canvas_height": 1610,
        "autoprompter": True,
        "route": "full_power_gpu",
        "prompt_model": "Qwen/Qwen3-VL-8B-Instruct",
    },
    ExecutionProfile.AGENT_LOCAL_MAC_16GB: {
        "candidate_max": 2,
        "retry_max": 2,
        "canvas_width": 832,
        "canvas_height": 1120,
        "autoprompter": False,
        "route": "local_mac",
        "prompt_model": "job_contract",
    },
    ExecutionProfile.AGENT_FULL_POWER_GPU: {
        "candidate_max": 6,
        "retry_max": 2,
        "canvas_width": 1196,
        "canvas_height": 1610,
        "autoprompter": False,
        "route": "full_power_gpu",
        "prompt_model": "job_contract",
    },
    ExecutionProfile.AGENT_REMOTE_RUNPOD: {
        "candidate_max": 6,
        "retry_max": 2,
        "canvas_width": 1196,
        "canvas_height": 1610,
        "autoprompter": False,
        "route": "remote_runpod",
        "prompt_model": "job_contract",
    },
}


GROUP_LABELS = [
    "00 Job and source",
    "01 Subject selection",
    "02 Crop and source preparation",
    "03 Color and restoration",
    "04 Masks and approved background",
    "05 Prompt",
    "06 Krea 2 identity edit",
    "07 HOI4 style LoRA",
    "08 Candidate generation",
    "09 Preview and evidence export",
]

HARD_AUDIT_GATES = [
    "face_embedding",
    "landmarks",
    "facial_proportions",
    "asymmetry",
    "head_direction",
    "expression",
    "hairline",
    "facial_hair",
    "accessories",
    "foreground_integrity",
    "mask_boundary",
    "style",
    "provenance",
]

STAGES = [
    "JOB_ACCEPTED",
    "SOURCE_VALIDATED",
    "SUBJECT_SELECTED",
    "REFERENCE_PREPARED",
    "BACKGROUND_RESOLVED",
    "PROMPT_READY",
    "WORKFLOW_VALIDATED",
    "CANDIDATES_GENERATED",
    "IDENTITY_AUDIT",
    "STYLE_AUDIT",
    "MASK_AUDIT",
    "PROVENANCE_AUDIT",
    "CANDIDATE_SELECTED",
    "PNG_VALIDATED",
    "DDS_VALIDATED",
    "INTEGRATION_HANDOFF",
    "COMPLETED",
]

WORKFLOW_VERSION = "graph-spec-1.1.0"
DEPENDENCY_LOCK_VERSION = "lock-2026-07-26.1"
AUTOPROMPTER_PATH = "prompts/autoprompter_instruction.txt"
STYLE_LORA_PATH = "loras/hoi4_portrait_new_style_lora.safetensors"
STYLE_LORA_SHA256 = "2ad94552d151d2dedf151cf7356cdd3ea07677607ff289fc0ac61534b34dead1"
# Calibration records may use either vocabulary used by the planning package
# (`APPROVED`) or the registry vocabulary used by the runtime (`RESOLVED`).
# Call sites still require a non-placeholder id, approver record, and
# fail-closed numeric values before treating a record as production-ready.
CALIBRATED_THRESHOLD_STATUSES = frozenset({"APPROVED", "RESOLVED"})
FINAL_WIDTH = 156
FINAL_HEIGHT = 210
