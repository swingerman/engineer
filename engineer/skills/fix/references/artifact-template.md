# Fix Artifact Template

Canonical schema for `.engineer/fixes/<YYYY-MM-DD-slug>.md`.
Copy and fill in. Fields marked `# required` must be present before validation passes.

```yaml
---
slug: "2026-05-25-login-redirect-loop"        # required — YYYY-MM-DD-<kebab-slug>
title: "Login redirect loops on expired token" # required — one-line human label
severity: high                                 # required — low | medium | high | critical
blocks_user: true                              # required — bool; true if users are actively blocked
workaround: "clear session cookies manually"  # required — describe workaround or "none"
status: investigating                          # required — see lifecycle below

source:
  kind: sentry                                 # sentry | github | slack | user | internal
  ref: "https://sentry.io/issues/12345"       # URL, issue ID, or conversation link

repro: |                                       # concise steps to reproduce
  1. Let a session token expire.
  2. Visit /dashboard while logged out.
  3. Observe infinite redirect between /login and /dashboard.

expected: "Redirected to /login once; prompted to log in."
actual: "Browser loops between /login and /dashboard indefinitely."

feature_refs:                                  # populated in Step 2; may be empty for loose fixes
  - "features/031-auth-session"

investigation:
  match_mode: auto                             # auto | manual | none
  candidates_considered: 3                    # number of features evaluated

pin_confirmation:
  feature_refs:
    - feature: "features/031-auth-session"
      spec_path: "features/031-auth-session/fixes/2026-05-25-login-redirect-loop.spec.md"
      red_run:
        result: red                            # must be "red" before proceeding
        command: "pytest tests/auth/test_redirect.py::test_expired_token_redirect"
        output: "FAILED — AssertionError: expected redirect once, got loop"

fix_commits:
  - "a1b2c3d fix: guard expired-token redirect in SessionMiddleware"

regression_evidence:                         # REQUIRED from status: fixed on
  repro_commit: "9f8e7d6"                    # Step 3 — commit adding the RED spec; must be an ancestor of fix_commits[0]
  command: "pytest tests/auth/test_redirect.py::test_expired_token_redirect"
  fail_output: |                             # run at repro_commit
    FAILED — AssertionError: expected redirect once, got loop
  pass_output: |                             # Step 4 — same command after the last fix commit
    1 passed

attempts:                                    # Step 4 — one entry per attempt, appended BEFORE the attempt
  - gate: regression-spec
    result: fail                              # pending | pass | fail
  - gate: regression-spec
    result: fail
  - gate: regression-spec                     # 3rd+ attempt after 2 fails on a gate: premise required
    result: pass
    premise:
      belief: "SessionMiddleware redirects before the token-refresh hook runs"
      observation: "if false, the refresh hook logs before the first redirect"
      command: "pytest tests/auth/test_redirect.py -k expired -s"
      output: "redirect /login; redirect /dashboard; no refresh line"
      falsified: false                        # true → re-diagnose (Step 2), new premise, no code

harden_results:                              # written by /engineer.harden (fix mode) + fix Step 7
  advisor: {decided_by: human, rows: [{tool: atdd-mutate, verdict: recommend, target: "src/auth/session.py", selected: true}]}
  introversion: {skipped: "no test files changed besides the regression spec"}
  mutation_score: 91                          # percent 0–100 (quality_thresholds.mutation_score_min), or {skipped: "<reason>"}
  formal: []                                  # [{tool, target, invariant, verdict, bound_or_proof, finding}]
  arch_check: {status: clean}                 # {status: clean | violations, notes}
  bug_line_mutation_confirmed: true           # true once bug-line gate passes

gap_analysis:
  - category: incomplete_spec                 # see gap-analysis-categories.md for vocabulary
    phase: atdd                               # which DAE phase leaked
    finding: "Spec for session management had no scenario covering token expiry during redirect."
    followup_kind: extend_spec

followups:
  - category: incomplete_spec
    action: "Add expired-token redirect scenarios to features/031-auth-session/spec.md"
    status: applied                           # open | applied

handoff_path: .engineer/handoffs/2026-05-15-login-redirect-loop-close.md
                                              # REQUIRED when status: closed
                                              # path to the close-step handoff for this fix
---
```

## Lifecycle status progression

```
investigating → pinned-pending → pinned → fixed → refined → verified → hardened → gap-analyzed → closed
```

Each status is written by the skill step that completes it (Steps 1–9).
`dae_fix.py --validate <file>` checks slug, title, severity, status, blocks_user, workaround, gap_analysis category membership, that any attempt after two failures on the same gate carries a complete, unfalsified `premise:`, and — from `status: fixed` on — complete `regression_evidence` whose `repro_commit` is a strict git ancestor of `fix_commits[0]`.
`dae_fix.py close_ready(rec)` enforces the close gate: pin confirmed + hardened (including bug-line gate) + gap_analysis non-empty + no unresolved blockers.
