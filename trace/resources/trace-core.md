# trace-core.md

Shared protocols for all trace specialist files. Every specialist reads this file
and follows the contracts below.

The trace skill consumes `.context/` artifacts produced by `/build-context-map`.
Those artifacts are **structured** — front-matter, section confidence, inline
citations — and trace exploits that structure for both speed and correctness.

---

## Schema-Aware Reading

Every `.context/` `context.md` and `map.md` carries machine-readable signals.
Trace honors them; do not treat these files as ordinary prose.

### Front-matter signals

Each file begins with YAML front-matter. The following fields drive trace behavior:

| Field | Effect on trace |
|-------|-----------------|
| `commit` | Compared against current repo HEAD for staleness detection (Phase 0c) |
| `confidence` (file-level) | Sets a ceiling on claims derived from this file's prose |
| `analyzer_version` | Mismatch with current `/build-context-map` version → flag possible schema drift |
| `review_depth` | `none` or `per_scope` is a weaker artifact than `full`; downstream claims default to MEDIUM |
| `scope` | The path the file describes; resolves citation relative paths |
| `origin` (or `origins:` for `map.md`) | Lets the trace verify the right repo is on disk |

### Section confidence signals

Every section heading is followed by `<!-- confidence: HIGH | MEDIUM | LOW -->`.

| Section confidence | Trace behavior |
|--------------------|----------------|
| **HIGH** | Trust the section's claims as-is. Use cited `path:line` references directly without re-deriving them. |
| **MEDIUM** | Treat as a starting point. Verify any claim before promoting it to HIGH in the trace output. |
| **LOW** | Re-derive from source. Do not rely on the section's claims without independent verification. |

A trace claim's confidence is bounded by the floor of:
1. The section confidence in the source `context.md`,
2. The file-level confidence in the source `context.md`,
3. The trace's own verification (whether source was independently re-read).

### Citations as a fast-path index

`context.md` files contain `path:LINE` citations inline. These are the **fast path**:
when a `context.md` says "JWT validation lives at `internal/auth/jwt.go:55-90`," the
trace treats that as the answer to "where does JWT validation happen?" — provided
the section is HIGH and the file is fresh.

Treat `path:LINE` citations in `.context/` as authoritative under those conditions.
Do not re-derive locations the upstream artifact has already established.

### Agent Rules sections

Every `context.md` contains a `## Agent Rules` section with `ALWAYS` / `NEVER` /
`PREFER` / `CHECK` / `NOTE` entries. These are **authoritative for design and
refactor traces.**

- **Feature traces** MUST load and apply Agent Rules from every relevant
  subsystem `context.md`. A design that violates an `ALWAYS` rule is invalid by
  construction.
- **Refactor traces** MUST verify the proposed target state against Agent Rules.
  Refactors that introduce new patterns must explicitly note the deviation.
- **Bug and question traces** consult Agent Rules when relevant but are not
  bound by them.

---

## Context Loading Protocol

Load context files **on demand** in this order. Stop loading when you have enough
to produce a precise response.

1. `.context/map.md` — already loaded in Phase 2. Do not reload.
2. `.context/$REPO/context.md` — load for each relevant repo identified in Phase 2.
3. `.context/$REPO/$SUBSYSTEM/context.md` — load only subsystems the repo context
   points you toward for this specific input.
4. **Source files** — read directly only when:
   - A specific claim needs verification before it can be made HIGH in the output
   - A specific implementation detail must be cited
   - A `context.md` section is MEDIUM or LOW and a HIGH-grade claim is needed
   - Staleness was detected for the relevant scope (Phase 0c)
5. **Prior traces** — see *Consulting Prior Traces* below.

Read the minimum range needed (`file:LINE-LINE` not the full file). Source reads
are cited in the trace output's `files_consulted`.

**Never** speculatively load files. Every load must be motivated by a specific gap
that the already-loaded context cannot close.

Record every file you load. This list is passed to the validator and stored in
the trace front-matter.

---

## Staleness Handling

The orchestrator is responsible for staleness detection (see SKILL.md Phase 0c).
This section defines how specialists react to the orchestrator's findings.

### Staleness states (from Phase 0c)

| State | What it means | Specialist response |
|-------|---------------|---------------------|
| `fresh` | `commit` field equals current HEAD | Trust context normally |
| `warned` | `commit` differs from HEAD AND a relevant subsystem was touched in the diff | Downgrade derived claims; re-verify from source |
| `refreshed` | Smart Update was run during Phase 0c | Trust context normally |

### Behavior under `warned`

When any consulted scope is `warned`:

1. Every claim sourced from a `warned` scope's `context.md` is downgraded one
   level (HIGH → MEDIUM, MEDIUM → LOW, LOW → drop or re-derive from source).
2. Citations in `warned` scopes are re-checked against current source. If the
   cited file/line no longer matches, drop the citation and either re-derive
   or mark the claim LOW.
3. The trace output MUST include a "Staleness Notes" section listing the
   warned scopes, the diff-impacted areas, and any claims that were downgraded
   or re-derived as a result.

### Behavior under `--refresh-stale`

If the user passed `--refresh-stale`, Phase 0c invoked Smart Update and the state
is `refreshed`. Specialists treat this as `fresh`. The trace output records the
refresh in `context_commit_alignment` so downstream readers know the context
was refreshed mid-trace.

---

## Citation Rules

Every factual claim about the codebase must be grounded:

- **HIGH confidence** — claim is directly verifiable from source AND the citation
  was either (a) re-derived from source by the trace, or (b) inherited from a
  HIGH section of a `fresh` `context.md`. Cite as `` `path/to/file.ext:LINE` ``
  or `` `path/to/file.ext:LINE-LINE` ``.
- **MEDIUM confidence** — inferred from patterns, MEDIUM context-file claims, or
  partial evidence. Note as "per `.context/$REPO/context.md`" or "based on
  [pattern]".
- **LOW confidence** — best-effort or uncertain. Flag explicitly:
  `> ⚠️ LOW confidence — verify before acting on this.`

Do not present MEDIUM or LOW claims as certain. Be explicit about the basis.

Every `path:LINE` citation in the output MUST resolve at the recorded
`head_commit`. The deterministic validator (Phase 4a) checks this before the
LLM validator runs.

---

## Steel-Thread Tracing

A steel-thread trace follows a single concern from entry point to resolution.

### How to trace

1. Identify the entry point from the input (API endpoint, function, event, UI action).
2. Use `.context/` citations to jump to the entry point directly when possible
   (HIGH section in fresh context = no need to grep).
3. Follow the call chain: handler → service → domain → persistence, or equivalent
   for the codebase's architecture (per `.context/$REPO/context.md`).
4. At each layer, note: what the layer does, what it passes down, what it returns.
5. Stop when you reach the boundary relevant to the input (e.g., for a bug: the
   layer where the fault is most likely introduced).
6. Do not trace layers that aren't relevant. A bug in the auth layer doesn't
   require tracing the payment layer.

### When to go wide

If the input spans multiple subsystems or repos, trace each thread separately,
then synthesize at the cross-boundary points. Cross-repo contracts in `map.md`
are the bridges; load them when crossing.

---

## Consulting Prior Traces

Saved traces (`.context/traces/*.md`) are first-class context. The orchestrator
maintains an index at `.context/traces/index.md` if any traces exist.

### When to consult

- The current input references a prior topic ("now design refresh-token rotation"
  after an earlier "how does JWT refresh work" trace).
- The current input is a follow-up that continues an investigation ("the bug
  we discussed yesterday — fix it").
- The orchestrator's prior-trace check (Phase 2b) surfaced a candidate.

### Loading rules

1. Read `.context/traces/index.md` if present (single small file).
2. Identify candidate prior traces by topic match.
3. Load at most 2 prior traces. More than that and the current input should be
   reclassified as a new trace, not a continuation.
4. **Check prior trace freshness**: a prior trace's `context_commit_alignment`
   records the commit per repo at the time. If current HEAD differs and the
   diff overlaps the prior trace's `files_consulted`, the prior trace is stale.
   Treat its claims as MEDIUM at best.

### Recording the relationship

If a prior trace was used, the new trace's front-matter sets:

```yaml
prior_trace_consulted: .context/traces/<prior>.md
depends_on:
  - .context/traces/<prior>.md
```

The new trace's preamble line acknowledges it: "extends `<prior>.md`".

---

## Document-Level Confidence Summary

Every trace ends with an Overall summary on its own line:

```
Overall: <CONF> (<N> HIGH, <M> MEDIUM, <K> LOW)
```

Where:
- `<CONF>` is the document-level confidence: HIGH if the majority of citation-bearing
  claims are HIGH and no LOW claims are central; MEDIUM if the trace materially relies
  on inferences; LOW if staleness or unresolved gaps mean the trace is exploratory.
- `<N>`, `<M>`, `<K>` count the section-level confidence annotations in the document.

This summary is checked by `scripts/validate-trace.py`.

---

## Phase 4a — Deterministic Validation

Before the LLM validator runs, the orchestrator invokes the deterministic
validator:

```bash
python3 ${SKILL_DIR}/scripts/validate-trace.py <draft_path> \
  --repo-root <repo1> [--repo-root <repo2> ...] \
  --json
```

The deterministic validator checks the things that are mechanically checkable:

- Front-matter present, well-formed, all required fields, no unknown fields
- Preamble line matches the required format
- Required sections present for the input type
- Every section heading has a confidence annotation
- Every HIGH section contains at least one citation
- Every `path:line` citation resolves on disk in the recorded `head_commit`
- Overall summary line present and well-formed
- Staleness notes present iff any scope was `warned`

Findings are returned as JSON. The orchestrator must fix all deterministic
findings before invoking the LLM validator. There is no judgment to be made
on these — broken citations are broken, missing sections are missing.

---

## Phase 4b — LLM Validator Contract

The LLM validator is invoked **after** deterministic validation passes. It is an
independent subagent with no conversation history, no specialist reasoning, and
no clarification-loop transcript. It receives only:

**Inputs:**
- `input`: the original user input verbatim
- `input_type`: question | bug | feature | refactor
- `draft_response`: the full draft response text
- `files_consulted`: list of context files and source files loaded during research
- `staleness_summary`: which scopes were warned/refreshed
- `prior_traces_used`: list of prior trace paths consulted (if any)

The LLM validator does NOT check what the deterministic validator already checked
(citation resolution, section structure, required sections). Its job is the
LLM-shaped checks:

**Validator checklist (all types):**

1. **Internal consistency** — does the response contradict itself?
2. **Input alignment** — does the response actually address the input? Flag tangents
   or gaps.
3. **Confidence calibration** — are LOW/MEDIUM claims flagged appropriately, or are
   uncertain claims presented as definite?
4. **Coverage adequacy** — does the trace cover the input's scope, or did it miss
   a relevant subsystem mentioned in `map.md`?

**Type-specific additions** — load the relevant section below:

### question — additional checks
- Is the explanation complete enough to be actionable?
- Are code references sufficient to let the reader find the implementation?

### bug — additional checks
- Is a root cause identified, not just symptoms?
- Does the proposed fix address the root cause and not just mask the symptom?
- Are side effects or risk areas noted?

### feature — additional checks
- Are insertion points specific (file + layer)?
- Are interface contracts and data shapes defined?
- Are risks and open questions surfaced?
- Do design choices respect the Agent Rules from the relevant `context.md` files?

### refactor — additional checks
- Is current-state accurately described before prescribing change?
- Is the migration path sequenced (can it be done incrementally)?
- Are risks of the refactor noted?
- Does the target state respect Agent Rules, or does it explicitly note deviations?

**Validator output format:**

```
VERDICT: PASS | REVISE

## Issues (if VERDICT: REVISE)
- [consistency] <claim A> contradicts <claim B>
- [alignment] <gap> — input asked about X but response doesn't address Y
- [confidence] <claim> — presented as certain but basis is unclear
- [coverage] <subsystem> — relevant per map.md but not addressed
- [type:<input_type>] <type-specific finding>

## Minor notes (does not block PASS)
- ...
```

The trace skill acts on `REVISE` verdicts. `PASS` verdicts with minor notes are
surfaced to the user only if `--auto-revision` is not set.

---

## Auto-Revision Gating

`--auto-revision` does NOT silently apply all validator findings. It auto-applies
only:

- Deterministic findings from Phase 4a (always; these are mechanical)
- LLM findings tagged `[confidence]` (label corrections — downgrading an
  over-confident claim is safe)

LLM findings tagged `[consistency]`, `[alignment]`, `[coverage]`, or
`[type:*]` are surfaced to the user even with `--auto-revision`. These need
user judgment — "you missed addressing the cache layer" is not the kind of
thing to auto-fix without confirmation.

---

## When the Skill Cannot Resolve a Validator Concern

If the LLM validator flags an issue and the trace skill cannot satisfy it (the
context truly does not support the claim, or the validator is mistaken), do not
loop and do not pretend the validator and the skill are separate intelligences.

State the situation honestly to the user:

> I'm uncertain about [specific point]. The validator flagged that [concern].
> My current claim is [claim] based on [basis]. I cannot resolve this without
> [what would be needed: more source reading, user input, an updated context
> map]. How would you like to proceed?

This replaces the older "validator and I disagree" framing. The reality is one
model with two prompts; an honest "I'm uncertain" is more accurate than
performing a disagreement.

---

## Output Preamble (all types)

Every response begins, after the H1 title, with a one-line preamble:

```
**Trace:** [input summary] · [type] · via [list of context files used]
```

If a prior trace was consulted, append: ` · extends [prior trace path]`.

Example:

```
**Trace:** how does JWT refresh work · question · via `.context/map.md`,
`.context/api/context.md`, `.context/api/auth/context.md`
```

This preamble is part of both terminal and `--file` output, and is required by
`validate-trace.py`.
