from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .constants import AUTOPROMPTER_PATH
from .util import sha256_file


@dataclass(frozen=True)
class PromptValidationResult:
    passed: bool
    normalized_prompt: str | None
    failure_codes: tuple[str, ...] = ()
    findings: tuple[str, ...] = ()
    claims: dict[str, tuple[str, ...]] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "normalized_prompt": self.normalized_prompt,
            "failure_codes": list(self.failure_codes),
            "findings": list(self.findings),
            "claims": {key: list(value) for key, value in self.claims.items()},
        }


_FORBIDDEN_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"\bbackground\b|\bbackdrop\b|\bscenery\b|\broom\b|\binterior\b|\bexterior\b", "background"),
    (r"\blighting\b|\blit\b|\bbacklit\b|\bkey light\b|\bsoftbox\b|\bshadow(?:s|ed)?\b|\bhigh[- ]key\b|\blow[- ]key\b", "lighting"),
    (r"\bstyle\b|\boil painting\b|\bwatercolor\b|\billustration\b|\bdigital art\b|\bphotorealistic\b|\bbrushwork\b|\bcanvas\b|\bcomic\b|\banime\b", "style"),
    (r"\bpalette\b|\bcolor palette\b|\bsepia\b|\bmonochrome\b|\bblack[- ]and[- ]white\b|\bblue[- ]toned\b|\bwarm[- ]toned\b|\bcool[- ]toned\b", "palette"),
    (r"\bhigh[- ]quality\b|\b8k\b|\b4k\b|\bultra[- ]detailed\b|\bsharp focus\b|\bhd\b|\bresolution\b|\bquality\b", "image_quality"),
    (r"\bcomposition\b|\bcentered\b|\bclose[- ]up\b|\bwide shot\b|\bportrait orientation\b|\bhead[- ]and[- ]shoulders\b|\bthree[- ]quarter view\b|\bprofile view\b", "composition"),
    (r"\bface[- ]swap\b|\bfaceswap\b|\bdeepfake\b|\breplace (?:the )?(?:face|head|person)\b|\bidentity swap\b|\bchange (?:the )?(?:face|head)\b", "identity_swap"),
)

_CLAIM_PATTERNS: dict[str, tuple[str, ...]] = {
    "nationality": (
        "american", "british", "english", "french", "german", "italian", "spanish", "russian", "soviet",
        "polish", "japanese", "chinese", "korean", "swedish", "norwegian", "danish", "finnish", "estonian",
        "latvian", "lithuanian", "ukrainian", "austrian", "hungarian", "romanian", "bulgarian", "turkish",
        "greek", "dutch", "belgian", "canadian", "australian", "indian", "irish", "scottish", "welsh",
    ),
    "ideology": (
        "communist", "socialist", "fascist", "national socialist", "liberal", "conservative", "monarchist",
        "anarchist", "democratic", "authoritarian", "republican", "royalist",
    ),
    "roles": (
        "general", "marshal", "commander", "officer", "soldier", "pilot", "admiral", "president", "minister",
        "king", "queen", "emperor", "empress", "duke", "duchess", "leader", "politician", "operative",
        "spy", "scientist", "field marshal", "prime minister",
    ),
    "medals_or_insignia": (
        "medal", "medals", "medallion", "cross", "star", "badge", "insignia", "ribbon", "order of", "iron cross",
    ),
    "organization_or_branch": (
        "army", "navy", "air force", "marines", "wehrmacht", "ss", "red army", "royal navy", "uniform", "military",
    ),
    "jewelry": (
        "earring", "earrings", "necklace", "bracelet", "ring", "brooch", "jewelry", "jewellery", "piercing",
    ),
}


def autoprompter_instruction(root: str | Path) -> str:
    path = Path(root) / AUTOPROMPTER_PATH
    return path.read_text(encoding="utf-8")


def autoprompter_instruction_sha256(root: str | Path) -> str:
    return sha256_file(Path(root) / AUTOPROMPTER_PATH)


def _normalize_allowed(text: str) -> str:
    text = text.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n").strip()
    text = re.sub(r" {2,}", " ", text)
    if text.endswith("\n"):
        text = text[:-1]
    return text


def _matches_claims(prompt: str) -> dict[str, tuple[str, ...]]:
    lowered = prompt.casefold()
    found: dict[str, tuple[str, ...]] = {}
    for category, terms in _CLAIM_PATTERNS.items():
        matches = tuple(term for term in terms if re.search(rf"(?<![\w-]){re.escape(term)}(?![\w-])", lowered))
        if matches:
            found[category] = matches
    return found


def validate_prompt(
    prompt: str,
    *,
    record_name: str | None = None,
    known_aliases: tuple[str, ...] = (),
    allowed_claims: dict[str, list[str] | tuple[str, ...]] | None = None,
    max_length: int = 1200,
) -> PromptValidationResult:
    findings: list[str] = []
    failure_codes: list[str] = []
    claims = _matches_claims(prompt)
    normalized = _normalize_allowed(prompt)

    if not normalized:
        failure_codes.append("AUTOPROMPT_EMPTY")
    if "\n" in normalized or "\t" in normalized:
        failure_codes.append("AUTOPROMPT_FORMAT_INVALID")
        findings.append("prompt must be one non-empty line")
    if normalized.startswith(('"', "'", "```")) or normalized.endswith(('"', "'", "```")):
        failure_codes.append("AUTOPROMPT_FORMAT_INVALID")
        findings.append("quotation or Markdown wrapper")
    if not normalized.startswith("hoi4_portrait,"):
        failure_codes.append("AUTOPROMPT_PREFIX_INVALID")
    if len(normalized) > max_length:
        failure_codes.append("AUTOPROMPT_FORMAT_INVALID")
        findings.append("prompt exceeds locked maximum")

    haystack = normalized.casefold()
    for term in (record_name, *known_aliases):
        if term and term.casefold() in haystack:
            failure_codes.append("AUTOPROMPT_NAME_LEAK")
            findings.append(f"subject name or alias appears: {term}")
    for pattern, label in _FORBIDDEN_PATTERNS:
        if re.search(pattern, normalized, flags=re.IGNORECASE):
            failure_codes.append("AUTOPROMPT_PROHIBITED_CONTENT")
            findings.append(f"prohibited {label} claim")

    allowed_claims = allowed_claims or {}
    for category, matches in claims.items():
        allowed = {str(item).casefold() for item in allowed_claims.get(category, [])}
        unsupported = tuple(item for item in matches if item.casefold() not in allowed)
        if unsupported:
            failure_codes.append("AUTOPROMPT_UNVERIFIED_CLAIM")
            findings.append(f"unsupported {category}: {', '.join(unsupported)}")

    # The validator must not rewrite model output. Normalization is only a
    # proposed value; it is returned only when every gate passes.
    unique_codes = tuple(dict.fromkeys(failure_codes))
    return PromptValidationResult(
        passed=not unique_codes,
        normalized_prompt=normalized if not unique_codes else None,
        failure_codes=unique_codes,
        findings=tuple(dict.fromkeys(findings)),
        claims=claims,
    )

