# Local agent Mac execution

The `agent_local_mac_16gb` workflow completed a private diagnostic run on the
public-domain Library of Congress fixture using the isolated CPU ComfyUI
server. The run used the job-contract prompt, not the human autoprompter.

- Canvas: 832×1120
- Krea steps: 8
- Sampler time: 34:24
- Prompt execution: 37:12
- Result: ComfyUI queue success
- Candidate: `jobs/local-agent-loc-cpu-full-08-01/candidates/candidate-000.png`
- Candidate SHA-256: `2258467b275a4097a4ff40e53ad4874808e880fe5a3c53fbee5b27ef2b240d42`
- Model: official checksum-verified NVFP4 artifact, CPU diagnostic substitution only

The candidate has one detected source face and one detected candidate face;
SFace similarity was `0.7120879607571169`. The independent auditor returned
`UNCERTAIN`, because the threshold registry is still fail-closed and the
landmark, pose, expression, accessory, mask-boundary, and style auditors are
not qualified. No final PNG, DDS, or mod integration output was created.

The private candidate and audit evidence remain ignored under the job root.
