---
name: refine
description: >
  Critically interrogates a raw technical input — question, bug report, feature
  request, or refactor target — until it is unambiguous and ready to hand to
  /trace. Does not produce a trace; produces a refined input that /trace can
  consume without guessing at scope, intent, or constraints.

  Use this skill whenever:
  - The user says "refine my input", "help me clarify this", "I'm not sure how
    to phrase this", "before I trace this I want to get it right"
  - The user has a vague or broad technical input and wants to sharpen it
  - A prior /trace returned low confidence or misaligned output — the input
    likely needed refinement first
  - The user is unsure which trace type applies to their input
  - The user says "challenge me on this", "poke holes in this", "what am I
    missing", "is this well-scoped"

  Trigger on phrasings like: "refine this", "help me clarify", "is this
  well-scoped", "I want to trace X but I'm not sure how to frame it",
  "what do I need to know before I trace this", "my trace came out wrong",
  or any input that is clearly a precursor to a /trace run.

  Modifiers (interpreted from natural language or explicit flags):
    --question | --bug | --feature | --refactor   override input-type classification
    --file                                         save refined input to
                                                   .context/refinements/<slug>.md
---

# Refine

Critically interrogates a raw technical input and drives it to an unambiguous,
traceable form — or hard-stops with a diagnosis if the input can't be made
tractable. The user does not control when the loop ends; `/refine` does.

---

## Skill Bundle

- **`resources/refine-core.md`** — shared protocols: classification, challenge
  loop, context-map grounding, hard-stop rules, LLM validator contract.
- **`resources/refine-question.md`** — question-type dimensions, challenge
  order, output shape.
- **`resources/refine-bug.md`** — bug-type dimensions, challenge order, output
  shape.
- **`resources/refine-feature.md`** — feature-type dimensions, challenge order,
  output shape.
- **`resources/refine-refactor.md`** — refactor-type dimensions, challenge
  order, output shape.
- **`resources/refine-schema.json`** — JSON Schema for refined-input artifact
  front-matter.
- **`scripts/validate-refine.py`** — stdlib-only deterministic validator.

---

## Quick Reference

| Modifier | Effect |
|----------|--------|
| `--question` | Force question mode |
| `--bug` | Force bug mode |
| `--feature` | Force feature mode |
| `--refactor` | Force refactor mode |
| `--file` | Save refined input to `.context/refinements/<slug>.md` |

---

## Phase 0 — Input Acceptance

Accept the raw input from the user. It may be a single sentence or several
paragraphs. Do not ask for more information yet.

### 0a. Check for `.context/`

- **Present:** Load `.context/map.md` now (lightweight — do not load repo or
  subsystem `context.md` files yet). Record that context-grounded challenge
  mode is active.
- **Absent:** Proceed in intent-only mode. Note in the artifact front-matter
  that no context map was available.

### 0b. Round-trip detection

If the input appears to already be a refined artifact (it has YAML front-matter
matching the refine schema, or it begins with the refinement preamble format),
treat it as a round-trip pass:

- **`.context/` absent or fresh (commit matches HEAD):** Emit the artifact
  immediately. State that the input is already well-formed and no clarification
  is needed.
- **`.context/` present and stale (commit differs from artifact's
  `context_commit`):** Compute the diff between the artifact's recorded commit
  and HEAD. Re-challenge only on dimensions the changed files could affect.
  If no dimensions are affected, treat as a fresh round-trip (silent pass).

---

## Phase 1 — Classify Input

Read `resources/refine-core.md` now. Follow the classification protocol there.

### 1a. Check for explicit modifier

If `--question`, `--bug`, `--feature`, or `--refactor` is present, use it.
Skip classification.

### 1b. Classify

Produce a single classification: `question`, `bug`, `feature`, or `refactor`.

If the input is genuinely ambiguous between two types and cannot be resolved
by reading it carefully, ask the user to pick before proceeding. This is the
one question `/refine` asks before the challenge loop. Do not classify
arbitrarily — a misclassified input produces a useless refinement.

State the classification to the user with a one-sentence rationale.

---

## Phase 2 — Gap Analysis

Load the specialist file for the classified type:

| Type | Specialist |
|------|-----------|
| `question` | `resources/refine-question.md` |
| `bug` | `resources/refine-bug.md` |
| `feature` | `resources/refine-feature.md` |
| `refactor` | `resources/refine-refactor.md` |

Read that file now. It lists the dimensions for that type in priority order.

For each dimension, assess the input:

- **Answered:** The input explicitly or obviously covers this dimension.
  Do not ask about it.
- **Inferable:** The answer is strongly implied by context. Record the
  inference; do not ask. Surface the inference in the artifact's
  `dimensions_assumed`.
- **Missing or ambiguous:** The dimension is absent or unclear. Queue it
  for the challenge loop, in priority order.
- **Context-contradicted:** The input makes a claim or assumption that
  `.context/map.md` (or a repo/subsystem `context.md` if needed) contradicts.
  Flag this as a higher-priority challenge than a simple gap — the user has
  a wrong mental model that must be corrected before refinement can proceed.

If `.context/` is present and a dimension involves a structural claim about the
codebase, load the relevant repo or subsystem `context.md` to ground the
challenge. Do not speculatively load context files — load only what is needed
to assess a specific dimension.

---

## Phase 3 — Challenge Loop

Follow the challenge loop protocol in `resources/refine-core.md`.

The loop is controlled by `/refine`, not the user. It runs until:

1. All queued dimensions are resolved (answered or inferable from answers
   given during the loop), **or**
2. A hard-stop condition is reached (see `refine-core.md`).

The user may volunteer information that resolves multiple dimensions at once.
Re-assess the queue after each answer before asking the next question.

**Never ask a question whose answer is already in the input or inferable from
prior answers.** Violating this erodes trust in the loop.

---

## Phase 4 — Assemble Refined Input

Once the loop terminates (all dimensions resolved), assemble the refined input
per the specialist's output shape. Follow the protocol in `refine-core.md`.

The refined input:
- Preserves the user's voice. It reads like the user wrote it, just clearer.
- Is self-contained. Someone reading it cold should understand the full scope,
  constraints, and intent without asking follow-up questions.
- Is typed. The input type is explicit in the artifact.
- Records all assumptions made for dimensions the user didn't address directly.

---

## Phase 5 — Validation (two-stage)

### 5a. Deterministic validation

Run:

```bash
python3 ${SKILL_DIR}/scripts/validate-refine.py <draft_path> \
  --input-type <type> \
  --json
```

Fix all findings before proceeding to 5b. These are mechanical — broken
structure, missing sections, malformed front-matter.

### 5b. LLM validator

Dispatch a validator subagent per the contract in `resources/refine-core.md`
(Phase 5b section). The subagent receives the refined input cold — no
conversation history, no challenge loop transcript.

The LLM validator checks:
- Does the refined input unambiguously answer all dimensions for its type?
- Would `/trace` be able to proceed without guessing at any of them?
- Is any assumption in `dimensions_assumed` a load-bearing one that should
  have been asked about instead?
- Round-trip check: would this input, if passed back to `/refine`, yield zero
  clarifying questions?

Present the validator's findings before revising. If the validator identifies
a gap, re-enter the challenge loop for that dimension only.

---

## Phase 6 — Output

### Default (terminal hand-back)

Present the refined input as a formatted block the user can copy and paste
directly into `/trace`. Precede it with a brief summary:

```
**Refined input** · <type> · <N> dimensions addressed, <M> assumed

[refined input text]

**Assumptions made:** [list of inferred dimensions and the values assumed]
**Ready for:** /trace
```

### `--file`

Write the artifact to `.context/refinements/<slug>.md` where `<slug>` is a
kebab-case summary of the input (e.g., `jwt-refresh-bug.md`). Report the path.

Append or update an entry in `.context/refinements/index.md` with the new
artifact's path, input type, original input summary, and date.

---

## Hard-Stop Output

If Phase 3 terminates with a hard-stop rather than resolution, do not emit a
refined input. Instead, produce:

```
**Refinement failed** · <type> · <reason>

**Why this input can't be made tractable:**
[clear diagnosis — what's fundamentally underspecified or too broad]

**How to rephrase:**
[concrete guidance — what the user needs to decide or discover before
returning to /refine]

**If the goal is actually two separate concerns:**
[split guidance — how to decompose into two refineable inputs]
```

---

## Reporting

After output, briefly report:
- Mode (intent-only / context-grounded)
- Dimensions addressed vs. assumed
- Validator verdict
- Path written if `--file` was used
- Whether a hard-stop occurred and why
