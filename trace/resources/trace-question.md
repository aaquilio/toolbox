# trace-question.md

Specialist for **question** traces: "how does X work", "what is Y", "walk me through Z".

Read `trace-core.md` first. This file adds question-specific research focus, a
clarification curriculum, and the output shape on top of the shared protocol.

---

## What Good Input Looks Like

`/trace` assumes its input has been refined upstream. This section describes
what a well-formed question input looks like — useful as reference material
for the `/refine` skill, and as a self-check if a trace surfaces ambiguity.

A good question input answers (or makes obvious) these dimensions, in rough
order of how much they shape the trace:

1. **Scope boundary** — narrow ("the entry-point version of this") vs. broad
   ("the full system flow including async retries"). Ambiguous between the two
   produces a trace that's either too shallow or too sprawling.
2. **Audience depth** — high-level mechanism vs. line-by-line walkthrough.
   Determines how deep the citations go.
3. **Specific subsystem** — when the topic touches multiple repos or subsystems
   per `map.md`, which ones are in scope. "How does auth work" is broader than
   "how does JWT validation work in the API gateway."

If `/trace` proceeds with a question that's ambiguous on these dimensions, it
will pick a reasonable interpretation and announce it in the response. The
user can re-run with a refined input if the interpretation was wrong.

---

## Research Focus

The goal is a complete, accurate explanation of how something works — grounded in
the actual code, not generic descriptions.

### What to trace

1. **Locate the entry point** — where does the thing being asked about begin?
   (An API handler, an event, a scheduled job, a UI action, a library call.)
   When the relevant `context.md` section is HIGH and fresh, jump directly to
   the citation; do not re-derive the entry point.
2. **Trace the happy path** — follow the main execution thread from entry to
   completion. Note each layer's responsibility and what it passes to the next.
3. **Note key decision points** — conditionals, configuration-driven branches,
   or feature flags that alter behavior.
4. **Identify data shapes** — what does the input look like? What does the output
   look like? Where are the schemas or types defined?
5. **Surface non-obvious behavior** — caching, retries, async patterns, ordering
   constraints, side effects.

### When to go deeper

- If the question asks "why" (not just "how"), also look for: git history signals
  in the context file, ADR references, or TODO/NOTE comments near the relevant
  code.
- If the question involves a cross-repo interaction, trace both sides of the
  boundary.

### What to skip

- Error paths, unless the question is specifically about error handling.
- Unrelated subsystems the thread passes through but doesn't meaningfully
  interact with.

---

## Output Shape

```markdown
# How [X] Works

**Trace:** [input summary] · question · via [context files]

## How [X] Works
<!-- confidence: <CONF> -->

[2–3 sentence plain-language summary of the mechanism.]

## Entry Point
<!-- confidence: <CONF> -->

[Where it starts, with citation.]

## Flow
<!-- confidence: <CONF> -->

1. **[Layer/Step]** — [what happens]. `path/to/file.ext:LINE`
2. **[Layer/Step]** — [what happens]. `path/to/file.ext:LINE`
...

## Key Data Shapes
<!-- confidence: <CONF> -->

[Relevant types, schemas, or interfaces, with citations.]

## Non-Obvious Behavior
<!-- confidence: <CONF> -->

[Anything that would surprise a new engineer: caching, async, ordering, flags.]
> ⚠️ LOW confidence on [X] — verify at `path/to/file.ext`.  ← include only if needed

## Where to Look Next
<!-- confidence: <CONF> -->

[2–4 specific files or functions for the reader to explore if they want to go
deeper. Not exhaustive — just the highest-value next stops.]

## Staleness Notes
<!-- confidence: HIGH -->

[Required only if any consulted scope was `warned`. List the warned scopes and
which claims were downgraded as a result.]

Overall: <CONF> (<N> HIGH, <M> MEDIUM, <K> LOW)
```

Required sections: `How [X] Works`, `Entry Point`, `Flow`. Other sections are
optional — omit any that have nothing useful to say. Do not pad.

The `Overall` line is required.
