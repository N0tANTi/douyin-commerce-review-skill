# 2026-10-20 — v0.2 refinement

Review of the first private trial found lengthy actions, weak task selection and dependencies, implicit business assumptions, mixed task/effect acceptance and no structured feedback path. Corrected these in the reusable Skill and revised the private plan using the same snapshot; no new operating results are implied.

Added decision schema v2 with stable IDs, same-shop acyclic dependencies, source-backed highlights, deliverables, experiment unknowns and a focused report. Preserved v1 rendering/replay. Feedback verifies plan binding and local evidence files while explicitly leaving outcome truth and causal attribution to business review.

Rewrote README around business use, three copyable prompts and a fully synthetic runnable demo. Added behavioral regression tests for action structure, reference/dependency errors, feedback proof/tampering, HTML safety and documented usage. Validation: 41 tests passed; old and new private reports replayed; Skill structure and public payload checked.

Updated [state](../../CURRENT_STATE.md), [roadmap](../../ROADMAP.md) and [runbook](../runbooks/local-review.md). Source synchronized to the existing public repository and local installation refreshed. Real data, private plans and reports remain excluded. Native export adapters, financial cohorts and actual action evaluation are still pending.
