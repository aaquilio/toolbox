# refine-feature.md

Specialist for refining **feature** inputs: new capabilities, enhancements,
integrations, extensions of existing behavior.

Read `refine-core.md` first. This file adds feature-specific dimensions,
challenge ordering, and the refined-input output shape.

---

## Dimensions (in priority order)

### 1. Scope boundary *(highest priority)*

**What it is:** What is explicitly out of scope? What is explicitly in scope?

**Why it matters:** Without an explicit boundary, `/trace` design proposals
sprawl — they include adjacent concerns, try to solve follow-on problems, and
produce designs too large to implement in one pass. The out-of-scope list is
as important as the in-scope list.

**How to challenge:**
> "What's explicitly out of scope for this feature — what adjacent concerns
> should the design deliberately leave for later? And to confirm: what's the
> minimum the feature must do to be considered done?"

Push hard on this. "We'll figure out scope later" is not an answer.

**Context grounding:** If `.context/` is present, use `map.md` to surface
adjacent subsystems the feature might naturally touch:
> "This feature will interact with [subsystem A] and likely brush against
> [subsystem B] and [subsystem C]. Are B and C in scope or explicitly out?"

---

### 2. Existing-pattern preference

**What it is:** Should the feature follow the existing pattern for similar
features in this codebase, or is a different architectural shape acceptable?

**Why it matters:** If the codebase has a strong pattern for this kind of
feature and the user wants to deviate, `/trace` needs to know to justify
the deviation (and check Agent Rules). If they want to follow the pattern,
the design is largely constrained — which is useful information.

**How to challenge:**
> "Does this feature need to follow the existing pattern for [similar
> features in this codebase], or is a different approach acceptable? The
> existing pattern [briefly describe from context if available]."

**Default assumption:** Follow existing pattern. Only ask if the input
signals the user might want something different (e.g., "we should do this
differently than we did for X").

**Context grounding:** If `.context/` is present and a relevant subsystem
`context.md` is available, name the existing pattern explicitly. Don't ask
the user to describe it — you have it.

---

### 3. Migration vs. greenfield

**What it is:** Must the feature coexist with existing behavior (migration
path, feature flags, dual-write, deprecation), or is it a clean replacement?

**Why it matters:** Determines whether the design needs compatibility shims,
feature flags, dual-write periods, or deprecation paths — which significantly
changes scope and implementation sequence.

**How to challenge:**
> "Does this need to coexist with the existing behavior during rollout
> (i.e., some users/requests use old behavior, some use new), or is it a
> clean cutover? If coexistence is needed, what's the rollout strategy —
> feature flag, percentage rollout, something else?"

**Inference signal:** If the feature is new functionality with no existing
counterpart, this dimension is not applicable — note it and skip.

---

### 4. Cross-repo scope

**What it is:** If the feature touches a cross-repo contract or shared
interface, does the design include changes to the other repo, or is that
a follow-up?

**Why it matters:** A trace that includes cross-repo changes is substantially
larger and more complex than one that treats the other repo as a follow-up.
The trace needs to know the boundary.

**How to challenge:**
> "This feature touches [cross-repo contract from context map]. Does the
> design include changes to [other repo], or does this trace scope to
> [this repo] only and treat the other side as a follow-up?"

**Skip if:** The feature clearly lives within a single repo with no
cross-repo contracts involved.

---

### 5. Performance / scale targets

**What it is:** Are there specific throughput, latency, or data-volume
constraints the feature must meet?

**Why it matters:** A feature with no scale constraints is designed
differently than one that must handle 10x current load. Affects query
design, caching strategy, async vs. sync patterns.

**How to challenge:**
> "Are there specific performance requirements — throughput, latency, or
> data volume — that the design must account for? Or should it match the
> existing behavior of similar features?"

**Default assumption:** Match existing behavior. Only ask if the input
signals scale is a concern, or if the context map shows the relevant
subsystem has explicit performance constraints.

---

### 6. User-visible behavior

**What it is:** For user-facing features, what is the desired UX — including
edge cases, empty states, error states, and permission boundaries?

**Why it matters:** UX details determine interface contracts, error handling
requirements, and validation logic. A vague "the user should be able to do X"
produces a design that handles the happy path only.

**How to challenge:**
> "What should the user experience look like for the edge cases — what
> happens when [relevant edge case: empty state / no permission / error /
> concurrent access]? And what does 'done' look like from the user's
> perspective?"

**Skip if:** The feature is purely internal (no user-visible surface).

---

## Challenge Budget

Minimum: 2 questions (scope boundary and at least one other are almost
always needed for feature inputs).
Typical: 3–4 questions.
Maximum: all six dimensions if the input is high-level.

Feature inputs are the most likely to require the full challenge budget.
Do not rush to assembly — an underspecified feature input produces a
sprawling, low-confidence trace.

---

## Output Shape for Refined Feature Input

The refined input makes the following explicit (woven into prose):

- **What the feature does** — specific capability
- **In-scope boundary** — what must be done
- **Out-of-scope boundary** — what is explicitly deferred
- **Pattern preference** — follow existing or justify deviation
- **Migration strategy** — coexistence or clean cutover
- **Cross-repo scope** — included or deferred
- **Performance targets** — explicit or match-existing
- **User-visible behavior** — including edge cases (if applicable)

### Example

**Before (raw):**
> Add support for API key authentication.

**After (refined):**
> Add API key authentication to the API gateway as an alternative to JWT
> for machine-to-machine clients. In scope: key generation (admin-only),
> key validation on inbound requests, and associating a key with a service
> identity for authz. Out of scope: key rotation UI, rate-limiting by key,
> and analytics — those are follow-ups. The design should follow the existing
> auth middleware pattern (same shape as the OAuth middleware). This must
> coexist with JWT auth — no cutover, both methods must work simultaneously
> via a feature flag. The gateway repo only; changes to the auth service's
> identity model are a follow-up. Performance must match JWT validation
> latency (sub-5ms p99). Error behavior: invalid or missing keys return 401
> with the same error shape as JWT failures — no information leak about
> whether the key exists.

---

## Hard-Stop Triggers for Features

Hard-stop if:

- After scope challenge, the user cannot or will not define an out-of-scope
  boundary, and the feature as described would require `/trace` to design
  across 4+ subsystems simultaneously.
  > "This feature as described spans [list subsystems]. That's a system
  > design, not a feature trace. Break it into [N] separate feature traces,
  > each scoped to one subsystem or concern: [list]. Return to /refine
  > with one of them."

- The user's answers reveal the feature hasn't been decided yet — they're
  using `/refine` to figure out what to build, not to sharpen a decision
  already made.
  > "The design decisions that shape this feature (X, Y, Z) haven't been
  > made yet. /refine sharpens a decision you've made; it can't make the
  > decision for you. Once you've decided [X], return to /refine."
