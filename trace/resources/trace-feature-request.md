# trace-feature-request.md

Specialist for **feature** traces: new capabilities, enhancements, integrations.

Read `trace-core.md` first. This file adds feature-specific design research, a
clarification curriculum, and the output shape on top of the shared protocol.

---

## What Good Input Looks Like

`/trace` assumes its input has been refined upstream. This section describes
what a well-formed feature input looks like — useful as reference material
for the `/refine` skill, and as a self-check if a trace's design comes out
sprawling or under-specified.

A good feature input answers (or makes obvious) these dimensions, in rough
order of how much they shape the trace:

1. **Scope boundary** — what is explicitly out of scope. The most valuable
   dimension; without an explicit boundary, design proposals sprawl.
2. **Existing-pattern preference** — whether the feature should follow the
   existing pattern for similar features in this codebase, or whether a
   different shape is acceptable. Default assumption: follow existing pattern.
3. **Migration vs greenfield** — whether the feature must coexist with
   existing behavior, or is a clean replacement. Determines whether the
   design includes feature flags, dual-write, or deprecation paths.
4. **Cross-repo scope** — when the feature touches a cross-repo contract,
   whether the design includes changes to the other repo or treats that as
   a follow-up. Significantly changes the trace shape.
5. **Performance / scale targets** — throughput, latency, data-volume
   constraints. Default: match existing behavior.
6. **User-visible behavior** — for user-facing features, the desired UX
   including edge cases (empty states, errors, permissions).

If `/trace` proceeds with a feature input missing these dimensions, it
designs for the most reasonable interpretation, notes assumptions
explicitly, and the Overall confidence reflects the inferences made.

Some dimensions are not always relevant: scale targets don't matter for a
flag-toggle feature.

---

## Research Focus

The goal is a technical design that fits cleanly into the existing codebase —
using its patterns, respecting its boundaries, and not inventing new conventions
where existing ones apply.

### Step 1 — Understand the existing shape

Before designing anything, load the context files for the relevant subsystem(s)
and read both the prose and the **Agent Rules section explicitly**:

- What architectural pattern does this codebase use? (Layered, hexagonal,
  event-driven, etc.)
- What conventions govern how new features are added in this layer?
- What `ALWAYS` / `NEVER` rules apply to the kind of change being designed?
- Are there existing features of similar shape to model from?

The Agent Rules sections are **authoritative**. A design that violates an
`ALWAYS` rule from a relevant subsystem is invalid. A design that introduces
a pattern not in use anywhere else must explicitly justify the deviation.

### Step 2 — Identify insertion points

For the new feature, determine:

| Concern | Question |
|---------|----------|
| API surface | Where is the new endpoint/event/command declared and registered? |
| Handler/controller | Where does request handling live for this domain? |
| Service/domain logic | Which service owns this behavior? Does a new one need to be created? |
| Persistence | What data needs to be stored or queried? Is the schema sufficient? |
| Cross-repo | Does this touch a contract or shared lib? What changes there? |

Cite the specific files and layers for each insertion point. Use HIGH-confidence
context citations directly when available.

### Step 3 — Define interfaces and data shapes

For every new boundary:
- What are the input types?
- What are the output types?
- What are the error cases?
- What invariants must be preserved?

Ground these in existing types and conventions from the context files where
possible.

### Step 4 — Assess risks and open questions

- Does this require a schema migration?
- Does it touch a shared interface that other callers depend on?
- Are there performance implications (new query patterns, new external calls)?
- Are there security implications (new auth checks, new data exposure)?
- What is explicitly out of scope for this design?

---

## Output Shape

```markdown
# Feature: [short name]

**Trace:** [feature summary] · feature · via [context files]

## Design Summary
<!-- confidence: <CONF> -->

[2–3 sentence plain-language description of the approach and why it fits this
codebase.]

## Insertion Points
<!-- confidence: <CONF> -->

| Layer | File | What Changes |
|-------|------|-------------|
| API declaration | `path/to/routes.ext:LINE` | Add route X |
| Handler | `path/to/handler.ext` | New handler function |
| Service | `path/to/service.ext` | New method on ExistingService |
| Persistence | `path/to/repo.ext` | New query |
| Schema | `migrations/` | New migration (see below) |

## Interface Contracts
<!-- confidence: <CONF> -->

### [New Interface/Method Name]

```
Input:  { field: type, ... }
Output: { field: type, ... }
Errors: [ErrorType] — when [condition]
```

## Schema Changes
<!-- confidence: <CONF> -->

[If applicable: describe the migration. Table name, new columns, indexes,
constraints.]
> Follow the migration conventions at `migrations/` — per `.context/$REPO/context.md`.

## Implementation Sequence
<!-- confidence: <CONF> -->

[Ordered steps for implementing without breaking the existing system. Designed
for incremental delivery where possible.]

1. [Step] — `path/to/file.ext`
2. [Step] — `path/to/file.ext`
...

## Risks & Open Questions
<!-- confidence: <CONF> -->

- **[Risk]** — [mitigation or decision needed]
- **Out of scope:** [what this design explicitly does not cover]

> ⚠️ LOW confidence on [X] — verify at `path/to/file.ext`.  ← include only if needed

## Staleness Notes
<!-- confidence: HIGH -->

[Required only if any consulted scope was `warned`. List the warned scopes and
which claims were downgraded as a result.]

Overall: <CONF> (<N> HIGH, <M> MEDIUM, <K> LOW)
```

Required sections: `Design Summary`, `Insertion Points`, `Interface Contracts`,
`Implementation Sequence`, `Risks & Open Questions`. `Schema Changes` is
optional. Omit any optional content with nothing useful to say. Do not pad.

The `Overall` line is required.
