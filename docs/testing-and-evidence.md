# Testing and evidence

The repository separates three claims:

- Structural validation: workflow JSON, schemas, node classes, model locks, revisions, and checksums.
- Smoke execution: source intake, preprocessing, prompt routing, Krea graph submission, previews, and portrait export.
- Production acceptance: identity-first experiment selection plus independent audit PASS for every required category.

The workflow screenshots and three 256×352, two-step before/after pairs are execution evidence only. They do not claim production quality or final acceptance.

Before production use, run:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
PYTHONPATH=src python -c "from portrait_pipeline.graph_spec.builder import build_workflow_artifacts; build_workflow_artifacts()"
PYTHONPATH=src python scripts/preflight/verify_live_comfy_compatibility.py
```

Any missing node, unsupported model format, unavailable approved background, checksum mismatch, license blocker, failed audit, or unmeasured target capability remains a hard blocker.
