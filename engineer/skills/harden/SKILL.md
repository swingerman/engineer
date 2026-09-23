---
name: harden
description: Use after a feature passes Light Verify (CP7), to prove the tests actually catch bugs and, where the code warrants it, to formally check its invariants — Checkpoint 8. Runs the refinement-advisor, then the picked tools — introversion scan, mutation testing, and opt-in TLA+ / Lean verification. Triggers — "/engineer.harden", "harden this feature", "Checkpoint 8", "which hardening does this need", "formally verify the feature".
---

# harden

Checkpoint 8. Acceptance tests show the feature works. Harden checks whether
the tests would notice if it stopped working, and, for code with a real
invariant, whether that invariant can be broken at all.

Tool choice comes from `/engineer.refinement-advisor`, not from a fixed list.
Formal verification is worth its cost on a retry loop, and a waste on a CRUD
endpoint.

## Modes

- **feature** (default): scope = the feature branch's changed code. Entry gate
  applies. Writes a CP8 handoff.
- **fix**: called from `/engineer.fix` Step 7. Scope = the fix diff. Skip the
  Step 0 feature gate, write results into the fix record's `harden_results`, and
  write no CP8 handoff (fix owns its own close).

## Workflow

**Step 0 — Entry gate** (feature mode). Run
`${CLAUDE_PLUGIN_ROOT}/scripts/dae_handoff.py <feature-dir> --through 7`. On a
non-zero exit, stop and show the gap to the human. Then run
`${CLAUDE_PLUGIN_ROOT}/scripts/dae_branch.py <feature-dir>`. On a non-zero exit,
stop. After both pass, show the breadcrumb
(`${CLAUDE_PLUGIN_ROOT}/scripts/dae_progress.py <feature-dir>`, advisory) and
create one TodoWrite todo per step. See
`${CLAUDE_PLUGIN_ROOT}/references/progress-indicator.md`.

**Verification independence:** CP8 runs on a non-implementer agent
(`agent_id` ≠ CP5's; enforced by `dae_handoff.py gate()`).

1. **Resolve + scope.** Resolve the root and manifest via
   `${CLAUDE_PLUGIN_ROOT}/scripts/dae_resolve.py`. Scope = changed code. Load
   `acs.md`, `spec.md`, `CHARTER.md`, and the CP7 handoff's `crap_results`
   block (arch-check records crap-analyzer's output there). In fix mode, or if
   the block is missing, run `crap-analyzer` on the scope first.
2. **Advise.** Run `/engineer.refinement-advisor` with `stage: harden` over the
   scope, passing it `crap_results`. Effective autonomy decides who picks the
   checks (see the advisor's *Who decides: autonomy*):
   - at `high`, the advisor decides alone
   - below `high`, it asks
   - `manifest.harden.required: true` makes every recommended check mandatory
   - Steps 3–5 each run only if their tool was selected. An unselected step
     records `{skipped: <the advisor's reason, or "not selected">}` in its
     `harden_results` field, so the decision is visible, not silent.

   Record the table, what was selected, and who decided (`decided_by: advisor |
   human`) in `harden_results.advisor`.
3. **Introversion pre-scan** (if selected). Run
   `${CLAUDE_PLUGIN_ROOT}/scripts/dae_introvert.py <methodology-root>`. It flags
   tests that can pass without asserting on SUT output. The script defers to
   `manifest.introversion.backend` when set. Any non-`ok` status is advisory.
   Dispatch an agent to confirm each finding. For each confirmed vacuous test,
   write a real assertion and re-run. Record `harden_results.introversion`.
4. **Mutation** (if selected). Run `atdd:atdd-mutate` on the touched files, then
   `atdd:kill-mutants` on the survivors. If a test was flagged in Step 3 **and**
   carries a surviving mutant, it is almost certainly vacuous. Record
   `harden_results.mutation_score`.
5. **Formal checks** (selected TLA+/Lean rows only). Dispatch one **plain subagent**
   (default isolation, **not a fork**) per pick, `subagent_type:
   engineer:formal-verifier` (or the project override): `/engineer.tlaplus` for
   interleaving/state-machine targets, `/engineer.lean` for all-inputs targets. Each
   brief gives:
   - the target function (file:line)
   - the confirmed invariant
   - "follow the skill's *Verifying real code* workflow; model the code as
     written"
   - "**do not open a PR**; return the verdict, and any counterexample
     reproduced against the real code"

   Picks for different targets are independent, so dispatch them in parallel.
   Handle each result as follows:
   - **Holds.** Record the verdict and its limit. TLC's "no error up to N" is not
     a proof; Lean with no `sorry` and clean `#print axioms` is.
   - **Confirmed counterexample.** Treat it like a surviving mutant. Pin it as a
     failing test (red), fix, go green, and re-run both test streams. If the fix
     would change AC-observable behavior, stop and route to
     `/engineer.feature-edit`. Harden does not rewrite the contract.
   - **Doesn't reproduce.** The model diverged from the code. Record it as
     `provisional` and do not fix the code.
   - **Side findings** (dead code, an unreachable branch). Record them as
     advisory, and don't block on them.

   Record `harden_results.formal[]`:
   `{tool, target, invariant, verdict: holds|violated|provisional, bound_or_proof, finding}`.
6. **Arch re-check.** Harden may have changed code, so re-run
   `${CLAUDE_PLUGIN_ROOT}/scripts/dae_arch.py <methodology-root>`. Record
   `harden_results.arch_check`.
7. **Handoff** (feature mode). Emit per
   `${CLAUDE_PLUGIN_ROOT}/references/handoff-summary.md` with `checkpoint: 8`.
   The `exit_criteria` block asserts:
   - the advisor ran, and every tool has a recorded verdict (selected, or
     skipped with a reason)
   - if mutation was selected: score ≥ `quality_thresholds.mutation_score_min`
     (`verified_by: tool`). Both are percentages, 0–100.
   - if introversion was selected: no unresolved confirmed vacuous tests
   - every selected formal check is `holds`, or its counterexample is fixed and
     pinned by a test that fails on the old code
   - arch-check clean

   `recommended_next`: "open PR / `/engineer.progress-log`".

## harden_results shape

```yaml
harden_results:
  advisor: {decided_by: advisor, rows: [{tool, verdict, target, why, invariant, selected}]}
  introversion: {status, flagged, confirmed_vacuous, fixed}
  mutation_score: 87            # percent, 0–100; or {skipped: "config-only change"}
  formal:
    - {tool: tlaplus, target: "ResidentialProxyHttpClient::get", invariant: "attempt ≤ 3; every path exits",
       verdict: holds, bound_or_proof: "TLC exhaustive, 16 states", finding: "post-loop throw unreachable (advisory)"}
  arch_check: {status: clean}
```

`fix` mode adds `bug_line_mutation_confirmed` in fix's own Step 7. That
bug-line gate always runs, whatever the advisor picked. It is how `fix` proves
its regression test is tied to the bug. A skipped `mutation_score`
(`{skipped: …}`) still counts as recorded for `dae_fix.py`'s close check.

## Fork safety

Formal subagents run toolchains and re-run their own output, which is not
fork-safe. Use plain subagents, and no detached/background Bash runs inside
them. See `${CLAUDE_PLUGIN_ROOT}/references/parallelism.md` (Fork safety).

## References

- `/engineer.refinement-advisor`: picks the tools
- `/engineer.tlaplus`, `/engineer.lean`: the formal-verification skills; each has a "Verifying real code" workflow
- `atdd:atdd-mutate`, `atdd:kill-mutants`: mutation testing
- `${CLAUDE_PLUGIN_ROOT}/references/handoff-dispatch.md`: autonomy keying and brief template
