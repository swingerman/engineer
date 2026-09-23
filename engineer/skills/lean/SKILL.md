---
name: lean
description: Use to formally verify real code with Lean 4. Model a function or state machine as written, prove an invariant for every input, and reproduce any counterexample as a failing test. Dispatched by /engineer.harden for all-inputs invariants (parsers, maskers, money math, permission predicates); also usable directly. Triggers — "/engineer.lean", "use lean to verify X", "prove X can't happen", "lean-verify this code".
---

# Lean

Lean is only useful here if the proof actually compiles. Don't hand back
`sorry`-riddled code and call it done — the whole point of a proof assistant
is that `lake build` is the ground truth, not your judgment about whether the
proof "looks right."

## Setup check

First run:

```bash
which lean lake elan
```

If missing, tell the user and offer to install via elan (the Lean toolchain
manager) — don't install it silently, it's a real download:

```bash
curl https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh -sSf | sh
```

If the project has a `lakefile.lean`/`lakefile.toml` + `lean-toolchain`, just
`cd` into it and use `lake build` — don't reinvent the toolchain setup.

## Workflow

1. **Write/edit the `.lean` file.**
2. **Check it**: `lake build` (whole project) or `lake env lean file.lean`
   (single file, faster while iterating).
3. **Read the error precisely.** Lean errors point at the exact tactic state
   — the "unsolved goals" block tells you exactly what's left to prove. Don't
   guess; read the goal state and pick a tactic that closes it.
4. **Before writing a new proof from scratch, check if Mathlib already has
   it.** Reproving a standard lemma is wasted work:
   - `exact?` — closes the goal if an exact Mathlib lemma exists.
   - `apply?` — suggests lemmas that partially match the goal.
   - [Loogle](https://loogle.lean-lang.org/) — search Mathlib by type
     signature/pattern when the tactic search above doesn't find it.
5. **No `sorry` in the final result.** A `sorry` is a placeholder for an
   unproved gap — it compiles but proves nothing. If you can't close a goal,
   say so and show the remaining goal state rather than papering over it with
   `sorry`.
6. **Iterate**: fix → rebuild → read next error. Don't try to fix every error
   in one shot on a long proof; Lean errors often cascade from one root
   cause.

## Verifying real code ("use lean to verify X")

This is a different job from proving a math statement: the goal isn't a
polished proof, it's finding real bugs in real code and getting them fixed.
Lean here is a bug-finding tool, not a deliverable — nobody merges the
`.lean` files, they merge the PRs the proofs led to. Structure the work as a
todo list and post progress as you go; this runs long and the user wants
visibility into where you are, not just a final answer.

1. **Split the target into independent state machines.** Read the real
   source (e.g. `claude.ts`, the SDK) and identify the handful of orthogonal
   subsystems worth modeling separately — retry logic, a turn loop, stream
   parsing, session phase transitions, a control protocol. Model each as its
   own small Lean 4 file. Small independent models are easier to get right
   and to review than one giant one, and a bug in one doesn't block proving
   the others.
2. **Write each model from the code, not from what the code "should" do.**
   The model's states, transitions, and guards must mirror what's actually
   implemented, including its bugs — if you model the *intended* behavior
   instead of the *actual* behavior, every proof is vacuous. Cite the
   file/line the model is based on so a reviewer (or you, later) can check
   the mapping.
3. **State the invariants that must hold** — the properties a reviewer would
   actually care about (one result per turn, in order; bounded retries; the
   stream only yields closed blocks; no state stuck unreachable). Prove them.
4. **Review each model independently against the real code before trusting
   its proofs.** A proof about a wrong model tells you nothing. Do this pass
   per-model as each one is written, not all at the end.
5. **When a proof fails or TLC-style search finds a counterexample, don't
   report the abstract trace as the finding — reproduce it against the real
   code.** Turn the counterexample into a concrete input/sequence, run it (or
   write a test) against the actual implementation, and confirm the bug
   really happens there. A counterexample that doesn't reproduce means the
   model diverged from reality — fix the model, not the code.
6. **For every confirmed bug, pin it with a test that fails before the fix
   and passes after.** State it in those terms: the test is what proves the
   bug was real and the fix works. Opening a PR is an external write. Propose
   the draft PR and wait for the human's OK
   (`${CLAUDE_PLUGIN_ROOT}/references/handoff-dispatch.md`). When
   `/engineer.harden` dispatched you, don't propose one: return the verdict and
   the reproduction, and harden pins and fixes on the feature branch.
7. **Track what's still open.** Some invariants won't be provable yet (need
   a stronger model, or the bug needs a design decision first) — say so
   explicitly as "held up: X" rather than silently dropping them.
8. **Flag disagreement between model and reality as provisional, not as a
   proof of a bug.** If a model's proofs consistently disagree with real
   runs of the code, the model is probably still wrong somewhere — call this
   out rather than shipping PRs off an untrustworthy model.
9. **Final audit before calling it done**: `lake build` succeeds, `#print
   axioms` on every top-level theorem shows no unexpected axioms snuck in
   (e.g. via a bad `sorry`-adjacent tactic), and `grep -rn sorry` on the
   Lean sources is empty.

## Common tactics (starting point, not exhaustive)

`rfl`, `simp`, `ring`, `linarith`, `omega`, `exact`, `apply`, `intro`, `cases`,
`induction`, `rcases`, `constructor`, `unfold`. `simp` and `omega` in
particular close a large fraction of routine goals — try them before hand-
building a proof term.

## Self-check

After any proof claimed "done", the runnable check is `lake build` (or
`lake env lean` on the file) exiting 0 with no `sorry`/`admit` left in the
diff. Report the actual exit status, not "looks correct."
