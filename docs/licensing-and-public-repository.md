# Licensing and public-repository policy

This project is public-facing code and workflow metadata. Public visibility does not grant rights to third-party models, source portraits, HOI4 assets, or the private style LoRA.

## Never commit

- model weights or tokenizer caches;
- source portraits or generated portraits;
- the immutable private LoRA;
- API keys, gateway tokens, `.env` files, or remote credentials;
- local ComfyUI installations and caches;
- private background/source material.

The repository `.gitignore` blocks these classes. Review `git status --ignored` before publishing changes.

## Required review before qualification

The exact revision, source URL, retrieval date, checksum, and applicable license must be recorded for every model and preprocessing artifact. Krea 2 use remains subject to the [Krea 2 licensing terms](https://www.krea.ai/krea-2-licensing). The project keeps Krea artifacts local until the owner confirms the intended use and distribution scope.

ComfyUI and the Krea node pack are pinned to their source revisions in the dependency locks. Qwen and llama.cpp sources are recorded in the autoprompter lock and model lock. Read those records before redistributing any runtime or model artifact.

## Source and background rights

A real-person source requires attribution, rights notes, and a source manifest. An approved HOI4 background requires a registry ID, exact file checksum, source URL, and redistribution decision. If any of those records is missing, the pipeline returns a blocker and does not create a final DDS.

## Contributions

Do not attach private portraits or weights to public issues or pull requests. Use sanitized JSON examples and screenshots such as those in [`docs/examples/`](examples/) and [`docs/assets/`](assets/).
