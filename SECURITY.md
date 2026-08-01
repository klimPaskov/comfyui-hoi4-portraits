# Security policy

## Supported version

Security fixes target the latest public release and the repository's default
branch. The archived v1 Krea workflows are preserved for reference and are not
actively supported.

## Reporting a vulnerability

Please use GitHub's **Security → Report a vulnerability** private reporting
flow. Do not open a public issue for leaked credentials, unsafe download
behavior, path traversal, arbitrary code execution, or another exploitable
problem.

Include affected files or workflow nodes, reproduction steps, impact, and any
suggested mitigation. Do not attach private portraits, API tokens, model
credentials, or third-party data. You should receive an acknowledgement
within seven days.

## Model and workflow safety

The download helper accepts model URLs and checksums only from the committed
`models.json`. Every downloaded file is size- and SHA-256-verified before it is
installed. Review changes to that manifest carefully. ComfyUI, third-party
models, and user-installed nodes have their own security policies and must be
kept current independently.
