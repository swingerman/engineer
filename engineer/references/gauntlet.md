# Gauntlet loop — build against a bar until it clears, without a human in between

A **builder** produces work, a **fresh critic** compares it against a concrete
reference — the *bar* — and names the single biggest remaining gap, the builder
closes that gap, and the loop repeats until the critic says the output ties or
beats the bar (or the round cap is hit). The human sees the rounds afterwards,
not between them.

This exists because DAE's objective graders only cover behavior. Acceptance
tests answer "does it work"; CRAP and mutation score answer "is it tested". For
anything they can't assert — visual fidelity to a design, interaction feel,
output quality — **the human is the grader**, which is why implementation gets
babysat even when the specs and designs were ready before a line was written.
The gauntlet substitutes a critic agent with a reference for the human with an
opinion.

Adapted from the Gauntlet Loop (somethingbig.ai). It is the loop-until quality
pattern of `${CLAUDE_PLUGIN_ROOT}/references/parallelism.md`, with a bar.

## The bar — no bar, no gauntlet

The bar is a **tangible artifact the critic can open and inspect**: an exported
design frame, a screenshot of the reference UI, a live reference URL, a
reference implementation module, a golden output file. Prose is not a bar —
"looks polished", "matches the design system" and the ACs themselves all fail
this test, because a critic that can't inspect the bar produces plausible-
sounding fiction and the loop optimizes toward it.

The bar is declared at CP4 in `plan.md`'s Test strategy (see the `plan` skill,
Step 5) as paths/URLs plus the command that captures the *candidate* in the same
form:

```yaml
gauntlet:
  bar:
    - design/checkout-desktop.png     # 1440x900, exported from Figma
    - design/checkout-mobile.png      # 390x844
  capture: npm run screenshot -- --route /checkout --viewport 1440x900
  max_rounds: 5
```

**A feature with no `gauntlet:` block runs no gauntlet — silently.** That is the
opt-in: not a flag, not a default, the presence of a bar. `manifest.gauntlet.capture`
may hold a project-wide capture command so features only declare the references.

## Where it fires

| Gate | Where | Bar | Fires when |
|---|---|---|---|
| **CP5 exit** | `atdd:atdd-team` Phase 4, **after** both streams are green | the `gauntlet:` block | a bar is declared |
| **CP5 green loop** | `atdd:atdd-team` Phase 4, during implementation | the failing acceptance tests | always — this is the no-human-between-rounds contract, below |
| CP6 | `refine` | — | not wired; add only if a run shows one-shot refine leaving accepted proposals on the table |

Not at CP2/CP4: those artifacts have nothing to A/B against, and the review
panel (`${CLAUDE_PLUGIN_ROOT}/references/review-panel.md`) already reviews
judgment there. Not at CP7/CP8: CRAP and mutation score are already numeric bars
with loops around them.

## The rules

1. **Never let the builder grade itself.** The critic is a separate agent with
   fresh context. A builder scoring its own output rates its own decisions, and
   the loop terminates on the first round every time.
2. **Destination, not route.** Give the builder the goal and the bar. Do not
   prescribe the fix — if you already know the fix, apply it and skip the loop.
3. **One gap per round.** The critic returns the *single largest* gap, not a
   list. A list gets partially addressed and the next critic re-reports the
   remainder as new findings, which reads like progress and isn't.
4. **The gap must be falsifiable.** "Spacing between the card and the header is
   16px; the reference is 32px" — not "feels cramped". An unfalsifiable gap
   cannot be closed, so the loop cannot terminate.
5. **The critic never edits.** It captures, compares, reports. Editing critics
   drift into builders and rule 1 is lost.

## Stop conditions — all four, checked every round

- **Clear** — the critic returns `verdict: ties-or-wins`. Done.
- **Cap** — `max_rounds` reached (default 5, never unbounded). Stop, hand off
  with the open gap recorded and `human_action_needed: yes`.
- **No progress** — two consecutive rounds return the same gap. The builder
  can't close it; stop and surface it rather than burning rounds.
- **Regression** — a round breaks a previously green test stream. Revert that
  round's change, stop, surface. The behavior contract outranks the bar.

## Autonomy keying

Source of truth is `${CLAUDE_PLUGIN_ROOT}/references/handoff-dispatch.md`.

| `autonomy_level` | behaviour |
|---|---|
| `low` | Offer the loop with the bar and round cap named; wait for the nod. Show each round's verdict. |
| `medium` | Auto-run; announce in one line ("gauntlet: 3 rounds vs `design/checkout-desktop.png`"). |
| `high` | Auto-run silently; report the final verdict and the round table. |

At every level the loop runs **round to round without asking**. The pause
between rounds is exactly the babysitting this removes; the stop conditions are
what keep it bounded.

## Fork safety — not optional here

The critic captures screenshots and re-runs on its own output, which is the
precise shape that is **not fork-safe**: a fork re-wakes on every detached-child
completion and can self-perpetuate (one capture fork looped ~300k tokens and
clobbered committed screenshots). Dispatch critics as **plain subagents (default
isolation)** or a workflow, and never launch detached/background Bash runs
inside one. See `${CLAUDE_PLUGIN_ROOT}/references/parallelism.md` (Fork safety).

## The critic brief

```
description: gauntlet critic round <N> — <feature-slug>
model: <inherit; frontier when the bar is visual/qualitative — classes, not
        product names, resolved against the Agent tool's live `model` enum>
prompt:
  You are grading one candidate against a reference. You do NOT edit code.

  ## The bar
  <abs paths / URLs of the reference artifacts>

  ## The candidate
  Run: <capture command>   → produces <abs path>
  (If capture fails, say so and stop — do not grade from the source code.)

  ## Compare
  Open both. A/B them. Decide which wins on fidelity to the bar.
  Return ONE verdict and, if the candidate loses, the SINGLE largest gap:
  concrete and measurable (a number, a color, a missing element, a wrong
  order), located in the candidate's source where you can find it.
  Ignore everything you are not asked to grade — behavior is already covered
  by the acceptance tests.

  ## Prior rounds
  <the gaps from previous rounds and what was done — so you don't re-report a
   gap that was deliberately rejected>

  ## How to report
  verdict: ties-or-wins | loses
  gap: <one line, falsifiable>  (omit when ties-or-wins)
  location: <file:line, or the captured region>
  <the reporting contract from handoff-dispatch.md — verbatim>
```

The builder's round brief is the same shape inverted: the gap, the bar, the
capture command, and "close this one gap; do not refactor anything else; both
test streams must still be green when you finish".

## What lands in the handoff

Record every round — `gauntlet_rounds[]` in the CP5 handoff, per
`${CLAUDE_PLUGIN_ROOT}/references/handoff-summary.md`:

```yaml
gauntlet_rounds:
  - round: 1
    bar: design/checkout-desktop.png
    verdict: loses
    gap: "Summary card uses 16px gutter; reference uses 32px."
    location: src/checkout/Summary.tsx:41
    action: "Gutter set to 32px (token spacing.8)."
  - round: 2
    bar: design/checkout-desktop.png
    verdict: ties-or-wins
    stopped_by: clear
```

A loop that stopped on `cap`, `no-progress` or `regression` sets
`human_action_needed: yes` and names the open gap — that is the one case where
the human is re-engaged, and by then the rounds show exactly what was tried.

## References

- `${CLAUDE_PLUGIN_ROOT}/references/parallelism.md` — the loop-until pattern; Tier-3 substrate; fork safety
- `${CLAUDE_PLUGIN_ROOT}/references/review-panel.md` — the one-shot artifact-gate sibling (CP2/CP4)
- `${CLAUDE_PLUGIN_ROOT}/references/handoff-dispatch.md` — autonomy source; the brief template and reporting contract
- `${CLAUDE_PLUGIN_ROOT}/references/handoff-summary.md` — where `gauntlet_rounds[]` lives
- `${CLAUDE_PLUGIN_ROOT}/references/model-classes.md` — resolving `inherit` / `frontier`
