# ControlNet policy

ControlNet is not included in the current workflows.

The approved route already has a source reference, deterministic subject/crop preparation, an identity-edit stage, a foreground mask, and an approved background guard. Adding a ControlNet node without a live-compatible, revision-pinned experiment would add a new dependency and an unmeasured identity/geometry interaction. The project therefore keeps the graph smaller and fail-closed.

ControlNet may be reconsidered only through the documented identity/style experiment matrix, with an official source, pinned revision and checksum, license review, live node compatibility, and identity-first audit comparison. It must not be enabled by editing a workflow JSON directly.
