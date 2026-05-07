# refine-refactor.md

Specialist for refining **refactor** inputs: restructuring, extraction,
simplification, decoupling, reorganization — where existing behavior is
preserved (or intentionally changed, and the changes are specified).

Read `refine-core.md` first. This file adds refactor-specific dimensions,
challenge ordering, and the refined-input output shape.

---

## Dimensions (in priority order)

### 1. Tolerance for breaking changes *(highest priority)*

**What it is:** Are public or cross-repo interfaces fair game to change, or
is the refactor constrained to internal-only changes?

**Why it matters:** Determines whether the migration plan needs deprecation
phases, versioned APIs, cross-repo coordination, or consumer migration. A
refactor that changes public interfaces is an order of magnitude more complex
than one that doesn't. This is the most important scoping decision.

**How to challenge:**
> "Can this refactor change public or cross-repo interfaces, or is it
> constrained to internal-only changes? If interfaces can change, are
> consumers expected to migrate, and on what timeline?"

**Context grounding:** If `.context/` is present, use the context map to
enumerate which interfaces are cross-repo contracts. Name them explicitly:
> "The context map shows [component X] has external consumers in [repo Y]
> and [repo Z]. Are those interfaces in scope for change, or is this
> refactor internal to [this repo/subsystem] only?"

Do not let the user be vague here. "We'll deal with breaking changes as
they come up" is not an answer.

---

### 2. Increment size

**What it is:** Must the refactor be delivered as small, independently
shippable steps, or is a single large change acceptable?

**Why it matters:** Determines whether the migration plan is a sequence of
PRs (each mergeable and safe on its own) or one large changeset. Incremental
delivery reduces risk but requires more planning. Single large change is
faster but riskier.

**How to challenge:**
> "Does this refactor need to be delivered incrementally — small PRs each
> safe to merge independently — or is a single large change acceptable?
> Is there a timeline or release constraint driving this?"

**Inference signal:** If the affected code is large (many files, many
callers) and the user hasn't said "do it all at once," default to
incremental and state that assumption. Ask only if there's ambiguity or
the user signals a preference.

---

### 3. Behavior preservation

**What it is:** Is this a pure refactor (behavior identical before and
after), or does it include intentional behavior changes — and if so, which?

**Why it matters:** The validation strategy is completely different. A pure
refactor can be validated by running existing tests unchanged. A refactor
with behavior changes requires specifying which behaviors change and why,
so the trace can design the migration to handle both the structural move
and the semantic change.

**How to challenge:**
> "Is this a pure refactor — behavior identical before and after — or does
> it include intentional behavior changes? If there are intentional changes,
> what are they specifically?"

This question has zero tolerance for vagueness. "Mostly the same behavior"
is not an answer. Either behavior is identical or there are specific named
changes.

**Context grounding:** If the context map or a subsystem `context.md` lists
test coverage for the affected code, surface it:
> "The context map shows [test suite X] covers [this subsystem]. If behavior
> is changing, those tests will need to be updated — which tests should
> change vs. which should remain as regression guards?"

---

### 4. Trigger

**What it is:** What is prompting this refactor — a specific pain point, a
pattern that broke down, an upcoming feature that doesn't fit?

**Why it matters:** The trigger often surfaces implicit constraints not
otherwise stated. "We need to refactor this because feature X won't fit"
implies the target state must accommodate feature X. "This is too slow"
implies performance is a constraint on the target state.

**How to challenge:**
> "What's driving this refactor — what's the specific problem with the
> current structure that this fixes? Is there an upcoming change or feature
> that the current structure can't accommodate?"

**Skip if:** The trigger is stated explicitly in the input and is specific
enough to be useful ("the current monolith makes it impossible to test
the payment layer independently").

---

### 5. Test coverage assumption

**What it is:** Do tests already cover the affected code, or do
characterization tests need to be added before the refactor begins?

**Why it matters:** A refactor without test coverage is high-risk. If tests
don't exist, the migration plan must include adding them first — otherwise
the refactor has no safety net. This affects sequencing significantly.

**How to challenge:**
> "Is the code being refactored covered by existing tests that would catch
> regressions? Or do characterization tests need to be added first to
> establish a safety net?"

**Context grounding:** If the subsystem `context.md` is available and lists
test coverage, use it rather than asking. State what you found:
> "The context map shows [this subsystem] has [test coverage description].
> I'll assume that provides the safety net unless you tell me otherwise."

---

### 6. Out of scope

**What it is:** Adjacent code that should explicitly not be touched, even if
it's tempting or adjacent to the refactor target.

**Why it matters:** Prevents scope creep. Refactors that grow to include
"while we're in here" changes are the ones that fail review, get stuck in
merge conflicts, or introduce unintended regressions.

**How to challenge:**
> "What's explicitly out of scope — adjacent code or concerns that should
> not be touched in this refactor, even if they're nearby or related?"

**Inference signal:** If the input already names a specific target (e.g.,
"refactor the auth middleware"), infer that adjacent but non-auth code is
out of scope. Only ask if the input is broad enough that the out-of-scope
boundary is genuinely unclear.

---

## Challenge Budget

Minimum: 2 questions (breaking changes and behavior preservation almost
always need explicit answers).
Typical: 3–4 questions.
Maximum: all six dimensions.

Refactor inputs are the most likely to contain assumptions the user hasn't
examined. Push harder than you might for other types — particularly on
breaking changes and behavior preservation. These are the two dimensions
where vague answers produce dangerous migration plans.

---

## Output Shape for Refined Refactor Input

The refined input makes the following explicit (woven into prose):

- **What is being refactored** — specific component, module, or pattern
- **Why** — the trigger and the problem with current state
- **Breaking change tolerance** — internal only or interfaces fair game
- **Increment strategy** — incremental PRs or single change
- **Behavior preservation** — pure or with specific named changes
- **Test coverage** — exists or must be added first
- **Out of scope** — explicit boundary

### Example

**Before (raw):**
> Refactor the auth middleware.

**After (refined):**
> Refactor the auth middleware in the API gateway to extract token
> validation into a standalone `TokenValidator` interface, decoupling it
> from the HTTP layer so it can be unit tested independently. Trigger:
> the current structure makes it impossible to test validation logic
> without spinning up an HTTP server. This is an internal-only refactor —
> the public middleware interface (the function signature that route
> handlers call) must not change; this is not the time to change how
> callers register middleware. Deliver incrementally: add the
> `TokenValidator` interface alongside the existing code first, migrate
> the internal logic to use it, then delete the old code. Pure behavior
> preservation — no semantic changes. The existing integration tests in
> `tests/auth/` cover the current behavior and must continue passing
> unchanged. Out of scope: OAuth token validation (separate middleware),
> rate limiting middleware, and any changes to the session store.

---

## Hard-Stop Triggers for Refactors

Hard-stop if:

- After the behavior preservation challenge, the user cannot specify which
  behaviors change. If behavior is changing but they can't say how, they
  need to do design work first.
  > "A refactor with unspecified behavior changes is a redesign in disguise.
  > Clarify which behaviors are changing and how, then return to /refine.
  > If the behavior changes are substantial, this may be a feature trace
  > rather than a refactor."

- The scope, even after challenge, spans the entire codebase or multiple
  large subsystems simultaneously.
  > "This refactor as described touches [list]. That's a multi-quarter
  > architectural migration, not a single trace. Break it into [N] focused
  > refactor traces by subsystem or phase: [list]. Start with the one that
  > unblocks the most."
