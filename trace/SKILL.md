---
name: trace
description: >
  Traces a technical input — question, bug, feature request, or refactoring target —
  through the project's .context/ map to produce a focused, expert-grade technical
  response without loading unnecessary code.

  Use this skill whenever the user asks:
  - how something works in the codebase
  - to diagnose or fix a bug
  - to design a new feature or enhancement
  - to plan a refactor or restructuring
  - to understand a system, flow, or behavior

  Trigger on phrasings like: "how does X work", "why is Y broken", "I want to add Z",
  "help me refactor W", "trace through the auth flow", "where should I make this
  change", "design this for me", or any question implying codebase-grounded
  technical investigation.

  Optionally consumes: .context/ artifacts produced by /build-context-map (recommended).
  If absent, runs a slower source-only trace and recommends running /build-context-map.

  Modifiers (interpreted from natural language or explicit flags):
    --question | --bug | --feature | --refactor   override input-type classification
    --file                                         write output to .context/traces/<slug>.md
    --auto-revision                                auto-apply only safe validator findings
    --refresh-stale                                Smart-Update stale .context/ scopes before tracing
    --no-context                                   skip .context/ entirely; trace from source only
---

# Trace

Produces a focused, codebase-grounded technical response by navigating the
`.context/` map, tracing only the relevant steel-threads into the code, and
validating the result with deterministic and LLM checks before delivering.

The skill is **schema-aware**: it reads the structured signals in `.context/`
artifacts (front-matter, section confidence, citations, Agent Rules) and uses
them as a fast-path index, not as decorative prose.

---

## Skill Bundle

This skill ships with these supporting resources, which the orchestrator and
specialists MUST use:

- **`resources/trace-core.md`** — shared protocols loaded by every specialist.
- **`resources/trace-question.md`** / **`trace-bug-fix.md`** /
  **`trace-feature-request.md`** / **`trace-refactor.md`** — type-specific
  research procedure and output shape.
- **`resources/trace-schema.json`** — JSON Schema for trace artifact
  front-matter and structural rules.
- **`scripts/validate-trace.py`** — stdlib-only deterministic validator. Run as
  Phase 4a before the LLM validator.

If `.context/` exists, the orchestrator may also invoke
`${BUILD_CONTEXT_MAP_SKILL_DIR}/scripts/validate.py` (from the upstream skill)
in Phase 0b for a health check.

---

## Quick Reference

| Modifier | Effect |
|----------|--------|
| `--question` | Force question mode |
| `--bug` | Force bug-fix mode |
| `--feature` | Force feature-request mode |
| `--refactor` | Force refactor mode |
| `--file` | Write final output to `.context/traces/<slug>.md` |
| `--auto-revision` | Auto-apply only safe validator findings (citation, confidence) |
| `--refresh-stale` | Run Smart Update on stale scopes via `/build-context-map` before tracing |
| `--no-context` | Skip `.context/` entirely; trace from source only |

These can be passed as literal flags or expressed in natural language ("just do a
quick trace from source," "refresh the context first," etc.). The orchestrator
interprets either form.

---

## Phase 0 — Prerequisites

### 0a. Check for `.context/`

- **Present and `--no-context` not set** → continue to 0b.
- **Absent** → soft-fail:

  > I don't see a `.context/` directory. I can run a slower trace by reading
  > source directly, or you can run `/build-context-map` first for a faster,
  > more comprehensive trace. Which would you prefer?

  If the user opts for source-only, treat this as `--no-context` and skip to
  Phase 1. Note in the trace front-matter that no context was used.

- **`--no-context` set** → skip to Phase 1.

### 0b. Health-check `.context/`

If `.context/` is present, run the upstream validator (best-effort):

```bash
python3 ${BUILD_CONTEXT_MAP_SKILL_DIR}/scripts/validate.py .context/ \
  --repo-root <each repo> --json
```

If the validator is not available (skill not installed, path not known), skip
this check silently. If the validator runs and reports issues:

- **Critical issues** (missing `map.md`, broken front-matter on `map.md`):
  treat as if `.context/` were absent (soft-fail in 0a).
- **Non-critical issues** (stale citations, missing index entries on a
  subsystem): proceed but record the issues in the trace front-matter under
  a notes field surfaced to the user at the end.

The trace skill does not attempt to fix `.context/` issues. That's
`/build-context-map`'s job.

### 0c. Staleness detection

For each repo whose `.context/$REPO/context.md` will be loaded:

```bash
CONTEXT_COMMIT=$(extract 'commit' from .context/$REPO/context.md front-matter)
HEAD_COMMIT=$(git -C <repo> rev-parse HEAD)
```

If `CONTEXT_COMMIT == HEAD_COMMIT`: state = `fresh`.

If they differ, compute the impacted file set:

```bash
git -C <repo> diff --name-only $CONTEXT_COMMIT..HEAD
```

For each subsystem `context.md` whose `scope` directory intersects the changed
files, the subsystem state = `warned`. For subsystems with no overlap, the
subsystem state = `fresh` (the context is technically older but nothing
relevant changed).

**Default behavior under any `warned` state:** proceed with the trace. The
specialist downgrades claims sourced from `warned` scopes per `trace-core.md`.
The output includes a "Staleness Notes" section.

**Under `--refresh-stale`:** before continuing, invoke
`/build-context-map` in Smart Update mode targeting the warned scopes.
On success, re-read the affected `context.md` files and set state =
`refreshed`. On failure, fall back to `warned` behavior and tell the user.

Record the per-repo staleness state for the trace front-matter:

```yaml
context_commit_alignment:
  <repo>:
    context_commit: <hash>
    head_commit: <hash>
    staleness: fresh | warned | refreshed
```

---

## Phase 1 — Classify Input

The input has already been refined upstream (see the `/refine` skill). Trace
assumes its input is well-formed and proceeds without confirmation.

### 1a. Check for explicit modifier

If `--question`, `--bug`, `--feature`, or `--refactor` is present (literally or
as natural-language signal: "treat this as a refactor"), use it. Proceed
without confirmation.

### 1b. Classify

If no modifier is present, read the input and produce a single classification:
`question`, `bug`, `feature`, or `refactor`. Use judgment, not keyword matching
— inputs like "why does the auth middleware reject valid tokens" contain
"valid" but are clearly bugs, while "I want to understand why X is broken" is
a question.

Proceed without confirmation. The classification appears in the trace
preamble (e.g. `**Trace:** ... · bug · via ...`), so the user sees it in the
output. If the classification is wrong, the user can re-run with an explicit
flag.

---

## Phase 2 — Context Map Exploration

### 2a. Load `map.md`

Load `.context/map.md`. Do not load any repo or subsystem `context.md` files
yet. Skip this if `--no-context` is set.

From `map.md`, identify:
- Which repo(s) are likely relevant to the input
- Which subsystem(s) within those repos are plausible starting points
- Any cross-repo contracts that may be involved

Form a **preliminary scope hypothesis**: a short list of `context.md` files to
load next, ranked by relevance.

### 2b. Check for prior traces

If `.context/traces/` exists:
1. Load `.context/traces/index.md` if present (lightweight summary of past
   traces — paths, inputs, types, dates).
2. Look for prior traces that overlap with the current input by topic.
3. If the current input is clearly a continuation ("now design the rotation
   feature for the JWT refresh you traced yesterday"), surface the candidate:

   > I see a prior trace that may be relevant: `.context/traces/<slug>.md`.
   > Should I treat this as a continuation, or as a fresh trace?

4. If the user accepts continuation, load the prior trace as additional context
   and record `prior_trace_consulted` and `depends_on` in the new trace
   front-matter.

Cap continuations at 2 prior traces. More than that, the input is too broad to
be a continuation.

---

## Phase 3 — Deep Research

Now load context files and trace into the code. Follow the specialist file for
the classified input type:

| Type | Specialist |
|------|-----------|
| `question` | `resources/trace-question.md` |
| `bug` | `resources/trace-bug-fix.md` |
| `feature` | `resources/trace-feature-request.md` |
| `refactor` | `resources/trace-refactor.md` |

Read that file now and follow its instructions. It will reference
`resources/trace-core.md` for shared research patterns, schema-aware reading
rules, and citation discipline.

Specialists exploit the schema:
- HIGH sections in fresh `context.md` files are trusted; their citations are
  used directly without re-derivation.
- MEDIUM sections are starting points; HIGH-grade trace claims require source
  verification.
- LOW sections require source re-derivation.
- `warned` scopes downgrade everything by one level.
- Agent Rules sections are loaded explicitly for feature and refactor traces.

---

## Phase 4 — Validation (two-stage)

### 4a. Deterministic validation

After producing a draft trace, run:

```bash
python3 ${SKILL_DIR}/scripts/validate-trace.py <draft_path> \
  --repo-root <repo1> [--repo-root <repo2> ...] \
  --json
```

This catches:
- Missing or malformed front-matter
- Missing required sections per input type
- Section confidence annotations missing
- HIGH sections without citations
- Broken `path:line` citations (file missing, line out of range)
- Missing/malformed Overall summary
- Missing Staleness Notes when staleness was detected

If the deterministic validator returns non-zero, fix all findings (they are
mechanical) before proceeding to 5b. Do not present these findings to the user
under `--auto-revision`; they are always auto-fixed.

### 4b. LLM validator

Once deterministic checks pass, dispatch a **validator subagent** per the
contract in `resources/trace-core.md` (Phase 4b section).

The LLM validator receives:
- The draft response (cold — no conversation history)
- The input that prompted it
- The input type
- The list of files consulted
- The staleness summary
- The list of prior traces consulted

The LLM validator does NOT re-check what the deterministic validator already
checked. Its scope:
- Internal consistency
- Input alignment (does it answer what was asked)
- Confidence calibration (uncertain claims flagged as such)
- Coverage adequacy (did it miss a relevant subsystem)
- Type-specific checks (root cause for bugs, Agent Rules respect for features
  and refactors, etc.)

### Show and Revise (default)

Present the LLM validator's feedback to the user before revising:

> **Validator feedback:**
> [feedback summary]
>
> Revising now based on the above.

Then revise and deliver the final output.

### Auto-Revision (`--auto-revision`)

Auto-revision applies automatically to:
- All deterministic validator findings (mechanical fixes)
- LLM findings tagged `[confidence]` (label calibration)

LLM findings tagged `[consistency]`, `[alignment]`, `[coverage]`, or
`[type:*]` are surfaced to the user even with `--auto-revision`. These need
user judgment.

### When the skill cannot resolve a validator concern

Do not loop. Do not pretend the validator is an independent intelligence the
skill can disagree with. Be honest:

> I'm uncertain about [specific point]. The validator flagged that [concern].
> My current claim is [claim] based on [basis]. I cannot resolve this without
> [source reading / user input / updated context map]. How would you like to
> proceed?

---

## Phase 5 — Output

See the specialist file for exact output shape. Common rules:

- Default: write to terminal.
- `--file`: write to `.context/traces/<slug>.md` where `<slug>` is a kebab-case
  summary of the input (e.g. `how-does-auth-work.md`). Report the path to the
  user.
- Front-matter fields are populated per `resources/trace-schema.json`.
- Cite every source file referenced: `path/to/file.ext:LINE` or `:LINE-LINE`.
- Do not include context or source content that wasn't needed for the response.
- The Overall confidence summary line is required.
- If `--file` was used, append/update an entry in `.context/traces/index.md`
  with the new trace's path, input, type, and date.

---

## Reporting

After delivery, the orchestrator briefly reports:

- Mode (with-context / source-only / context-refreshed)
- Files consulted (count by kind)
- Validator outcome (deterministic + LLM verdicts)
- Any staleness warnings carried into the trace
- Any prior traces consulted
- Path to written trace if `--file` was used

The skill does not claim the trace is correct. It reports which checks passed.
Correctness is established by use.
