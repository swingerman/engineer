# Choice points — recommend-and-redirect, sized by projection

How DAE puts a decision to the human: **a filled-in recommendation to approve or
redirect, not a one-question-at-a-time interview.** The agent projects what it
can, picks the likely answer, and shows the alternatives so the human bumps it a
notch rather than being interrogated. Judgment concentrates at the two ends
(front + back gates) and the funnel; the autonomous middle asks nothing.

This is the anti-fragmentation rule made concrete: mid-stream questions re-prime
context and fragment the work (they are the expensive kind). A choice point is
allowed only where the human's judgment actually lives.

## The shape

Every choice point renders as:

- **Recommendation** — one option, marked **"(Recommended)"**, listed first.
- **Rationale** — the one-line projection behind it ("~1 file, well-understood
  → express (XS)").
- **Alternatives** — the other options, so the human redirects in one move.
- **Default on silence** — dialed by `autonomy_level`: `low` → always confirm;
  `medium`/`high` → recommend and proceed if the human doesn't engage.

Use `AskUserQuestion` to render it (recommended option first). Never a bare
open question where a projection could have pre-filled the answer.

## The projection — size + clarity from the conversation

At the funnel (discuss / intent / feature-init) the agent reads the idea and
projects two things that pre-select the build path:

| signal (from discuss / intent / the idea) | pushes toward |
|---|---|
| touches ~1 file / 1 module / ~1 PR | XS → **express** |
| spans multiple competencies / "several PRs" | M+ → **full** (+ offer decompose) |
| shape unclear, UX-heavy, "know it when I see it" | **prototype-first** |
| shape known, behavior specifiable up front | **spec-first** |
| charter-flagged (payments/auth/migration/blast-radius) | **full + never express** (overrides size) |
| novel domain, no prior art in the repo | nudge prototype + up-size |

Output = a projected `size` (XS/S/M/L/XL) + a front-half flag. This *is* the
`size` field `feature-init` already consumes — the projection fills it in
instead of asking cold. The human confirms or bumps it.

## The two funnel decisions

Two orthogonal choices, both front-loaded, decided once (see
`references/two-paths.md` + `references/express-lane.md`):

- **A — front half:** do we know what to build? Known → **spec-first**; fuzzy →
  **prototype-first** (iterate, then re-enter B on convergence).
- **B — weight:** how much pipeline does it deserve? Small/low-risk → **express
  (XS)**; non-trivial → **full DAE**. Reached from *either* front-half — a
  converged prototype re-enters B via `prototype_disposition` (XS = in-place
  harden, the small notch).

```
intent/discuss
  └─ A: understood? ── no ─→ prototype (iterate) ─┐ converge
        │ yes                                     │
        ▼                                         ▼
     B: weight? ───────────────→  express (XS)  |  full DAE
```

## Guardrails

- **Charter beats the projection** — a flagged path is never recommended
  express, however tiny.
- **Escalation ratchet catches under-projection** — a wrong-small guess ratchets
  XS → full mid-pass with the tracker row intact (`references/express-lane.md`).
  So the projection is allowed to be cheap and occasionally wrong.

## Where choice points fire (ends + funnel only)

Funnel path triage (discuss / intent / feature-init) · front bundle approval
(post-CP4: acs+spec+plan, one approval) · back verify gate · prototype decide
(iterate/discard/convert) · fix triage. Handoffs *inside* the middle stay
non-interactive durable state.

## References

- `${CLAUDE_PLUGIN_ROOT}/references/two-paths.md` — front-half A (spec vs prototype)
- `${CLAUDE_PLUGIN_ROOT}/references/express-lane.md` — weight B, the XS end
- `${CLAUDE_PLUGIN_ROOT}/references/gate-profile.md` — the `size` dial the projection fills
- `${CLAUDE_PLUGIN_ROOT}/references/handoff-dispatch.md` — `autonomy_level`, the default-on-silence dial
