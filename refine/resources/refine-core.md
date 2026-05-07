# refine-core.md

Shared protocols for all `/refine` specialist files. Every specialist reads
this file before executing its type-specific logic.

---

## Input Classification Protocol

Classify the input into exactly one of four types. Use judgment, not keyword
matching.

| Type | Signal |
|------|--------|
| `question` | The user wants to understand something. "How does X work", "what is Y", "explain Z", "walk me through". No change is being requested. |
| `bug` | Observable behavior is wrong. Something is broken, erroring, or behaving differently than expected. The goal is diagnosis and fix. |
| `feature` | A new capability is being added. Something that doesn't exist yet (or a meaningful extension of something that does). |
| `refactor` | Existing behavior is preserved but structure changes. Restructuring, extraction, simplification, decoupling. No new capability. |

**Ambiguous cases:**

- "Why is X broken AND how should we redesign it" → ask the user to split.
  These are a bug trace and a feature/refactor trace respectively.
- "Add X but also fix the broken Y while we're there" → ask which one to
  refine first. `/trace` handles one concern at a time.
- "Improve performance of X" → usually `refactor` unless a new approach
  (caching layer, different algorithm, new dependency) is being introduced,
  in which case `feature`.
- "Update X to work with the new Y" → `feature` if Y is new infrastructure;
  `bug` if X *should* already work with Y.

When classifying, state the classification and a one-sentence rationale.
Do not ask the user to confirm unless the input is genuinely ambiguous between
two types after careful reading.

---

## Context Map Grounding Protocol

When `.context/` is present, use it actively during gap analysis and the
challenge loop. Do not treat it as background reading — use it to surface
contradictions and sharpen questions.

### Loading order

1. `.context/map.md` — loaded in Phase 0a of the orchestrator. Use it to:
   - Identify which repos and subsystems are relevant to the input.
   - Detect when the user refers to a subsystem by a vague name ("the auth
     service") that maps to multiple concrete components.
   - Identify cross-repo contracts that might affect the trace.
2. `.context/$REPO/context.md` — load on demand when a dimension involves
   a structural claim about a specific repo. Load only the relevant repo's
   context, not all repos.
3. `.context/$REPO/$SUBSYSTEM/context.md` — load on demand when a dimension
   involves a specific subsystem.

**Never speculatively load context files.** Every load must be motivated by
a specific dimension that requires grounding.

### Context-contradicted dimensions

A context-contradicted dimension is one where the user's input makes a claim
or assumption that the context map or a context file contradicts. Examples:

- User says "the JWT validation in the API service" but the context map shows
  JWT validation lives in the gateway service, not the API service.
- User says "this is a simple change to one file" but the context map shows
  the affected subsystem has 12 callers across 3 repos.
- User says "there are no existing tests for this" but the subsystem
  `context.md` lists a test suite covering the relevant code.

Context-contradicted dimensions take priority over simple missing dimensions
in the challenge queue. The user has a wrong mental model; correcting it is
more valuable than filling a missing detail.

**How to challenge a contradiction:**

> "The context map shows [concrete fact from context]. Your input assumes
> [what the user said]. These are in conflict — [explain why it matters for
> the trace]. [Ask the question that resolves it]."

Do not soften contradictions. The point of `/refine` is to surface them.

### Staleness and round-trip re-challenge

When a refined artifact is passed back through `/refine` and `.context/`
commit differs from the artifact's `context_commit`:

1. Compute `git diff --name-only <artifact_context_commit>..HEAD`.
2. For each changed file, identify which dimensions (if any) it could affect.
3. Re-challenge only those dimensions. All others are treated as resolved.
4. If no dimensions are affected by the changed files, treat as a silent
   round-trip pass.

---

## Challenge Loop Protocol

The challenge loop is `/refine`'s core mechanism. It is not a conversation —
it is a structured interrogation with a defined end condition.

### Format for each challenge

```
**[Dimension name]**

[One sentence stating why this dimension matters for the trace — what goes
wrong if /trace has to guess at it.]

[If context-contradicted: state the contradiction explicitly, citing the
context map.]

[The question. Direct and specific. Not "can you tell me more about X?" but
"which of these is your goal: A or B?"]

[Optional: 2–3 options with tradeoffs, when the answer space is bounded and
tradeoffs are meaningful. Not a menu to pick from — an aid to thinking.]
```

### One question at a time

Ask exactly one question per turn. Wait for the answer. Re-assess the queue
before asking the next question — the answer may resolve other dimensions.

### Infer before asking

Before queuing a dimension for challenge, ask: can I infer this from the
input or from prior answers? If yes, infer and record in `dimensions_assumed`.
Only ask when inference would require a guess that could materially change
the trace.

### After each answer

1. Record the answer against the dimension.
2. Re-assess remaining queued dimensions — does this answer resolve any of them?
3. If the answer reveals a new gap not in the original queue, add it.
4. Ask the next question, or terminate the loop.

### Loop termination conditions

**Resolution:** All queued dimensions are answered or inferable. Proceed to
Phase 4 (assembly).

**Hard-stop — input too broad:** The input spans multiple independent concerns
that cannot be unified into a single coherent trace input. The user cannot
narrow it within the challenge loop because the breadth is fundamental to
how they've framed the goal. See Hard-Stop Protocol below.

**Hard-stop — goal underspecified beyond recovery:** The user's answers
reveal they don't yet have enough information to specify the goal (e.g., "I
don't know what the expected behavior should be" for a bug, or "we haven't
decided the scope yet" for a feature). Refinement cannot proceed without
information the user doesn't have. See Hard-Stop Protocol below.

**Hard-stop — type conflict:** Answers reveal the input is simultaneously two
different trace types (e.g., "fix the bug AND redesign the module"). Ask the
user to split. If they decline, hard-stop.

---

## Hard-Stop Protocol

A hard-stop means `/refine` will not emit a refined input. This is not a
failure — it is the correct output when the input cannot be made tractable.

Hard-stops are rare. Exhaust the challenge loop before concluding one is
needed.

### When to hard-stop

- **Too broad:** The input, even with all dimensions answered, would require
  `/trace` to produce a multi-day design document rather than a focused trace.
  A trace has a single steel thread; an input that requires 5 steel threads
  is 5 trace inputs.
- **Underspecified beyond recovery:** The user lacks information that is
  prerequisite to specifying the goal. They need to do discovery (read code,
  talk to stakeholders, run the system) before `/refine` can help.
- **Type conflict unresolvable:** The input is two traces and the user will
  not split them.

### Hard-stop output

State clearly:
1. **Why** the input can't be made tractable. Be specific — not "this is too
   vague" but "this input requires resolving three independent architectural
   questions that each merit their own trace."
2. **What the user needs to do** before returning to `/refine`. Concrete
   actions, not abstract advice.
3. **How to split** if the input contains multiple valid trace concerns.
   Give the user the decomposition — what would the two (or three) focused
   inputs look like?

---

## Refined Input Assembly Protocol

Once all dimensions are resolved, assemble the refined input.

### Preservation of user voice

The refined input reads like the user wrote it — just with the ambiguities
resolved and the gaps filled. Do not rewrite their concern in your voice.
Do not add jargon they didn't use. Do not change their framing unless it
was demonstrably wrong (context-contradicted).

### Structure

The refined input is a prose paragraph or short set of paragraphs. It is not
a form or a list of answers. It reads naturally. The dimensions are woven in,
not enumerated.

A reader coming cold to the refined input should understand:
- What the concern is
- What the boundaries are
- What success looks like
- What constraints apply
- Which part of the codebase is in scope

### What to record in the artifact

- `original_input`: verbatim user text (the raw input before any clarification)
- `refined_input`: the assembled refined input
- `input_type`: the classified type
- `dimensions_addressed`: dimensions that were explicitly answered
- `dimensions_assumed`: dimensions where a default was inferred (with the
  inference stated)
- `clarifications`: the Q&A pairs from the challenge loop, in order
- `context_commit`: the HEAD commit of each relevant repo at refinement time
  (only if `.context/` was present)

### Round-trip safety check

Before emitting, mentally pass the refined input back through the gap analysis
for its type. If any dimension would be re-queued for challenge, the assembly
is incomplete — revise before emitting.

---

## Phase 5b — LLM Validator Contract

The LLM validator is an isolated subagent. It receives no conversation history
and no challenge loop transcript. Cold inputs only.

**Inputs to the validator:**
- `original_input`: verbatim raw input
- `refined_input`: the assembled refined input
- `input_type`: question | bug | feature | refactor
- `dimensions_addressed`: list
- `dimensions_assumed`: list with inferred values
- `context_available`: true | false

**Validator checklist:**

1. **Completeness** — does the refined input address all dimensions for its
   type? List any that are absent or still ambiguous.
2. **Assumption audit** — for each dimension in `dimensions_assumed`, is the
   inference reasonable? Would a different reasonable inference materially
   change the trace? If yes, flag it — the question should have been asked.
3. **Round-trip safety** — would this refined input, passed back to `/refine`,
   yield zero clarifying questions? If not, identify which dimensions would
   be re-challenged.
4. **Voice preservation** — does the refined input sound like the user or like
   the skill? Flag if it has been over-rewritten.
5. **Tractability** — is this input scoped such that `/trace` can produce a
   focused steel-thread response? Or is it still too broad?

**Validator output format:**

```
VERDICT: PASS | REVISE

## Issues (if VERDICT: REVISE)
- [completeness] <dimension> — still missing or ambiguous
- [assumption] <dimension> — inference '<value>' is a material guess; should have been asked
- [round-trip] <dimension> — would be re-challenged on round-trip
- [voice] <description> — over-rewritten
- [tractability] <description> — still too broad for a focused trace

## Minor notes (does not block PASS)
- ...
```

On `REVISE`, re-enter the challenge loop for the flagged dimensions only.
On `PASS`, proceed to Phase 6 output.
