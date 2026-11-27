# specs/

This repo follows a lightweight spec-driven-development convention, layered on top of the `/feature-dev` workflow (installed as a Claude Code plugin):

1. Run `/feature-dev <description>` for any real feature.
2. When Phase 1 (Discovery) lands on a clear understanding of what's being built, save it to `specs/<feature-slug>/spec.md` (what/why, acceptance criteria).
3. When Phase 4 (Architecture) lands on a chosen approach, save it to `specs/<feature-slug>/plan.md` (approach + rationale).
4. Track progress in `specs/<feature-slug>/tasks.md`, mirroring the phase's own todo list.

This gives every feature a short, durable record in the repo — future sessions (yours or a collaborator's) can read `specs/<feature-slug>/spec.md` instead of re-deriving requirements from scratch.

**Skip this for trivial, single-file changes** — the ceremony is for real features, not typo fixes.
