# Autoprompter Specification

## Workflow boundary

The autoprompter exists only in:

- `human_local_mac_16gb`
- `human_full_power_gpu`

The following workflows must contain no autoprompter node, VLM client, hidden VLM call, or automatic prompt fallback:

- `agent_local_mac_16gb`
- `agent_remote_runpod`

## Exact instruction

The vision model receives the exact contents of `prompts/autoprompter_instruction.txt`. Do not prepend a system explanation about Krea 2, the LoRA, the pipeline, identity preservation, or the reason for the prompt. Do not append examples.

The image input is the processed portrait after:

- EXIF orientation correction
- subject selection
- head-and-shoulders crop
- conditional colorization
- conservative restoration

The model must not inspect the approved background composite because the instruction forbids background description and the original subject is the only relevant content.

## Local model

First qualification candidate:

- `Qwen/Qwen3-VL-4B-Instruct-GGUF`
- official Q4_K_M language model
- matching official vision `mmproj`
- pinned llama.cpp release or commit
- loopback-only OpenAI-compatible sidecar

Use a small context window sufficient for one instruction and one image. Run one request at a time. Stop the sidecar and verify memory release before loading Krea 2.

No unofficial quantization is allowed when an official Qwen GGUF exists.

## Full-power model

First qualification candidate:

- `Qwen/Qwen3-VL-8B-Instruct`
- BF16 or an officially published and supported reduced-precision variant

Benchmark the official 32B family only on hardware that can load it safely in a separate stage. Choose 32B only when it materially reduces unsupported claims or format failures over 8B. Model size is not a quality assumption.

## Output validation

The validator operates on Unicode text and returns a structured report. It may normalize only:

- UTF-8 BOM removal
- CRLF to LF
- outer whitespace
- repeated internal ASCII spaces
- a single trailing newline

It cannot paraphrase, delete a clause, replace a term, add the trigger, or rewrite the description.

PASS requires:

- one non-empty line
- exact prefix `hoi4_portrait,`
- no heading, bullet, quotation wrapper, Markdown, explanation, or model preamble
- no person's record name or known aliases
- no background, lighting, art style, brushwork, palette, image quality, or composition description
- no unsupported nationality, ideology, role, medal, insignia, or decoration claim
- length within the locked prompt maximum

## High-risk claim validation

High-risk claim classes are:

- nationality
- ideology
- military or political role
- named medal or insignia
- organization or uniform branch
- jewelry type when unclear

For every high-risk claim, require one of:

1. the claim is explicitly allowlisted in job metadata from verified provenance
2. an independent fixed verification pass on the pre-colorized processed source returns a supported verdict above its calibrated threshold

The colorized derivative cannot authorize a claim.

When a claim is unsupported, reject the whole autoprompt. Do not remove the words and keep the rest because that would rewrite model output.

## Retry

Use at most three autoprompt attempts. Every attempt receives the same exact instruction and the same processed image. The implementation may use a different recorded seed or decoding setting selected from a fixed retry profile. It cannot add corrective prose to the instruction.

Failure codes:

- `AUTOPROMPT_PREFIX_INVALID`
- `AUTOPROMPT_FORMAT_INVALID`
- `AUTOPROMPT_PROHIBITED_CONTENT`
- `AUTOPROMPT_NAME_LEAK`
- `AUTOPROMPT_UNVERIFIED_CLAIM`
- `AUTOPROMPT_EMPTY`

After the retry limit, the human workflow pauses for a manual prompt or ends as `NEEDS_REVIEW`. It never invents a fallback prompt.

## Agent prompt validation

Agent-supplied prompts use the same structural and prohibited-content validator. The coding agent can supply provenance-backed nationality or role claims through `allowed_autoprompt_claims`, but the person's name remains forbidden.

## Test suite

Test at least:

- correct trigger
- wrong trigger spelling
- heading before trigger
- quoted output
- multiple paragraphs
- person's name
- background and lighting language
- style language
- invented nationality
- invented medal
- source with no visible uniform
- black-and-white source with colorized derivative
- valid concise descriptions across age, facial hair, glasses, hat, jewelry, and three-quarter pose

Measure exact-format pass rate and unsupported-claim rate for local and full-power models. The selected models must pass the locked acceptance thresholds before workflow delivery.
