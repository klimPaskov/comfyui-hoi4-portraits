# Background Candidate Review

The live Chaos Redux checkout contains one plausible portrait-background
candidate at `gfx/leaders/portrait_leader_background.psd`. Its SHA-256 is
`4c9f9ab945fda0d74912684d0ce17a777b0b08838528cdba53afd901134bc8d6` and its
tracked Git blob is `cd770b69f01d5c47f79d1d5baf30a6e455086109` at repository
HEAD `420cfb326e8ec78ec5641b152f32fce2b2d94db6`.

It remains `BLOCKED_RIGHTS_UNRESOLVED`. The local checkout is at
`420cfb326e8ec78ec5641b152f32fce2b2d94db6`, while the current primary remote
master is `276ea88b959c0b1833c414476f3d9c69bf5a41ba`. The remote PSD was
verified read-only and matches the local artifact byte-for-byte, but the
remote repository root contains no `LICENSE`, `COPYING`, or `NOTICE` record.
`descriptor.mod` is only a mod descriptor, and the PSD is not yet an approved
runtime background artifact. It has therefore not been copied, converted,
added to the registry, or used by any workflow. The live checkout's unrelated
untracked paths were preserved.

Machine-readable evidence: `docs/preflight/background_candidates.json`.
