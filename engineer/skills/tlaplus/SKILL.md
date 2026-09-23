---
name: tlaplus
description: Use to model-check real code or a design with TLA+ and TLC. Model retries, locks, async flows, protocols or state machines as written, check invariants over every interleaving, and reproduce any counterexample trace as a failing test. Dispatched by /engineer.harden for concurrency- and ordering-shaped risks; also usable directly, including to spec a design before building it. Triggers — "/engineer.tlaplus", "use TLA+ to verify X", "model-check X for races/deadlocks", "write a TLA+ spec for this protocol".
---

# TLA+

TLA+ earns its keep by finding the counterexample you didn't think of. Don't
write a spec and declare victory without actually running TLC — an
uncompiled/unchecked spec is just prose with extra syntax.

## Setup check

`java -version` (TLC needs a JVM 11+; if it's missing, tell the user rather than
installing one). The model checker jar (`tla2tools.jar`, pinned to v1.7.4)
auto-downloads on first run via
`${CLAUDE_PLUGIN_ROOT}/skills/tlaplus/scripts/tlc.sh`, no separate install step needed.

## Translating an informal design into TLA+

When the user describes a protocol/state machine in plain language, structure
the spec around these pieces — this is the actual translation work, not
boilerplate:

1. **`VARIABLES`** — the pieces of state that change. Keep this minimal;
   every variable multiplies the state space TLC has to explore.
2. **`Init`** — the starting state predicate.
3. **Actions** — one predicate per state transition (e.g. `SendMsg`,
   `Crash`, `Receive`). `Next == SendMsg \/ Receive \/ Crash \/ ...`
4. **Invariants** — the safety properties that must hold in *every* reachable
   state (e.g. `NoDataLoss`, `MutualExclusion`). These are what TLC actually
   checks — a spec without invariants can't find bugs.
5. **(Optional) Temporal properties** — liveness, e.g. `EventuallyDelivered`,
   checked separately from safety invariants and much more expensive.

Ask the user what actually must never happen (safety) before modeling — that
answer is the invariant, and it's the one thing you can't infer from the
protocol description alone.

## Workflow

1. Write `Spec.tla` (the spec/module) and `Spec.cfg` (which invariants to
   check, `CONSTANTS` values, and state-space bounds like a max number of
   processes — TLC exhaustively explores states, so unbounded constants mean
   it never finishes).
2. Run: `bash ${CLAUDE_PLUGIN_ROOT}/skills/tlaplus/scripts/tlc.sh Spec.tla Spec.cfg`
3. **Read the output precisely.** TLC either says the invariant holds
   (`Model checking completed. No error has been found.`) or prints a
   counterexample trace — the exact sequence of states that breaks the
   invariant. That trace is the whole value of doing this: don't summarize it
   away, show the state-by-state trace so the actual bug is visible.
4. Fix the spec (or realize the invariant was wrong) and rerun. A "violation"
   is sometimes the invariant being stated too strongly — check which one is
   actually wrong before patching either.
5. If TLC times out or the state space is too large, narrow `Spec.cfg`
   constants (fewer processes/values) first — that's usually cheaper than
   restructuring the spec, and still finds most bugs since TLA+ bugs are
   rarely scale-dependent.

## Verifying real code ("use TLA+ to verify X")

This is a different job from writing a spec from scratch: the goal is
finding real concurrency/protocol bugs in real code and getting them fixed.
The `.tla` files are scaffolding, not the deliverable — nobody merges them,
they merge the PRs the counterexamples led to. TLA+'s specific strength here
is interleavings: races, missed locks, out-of-order delivery, retry/timeout
interactions — the class of bug that's nearly impossible to hit with a unit
test because it depends on *when* two things happen relative to each other.
Reach for TLA+ over Lean when the suspected bug is about concurrent/
interleaved behavior; reach for Lean when it's about a pure functional
transformation or an unbounded data invariant. Structure the work as a todo
list and post progress as you go — this runs long.

1. **Split the target into independent state machines**, same as for a
   from-scratch spec — read the real source and model each orthogonal
   subsystem (retry logic, session lifecycle, a message queue, a lock
   protocol) as its own small `.tla` module.
2. **Model from the code as written, not as intended.** States, actions, and
   guards must mirror the actual implementation including its bugs, or every
   check is vacuous. Cite the file/line each action is based on.
3. **State the invariants a reviewer would actually care about** (mutual
   exclusion, no lost message, bounded retries, no state stuck unreachable)
   and check them with TLC. TLC's exhaustive search over the bounded state
   space in `Spec.cfg` is doing the same job proof search does in Lean, but
   it's automatic — you don't have to find the counterexample yourself, TLC
   does, which is exactly why this is a good fit for "does this race exist."
4. **Review each model independently against the real code before trusting
   its results.** A clean TLC run on a wrong model proves nothing about the
   real system.
5. **When TLC reports a violation, don't report the abstract trace as the
   finding — reproduce it against the real code.** Translate the
   state-by-state trace into a concrete interleaving/input sequence and
   confirm it against the actual implementation (a test, a script forcing
   the interleaving, or a careful read of the code path). If it doesn't
   reproduce, the model diverged from reality — fix the model, not the code.
6. **For every confirmed bug, pin it with a test that fails before the fix
   and passes after.** State it in those terms: the test is what proves the
   bug was real and the fix works. Opening a PR is an external write. Propose
   the draft PR and wait for the human's OK
   (`${CLAUDE_PLUGIN_ROOT}/references/handoff-dispatch.md`). When
   `/engineer.harden` dispatched you, don't propose one: return the verdict and
   the reproduction, and harden pins and fixes on the feature branch.
7. **Track what's still open** ("held up: X") rather than silently dropping
   an invariant you couldn't get TLC to finish checking.
8. **Flag model/reality disagreement as provisional.** If a model's
   violations keep failing to reproduce, or a model that should model a real
   race never turns one up, the model is probably still wrong — say so
   before shipping PRs off it.
9. **Know the limit of a "no error found" run**: TLC checked every state
   reachable within `Spec.cfg`'s bounds, not the system for all scales. That
   supports "we found no counterexample up to N processes," not "this is
   proven correct" — say the former, not the latter, in the final report.

## Self-check

The runnable check is the TLC run itself — report the actual TLC verdict
("no error found" vs. a specific counterexample), not "the spec looks
correct." A spec that was never run through TLC hasn't been verified.
