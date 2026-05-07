# refine-bug.md

Specialist for refining **bug** inputs: error reports, wrong behavior,
regressions, exceptions, flaky behavior.

Read `refine-core.md` first. This file adds bug-specific dimensions,
challenge ordering, and the refined-input output shape.

---

## Dimensions (in priority order)

### 1. Observable symptom and "fixed" definition *(highest priority)*

**What it is:** What observable behavior proves it's broken? What observable
behavior would prove it's fixed?

**Why it matters:** This is the hypothesis `/trace` must test. Without a
concrete symptom, the trace has nothing to locate in the code. Without a
"fixed" definition, the fix design has no acceptance criterion.

**How to challenge:**
> "What exactly is the broken behavior — what do you see, get, or observe
> that's wrong? And what would 'fixed' look like — what would you need to
> observe to know it's working correctly?"

Push for specificity. "It doesn't work" is not a symptom. "Users get a 401
on every POST to /api/orders even with a valid token" is a symptom.

**Context grounding:** If the symptom references a component, endpoint, or
behavior that the context map shows lives in an unexpected place, flag it:
> "The error you're describing originates at [X], but the context map shows
> [Y] is actually responsible for [that behavior]. The bug may be in [Y], not
> [X] — does that match what you're seeing?"

---

### 2. Reproducer

**What it is:** Concrete inputs, environment, or sequence that reliably
triggers the bug.

**Why it matters:** A concrete reproducer lets `/trace` follow the exact
code path that's failing. Abstract descriptions ("sometimes auth fails")
produce speculative traces.

**How to challenge:**
> "Can you give me a concrete reproducer — specific inputs, request payload,
> environment, or sequence of actions that triggers this? If it's not
> consistently reproducible, describe the conditions under which you've seen
> it occur."

**Inference signal:** If the symptom is specific enough to imply the
reproducer (e.g., "401 on every POST to /api/orders with a valid JWT"),
the reproducer is largely covered by the symptom. Don't ask separately —
infer and note it.

---

### 3. When it started

**What it is:** Was this working before? When did it break? What changed?

**Why it matters:** A regression that started with a specific deploy narrows
the fault zone dramatically — the trace can focus on the diff rather than
the entire subsystem.

**How to challenge:**
> "Was this working at some point? If so, when did it break — after a
> specific deploy, code change, config update, or dependency upgrade?"

**Skip if:** The user has indicated this behavior has never worked (a feature
that was never implemented correctly) — "when it started" is irrelevant for
new code.

---

### 4. Frequency and conditions

**What it is:** Is this always broken, or only sometimes? Under what
conditions — specific environments, users, load levels, data states?

**Why it matters:** A deterministic logic bug (always fails) is found
differently than a race condition (sometimes fails under load) or an
environment issue (fails in production but not staging).

**How to challenge:**
> "Is this always broken, or intermittent? Does it happen for all users,
> specific users, or under specific conditions (load, environment, data
> state)?"

**Inference signal:** If the symptom is clearly always-on (e.g., "every
request to this endpoint returns 500"), don't ask. Infer frequency as
deterministic.

---

### 5. What's already been tried

**What it is:** Hypotheses already ruled out, investigations already done,
fixes already attempted.

**Why it matters:** Prevents `/trace` from re-treading dead ends and wasting
the trace budget on known-false hypotheses.

**How to challenge:**
> "What have you already tried or ruled out? Any hypotheses you've
> investigated and dismissed, or fixes that didn't work?"

**Skip if:** The input is clearly a fresh bug report with no investigation
history (e.g., "just discovered this in prod"). Don't ask what they've tried
if the framing implies nothing yet.

---

## Challenge Budget

Minimum: 1–2 questions (symptom and reproducer almost always need sharpening).
Typical: 2–3 questions.
Maximum: all five dimensions if the input is a vague report.

---

## Output Shape for Refined Bug Input

The refined input makes the following explicit (woven into prose):

- **Symptom** — what's broken, specifically
- **Fixed definition** — what "working" looks like
- **Reproducer** — how to trigger it
- **Timing** — when it started (or "never worked")
- **Frequency** — always / intermittent / conditions
- **Prior investigation** — what's been ruled out (or "none yet")

### Example

**Before (raw):**
> Auth is broken for some users.

**After (refined):**
> Users with OAuth-issued tokens (not internal JWTs) are getting a 401 on
> every request to /api/v2/orders, even though the same tokens work on
> /api/v2/profile. Internal JWT holders are unaffected. This started after
> the v2.4.1 deploy on Tuesday. It's 100% reproducible for OAuth users —
> any valid OAuth token triggers it. Fixed would mean OAuth users can hit
> /api/v2/orders with the same success rate as /api/v2/profile. We've
> confirmed the tokens themselves are valid (they work on profile), so
> the issue is in how /api/v2/orders validates or handles OAuth tokens
> specifically.

---

## Hard-Stop Triggers for Bugs

Hard-stop if:

- The user cannot describe any observable symptom after direct challenge.
  They need to reproduce the bug before `/refine` can help.
  > "You'll need to observe and reproduce the bug before I can help refine
  > the input. Return to /refine once you can describe what you see when it
  > fails."

- The input conflates a bug (wrong behavior) with a feature (behavior that
  was never designed to work this way). After challenge, if it's clear the
  "bug" is actually missing functionality:
  > "This sounds like the behavior you want was never implemented, not that
  > working behavior broke. This is a feature request, not a bug. Re-run
  > /refine with that framing."
