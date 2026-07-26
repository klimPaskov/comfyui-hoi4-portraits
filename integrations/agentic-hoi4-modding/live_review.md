# Generic agentic HOI4 live review

No live target repository was discoverable in the workspace or the planning
package. The generic integration remains a portable package with explicit
patch templates and complete new-file replacements. It must be applied only
after the parent agent supplies and reads the actual target repository. Every
custom subagent route is specified with `fork_context=false`; the parent owns
final wiring and live-consumer validation.

