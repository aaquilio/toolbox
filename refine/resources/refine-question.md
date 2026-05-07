# refine-question.md

Specialist for refining **question** inputs: "how does X work", "what is Y",
"explain Z", "walk me through".

Read `refine-core.md` first. This file adds question-specific dimensions,
challenge ordering, and the refined-input output shape.

---

## Dimensions (in priority order)

These are the axes on which a question input must be unambiguous before
`/trace` can produce a focused response. Challenge in this order, skipping
dimensions that are already answered or cleanly inferable.

### 1. Scope boundary *(highest priority)*

**What it is:** How narrow or broad is the question? Is the user asking about
one entry point and its immediate behavior, or the full system flow end-to-end
including error paths, retries, async behavior?

**Why it matters:** An ambiguous scope produces a trace that's either too
shallow (if the tracer picks narrow) or sprawling and unfocused (if it picks
broad). This is the single dimension most likely to cause a misaligned trace.

**How to challenge:**
> "How does [X] work" could mean [narrow interpretation] or [broad
> interpretation]. A narrow trace covers [describe]; a broad trace covers
> [describe] and would be substantially longer. Which scope do you need?

If `.context/` is available, use `map.md` to name the specific subsystems
or repos that a broad scope would include — this makes the tradeoff concrete.

**Context grounding:** If the user names a component that the context map
shows is actually multiple components, surface the ambiguity:
> "The context map shows [X] is split across [subsystem A] and [subsystem B].
> Which one (or both) do you mean?"

---

### 2. Audience depth

**What it is:** Does the user want a high-level mechanism explanation (how
the pieces fit together, what each layer does) or a line-by-line walkthrough
with specific code citations?

**Why it matters:** Determines how deeply `/trace` digs into source. A
high-level answer skips implementation detail; a deep walkthrough cites
specific functions and follows the call chain precisely.

**How to challenge:**
> "Are you looking for a high-level understanding of how [X] is structured,
> or do you need to follow the actual code path with specific file and line
> references?"

**Inference signal:** If the user says "I need to understand this before
making a change" → lean toward deep. If they say "explain this to my team"
or "give me an overview" → lean toward high-level. Infer if the signal is
clear; ask if it isn't.

---

### 3. Specific subsystem

**What it is:** When the topic touches multiple repos or subsystems, which
ones are in scope?

**Why it matters:** "How does auth work" could span a gateway service,
an auth service, a shared JWT library, and a session store. Without knowing
which parts the user cares about, the trace either over-covers (loads all of
them) or under-covers (picks one arbitrarily).

**How to challenge:**
> "This touches [list subsystems from context map, or from the input].
> Which of these are you asking about — all of them, or a specific part?"

**Context grounding:** If `.context/` is present, use `map.md` to enumerate
the concrete components. Do not ask the user to name subsystems from memory —
surface the options from the map.

**Skip if:** The question names a specific enough component that subsystem
scope is clear. "How does JWT validation in the API gateway work" does not
need subsystem clarification.

---

## Challenge Budget

Minimum: 1 question (scope boundary almost always needs asking).
Typical: 1–2 questions.
Maximum: all three dimensions if none are clear from the input.

Questions are bounded by what's needed, not by the budget. If all three
dimensions are inferable, ask zero questions.

---

## Output Shape for Refined Question Input

The refined input is a well-scoped question that makes the following
explicit (woven into prose, not listed):

- **What** is being asked about (specific enough to identify the right
  subsystem or component)
- **How deep** the answer should go (high-level or code-level)
- **What scope** is in or out (narrow or broad, with specifics)

### Example structure

```
[Specific component or system], [scope qualifier]. [What the user wants
to understand]. [Any constraints on the answer — level of detail, what
to include or exclude]. [Optional: why they're asking, if it shapes the
trace.]
```

### Example

**Before (raw):**
> How does auth work?

**After (refined):**
> How does JWT validation work in the API gateway service specifically —
> I want a code-level walkthrough of the validation path from when a
> request arrives to when the claim is trusted (or rejected). I'm not
> asking about token issuance or the session store, just the validation
> step. I need enough detail to know where to add a new claim check.

---

## Hard-Stop Triggers for Questions

Hard-stop if the question, even after all three dimensions are resolved,
remains a survey question that would require `/trace` to produce a
document covering 5+ independent subsystems or flows. In that case:

> "This is a survey of [system], not a question about a specific mechanism.
> `/trace` works best on focused questions. Here are [N] more tractable
> questions this breaks into: [list]. Pick the one closest to your actual
> need."
