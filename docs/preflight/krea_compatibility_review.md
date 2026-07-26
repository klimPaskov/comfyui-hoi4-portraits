# Krea 2 Compatibility Review

Status: **BLOCKED_PINNED_CORE_SCHEMA_UNVERIFIED**.

The generated graph now follows the primary `comfyui-krea2edit` contract for
`fit` mode: `Krea2EditModelPatch` receives the Krea VAE and the approved
composite source image, and both grounded encoders use the documented 768-pixel
baseline. The official ComfyUI Krea 2 documentation also identifies Turbo as
the eight-step route.

The pinned ComfyUI core revision
`f49bdb655707b97952dcef40e12e5af1f08d2007` does not list `krea2` among the
`DualCLIPLoader` type choices in its primary `nodes.py` source. The exact
workflow therefore cannot be called loadable against the current lock without
a live verification of a compatible core/node combination. The loader type is
not silently changed. No Krea model is installed and no generation is claimed.

Primary evidence and the machine-readable finding are in
`docs/preflight/krea_compatibility_review.json`.
