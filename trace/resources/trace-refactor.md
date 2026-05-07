# trace-refactor.md

Specialist for **refactor** traces: restructuring, extraction, simplification,
decoupling, reorganization.

Read `trace-core.md` first. This file adds refactor-specific analysis, a
clarification curriculum, and the output shape on top of the shared protocol.

---

## What Good Input Looks Like

`/trace` assumes its input has been refined upstream. This section describes
what a well-formed refactor input looks like — useful as reference material
for the `/refine` skill, and as a self-check if a trace's migration plan
comes out vague.

Refactor inputs are the most often vague at the source; the dimensions below
are where refinement adds the most value.

A good refactor input answers (or makes obvious) these dimensions, in rough
order of how much they shape the trace:

1. **Tolerance for breaking changes** — internal-only vs. public/cross-repo
   interfaces fair game. Determines whether the migration plan needs
   deprecation phases.
2. **Increment size** — small independently-shippable steps vs. single large
   change acceptable. Determines whether the plan is a sequence of PRs or one.
3. **Behavior preservation** — pure refactor (behavior identical) vs. refactor
   with intentional behavior changes (and which changes). The validation
   strategy is completely different in each case.
4. **Trigger** — what's prompting the refactor: a specific pain point, a
   pattern that broke down, an upcoming feature that doesn't fit. Often
   surfaces constraints not otherwise stated.
5. **Test coverage assumption** — whether tests already cover the affected
   code, or whether characterization tests need to be added first. Affects
   sequencing.
6. **Out of scope** — adjacent code that should explicitly not be touched.
   Prevents scope creep.

If `/trace` proceeds with a refactor input missing these dimensions, the
migration plan will be best-effort — likely picking conservative defaults
(internal-only, incremental, behavior-preserving) and noting the assumptions
in the Risk Assessment.

---

## Research Focus

The goal is a migration plan that moves the codebase from its current state to a
cleaner target state, incrementally, without breaking existing behavior.

### Step 1 — Accurately describe the current state

Before prescribing anything, trace the current shape of what's being refactored:

- What does the code currently do?
- What are the structural problems? (Coupling, duplication, missing abstraction,
  wrong layer, too large, etc.)
- What are the callers and dependents? Load context files to enumerate usage.
  HIGH context sections naming dependents are authoritative; do not re-derive.
- Are there tests covering the current behavior? (Critical — behavior must be
  preserved unless the refactor explicitly includes changing it.)

Do not skip this step. A refactor plan built on a wrong current-state model
produces a migration that breaks things.

### Step 2 — Define the target state

Describe the desired end state precisely:

- What does the structure look like after the refactor?
- What abstractions exist that don't exist now?
- What is deleted? What is moved? What is split?
- What contracts change at the boundary (interface signatures, event shapes, etc.)?

The target state must be consistent with the codebase's architectural conventions
(per Agent Rules in context files). Refactors that introduce new patterns
should note the deviation explicitly. Refactors that violate `ALWAYS` rules in
Agent Rules require an explicit "and here's why we're breaking this rule"
justification — or the design is wrong.

### Step 3 — Sequence the migration

A refactor must be deliverable incrementally wherever possible:

1. **Preparatory moves** — renames, file relocations, adding new abstractions
   alongside old ones (expand phase).
2. **Migration moves** — callers updated one at a time to use the new structure.
3. **Cleanup moves** — old code deleted once all callers are migrated (contract
   phase).

If the refactor cannot be incremental (e.g., a schema rename that requires an
atomic migration), say so explicitly and explain why.

### Step 4 — Assess risk

- What breaks if a step is done incorrectly?
- What existing tests cover the affected code?
- Are there callers outside the traced scope (other repos, external consumers)
  that the context map suggests might be affected?
- Does this touch a shared library or cross-repo contract?

---

## Output Shape

```markdown
# Refactor: [short name]

**Trace:** [refactor summary] · refactor · via [context files]

## Current State
<!-- confidence: <CONF> -->

[Accurate description of what exists now — structure, responsibilities,
problems. Cite the key files.]

`path/to/file.ext:LINE` — [what's here and why it's a problem]

**Problems identified:**
- [structural problem]: [why it matters]

## Target State
<!-- confidence: <CONF> -->

[Description of the desired end state after the refactor. What the structure
looks like, what abstractions exist, what is gone.]

## Migration Plan
<!-- confidence: <CONF> -->

### Phase 1 — Prepare (non-breaking)
1. [Step] — `path/to/file.ext` — [what and why]
2. ...

### Phase 2 — Migrate (callers updated)
1. [Step] — `path/to/file.ext` — [what and why]
2. ...

### Phase 3 — Clean up (old code removed)
1. [Step] — `path/to/file.ext` — [what and why]

## Interface Changes
<!-- confidence: <CONF> -->

[If public interfaces change, describe before/after.]

| Symbol | Before | After | Callers Affected |
|--------|--------|-------|-----------------|
| `FuncName` | `(x T) R` | `(x T, y U) R` | `path/to/caller.ext` |

## Risk Assessment
<!-- confidence: <CONF> -->

- **[Risk]** — [mitigation]
- **Tests at risk:** [list test files that cover the affected code]
- **Cannot be incremental:** [if true, explain why and what the atomic step is]

> ⚠️ LOW confidence on [X] — verify at `path/to/file.ext`.  ← include only if needed

## Staleness Notes
<!-- confidence: HIGH -->

[Required only if any consulted scope was `warned`. List the warned scopes and
which claims were downgraded as a result.]

Overall: <CONF> (<N> HIGH, <M> MEDIUM, <K> LOW)
```

Required sections: `Current State`, `Target State`, `Migration Plan`,
`Risk Assessment`. `Interface Changes` is optional. Omit any optional content
with nothing useful to say. Do not pad.

The `Overall` line is required.
