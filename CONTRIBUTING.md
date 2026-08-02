# Contributing

Thanks for improving the HOI4 portrait workflows. Bug reports, workflow fixes,
documentation improvements, and reproducible quality comparisons are welcome.

## Before opening a change

1. Fork the repository and create a focused branch.
2. Do not commit private or unlicensed source/generated portraits, model
   weights, API tokens, or private ComfyUI settings. Maintainer-approved test
   images may live under `docs/assets/test-runs/` with their conditions
   documented.
3. Edit `scripts/build_workflows.py` instead of hand-editing generated workflow
   JSON. Rebuild afterward.
4. Keep public workflows portable across the supported ComfyUI environments.
   Any new dependency needs a clear portability reason and maintainer approval.

## Verify the change

```bash
python scripts/build_workflows.py
python scripts/validate_workflows.py
python -m unittest discover -s tests -v
git diff --check
```

Commit regenerated editor JSON, API JSON, and `workflows/manifest.json` with
the source change. If visual output changes, state the GPU, ComfyUI revision,
model checksums, seed, prompt, and settings in the pull request. Use only test
images you have permission to share.

## Reporting workflow bugs

Include the workflow name, ComfyUI version/commit, operating system, GPU and
VRAM, full error text, and whether the same API JSON passes
`scripts/validate_workflows.py`. Redact file paths, tokens, and personal data.

By contributing, you agree that your project-owned contribution is licensed
under the repository's MIT license.
