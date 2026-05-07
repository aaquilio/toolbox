# trace-bug-fix.md

Specialist for **bug** traces: error reports, wrong behavior, regressions, exceptions.

Read `trace-core.md` first. This file adds bug-specific diagnosis, a clarification
curriculum, and the output shape on top of the shared protocol.

---

## What Good Input Looks Like

`/trace` assumes its input has been refined upstream. This section describes
what a well-formed bug input looks like — useful as reference material for the
`/refine` skill, and as a self-check if a trace's diagnosis comes out shallow.

A good bug input answers (or makes obvious) these dimensions, in rough order
of how much they shape the trace:

1. **Observable symptom and "fixed" definition** — what observable behavior
   indicates it's broken, and what observable behavior would indicate it's
   fixed. This is the most valuable dimension; it tells the trace what
   hypothesis to test.
2. **Reproducer** — concrete inputs, environment, or sequence that triggers
   the bug. Concrete reproducers produce sharper traces than abstract
   descriptions.
3. **When it started** — was it working before, and what changed recently?
   Recent regressions narrow the search to recent diffs.
4. **Frequency and conditions** — always vs. sometimes; under specific load,
   environments, or users. Distinguishes deterministic logic bugs from race
   conditions and environment issues.
5. **What's already been tried** — hypotheses ruled out, investigations
   already done. Prevents re-treading dead ends.

If `/trace` proceeds with a bug input missing these dimensions, the diagnosis
will be best-effort — likely identifying a plausible fault zone but not
necessarily the actual root cause. The Overall confidence will reflect that.

Some inputs are already self-explanatory: "AuthError on every login since the
v2.3 deploy" carries the symptom, the frequency, and the timing.

---

## Research Focus

The goal is a root-cause diagnosis and a precise fix design — not a workaround,
not a symptom patch.

### Step 1 — Reproduce the mental model

Before tracing code, construct the expected behavior from context:

- What _should_ happen according to the context files and API contracts?
- What _is_ happening according to the bug description?
- Where is the delta?

This gives you a hypothesis to test with the trace, not just a code reading
exercise.

### Step 2 — Locate the fault zone

Use the context map to narrow to the layer(s) where the delta is most likely
introduced:

- **Input validation layer** — wrong input accepted or correct input rejected
- **Business logic layer** — correct input, wrong transformation
- **Persistence layer** — correct logic, wrong read/write
- **Integration layer** — correct internal behavior, wrong external interaction
- **Infrastructure layer** — config, env, deployment mismatch

Load only the subsystem context files for the suspected layer(s). When a HIGH
context section names a specific file as the home of the relevant logic, jump
directly to it; do not re-derive locations.

### Step 3 — Trace the bug path

Follow the steel-thread protocol from `trace-core.md`, focused on the fault
zone:

1. Trace from the entry point to where the fault is introduced.
2. Identify the exact line or block where behavior diverges from expectation.
3. Check: is this a logic error, a missing guard, a wrong assumption about an
   API, a race condition, or an environment issue?

### Step 4 — Check for side effects

Before proposing a fix:
- What else calls the faulty code? (Look for usages in context files.)
- Could fixing it here break a different caller?
- Is there a test that currently passes but relies on the wrong behavior?
- Does the relevant subsystem's Agent Rules section govern how this kind of
  fix should be made?

---

## Output Shape

```markdown
# Bug: [short name]

**Trace:** [bug summary] · bug · via [context files]

## Diagnosis
<!-- confidence: <CONF> -->

[2–3 sentence plain-language statement of what is wrong and why.]

## Root Cause
<!-- confidence: <CONF> -->

[The specific code location and mechanism of the fault, with citation.]
`path/to/file.ext:LINE`

**Expected:** [what should happen at this point]
**Actual:** [what happens instead]

## Fix Design
<!-- confidence: <CONF> -->

[Precise description of the change needed. Not pseudocode unless the change
is complex enough to warrant it — prefer "change X to Y at path:LINE".]

### Changes Required

| File | Location | Change |
|------|----------|--------|
| `path/to/file.ext` | Line N | [description] |

## Side Effects & Risks
<!-- confidence: <CONF> -->

[What else could be affected by this fix. Be specific.]
- [risk or side effect] — `path/to/affected/file.ext`

## Verification
<!-- confidence: <CONF> -->

[How to confirm the fix works: what to test, what to observe, what a passing
state looks like. Reference existing test files if relevant.]

> ⚠️ LOW confidence on [X] — verify at `path/to/file.ext`.  ← include only if needed

## Staleness Notes
<!-- confidence: HIGH -->

[Required only if any consulted scope was `warned`. List the warned scopes and
which claims were downgraded as a result.]

Overall: <CONF> (<N> HIGH, <M> MEDIUM, <K> LOW)
```

Required sections: `Diagnosis`, `Root Cause`, `Fix Design`, `Side Effects & Risks`,
`Verification`. Omit any optional content with nothing useful to say. Do not pad.

The `Overall` line is required.
