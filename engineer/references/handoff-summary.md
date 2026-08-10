# Agentic handoff summary — shared contract

Every DAE skill ends by emitting a **handoff summary** — the signal that tells the human when to re-engage. This file is the canonical format; skills reference it instead of inlining the template.

(Exception: `progress-log` does NOT emit one — it is the skill that *processes* handoffs. Emitting one would loop.)

## Location and naming

- **Feature-scope handoffs** — `<methodology_root>/features/NNN-<slug>/handoffs/<ISO-timestamp>-<skill>.md`
- **Project-scope handoffs** — `<methodology_root>/.engineer/handoffs/<ISO-timestamp>-<skill>.md` — for skills that run without a feature folder: `onboard` (Checkpoint 0), `consistency-check --project`, and any other project-scope task.

Timestamp is compact ISO 8601 `YYYY-MM-DDTHHMM` (no seconds) — chronologically sortable.

## Format

YAML frontmatter + markdown body.

```markdown
---
skill: <skill name>
agent_id: <main | subagent-N | team-role | remote-session-id>
started: <ISO timestamp>
ended: <ISO timestamp>
checkpoint: <number | null>          # the pipeline checkpoint addressed; null if off-pipeline
artifacts:                           # paths produced/changed; [] if none
  - features/NNN-<slug>/<file>
exit_criteria:                       # required on checkpoint-advancing skills
  - criterion: <one Section 8 exit criterion>
    verified_by: <tool | human | judgment>
    met: <true | false>
    evidence: <one line; for `tool`, the command + its output>
panel_findings:                      # required when a review panel ran (CP2/CP4)
  - role: <adviser | advocate>
    severity: <error | advisory>
    claim: <one line — the defect, not the topic>
    location: <file:line, or file>
    accepted: <yes | no>
    disposition: <what was done, or why it was rejected>
gauntlet_rounds:                     # required when a gauntlet loop ran (CP5)
  - round: <n>
    bar: <the reference this round was graded against>
    verdict: <ties-or-wins | loses>
    gap: <one line, falsifiable — omit on ties-or-wins>
    location: <file:line, or the captured region>
    action: <what the builder changed to close it>
    stopped_by: <clear | cap | no-progress | regression>   # last round only
findings_summary: <one line>          # optional
human_action_needed: <yes | no>
human_action_kind: <review | decision | approval | none>   # optional
recommended_next: <next checkpoint / skill / "done">
tracker_update: <tracker_ref + what changed | none>         # optional
cloud_session_url: <claude.ai/code session URL + PR link>   # optional; set when this checkpoint ran on a cloud agent
status: <complete | interrupted>
---

# <skill> — handoff summary

## What I did
1–2 sentences.

## Artifacts produced
File paths, or "None".

## Findings
Key results / surprises. Optional section.

## Human action needed?
Yes/No, and if yes what kind (decision / review / approval).

## Recommended next step
Next checkpoint, next skill, or done.

## Tracker update
What state was written. Optional section.
```

## Required vs optional

- **Required frontmatter:** `skill`, `agent_id`, `started`, `ended`, `artifacts`, `human_action_needed`, `recommended_next`, `status`
- **Required on checkpoint-advancing skills:** `checkpoint`, `exit_criteria` — required when `checkpoint` is set; both omitted for off-pipeline skills (`checkpoint: null`).
- **Required when a review panel ran:** `panel_findings` — on `discover-acs` (CP2) and `plan` (CP4) whenever the panel was dispatched. Record **every** finding, accepted or rejected; an undocumented rejection means the next agent re-litigates it. See `${CLAUDE_PLUGIN_ROOT}/references/review-panel.md`.
- **Required when a gauntlet loop ran:** `gauntlet_rounds` — on the CP5 handoff whenever the feature declared a `gauntlet:` bar. Record **every** round, including the ones whose gap was rejected. See `${CLAUDE_PLUGIN_ROOT}/references/gauntlet.md`.
- **Optional frontmatter:** `agent_role`, `findings_summary`, `human_action_kind`, `tracker_update`, `cloud_session_url`
- **Required body:** What I did, Artifacts produced, Human action needed?, Recommended next step
- **Optional body:** Findings, Tracker update

## Rules

- One summary per skill invocation. Sub-tasks don't emit unless themselves dispatched as a skill.
- On crash/interruption, emit a partial summary with `status: interrupted` capturing what was done.
- `agent_id` enforces verification independence (Principle 7): a verification handoff's `agent_id` must differ from the implementer's for the same feature. Enforced by `dae_handoff.py gate()` — any CP6/CP7/CP8 handoff whose `agent_id` equals the feature's CP5 handoff `agent_id` fails the gate with a "Principle 7" error. If the verify subagent crashes, the implementer MUST NOT self-verify — re-dispatch a fresh subagent or pause for the human.
- `exit_criteria[*].met` accepts `true`, `false`, or `partial`. `partial` counts as **not met** for the gate but is preserved distinctly in reports so the human can see the criterion was *attempted* but didn't fully satisfy. Never auto-promote `partial` to `true` to move forward.
- An **unaddressed `error`-severity `panel_findings` entry blocks the checkpoint** at autonomy `medium`/`high`: set `human_action_needed: yes` and do not dispatch the next checkpoint. "Addressed" is `accepted: yes` with the artifact edited, or `accepted: no` with a disposition — silence is not addressing it. Advisory at autonomy `low`.
- A gauntlet loop that stopped on `cap`, `no-progress` or `regression` sets `human_action_needed: yes` (`human_action_kind: review`) and names the open gap in `findings_summary`. A loop that stopped on `clear` needs no human action.
- Writing the summary triggers `progress-log`, which propagates it to `progress.md` and the tracker.
- **Ontology gate.** Before writing the handoff, run
  `${CLAUDE_PLUGIN_ROOT}/scripts/dae_ontology.py <feature-dir>`. It checks the
  mechanical constraints over the artifact graph — enumerations, functional
  properties, parent/child inverses, AC↔scenario coverage closure, and the
  Principle 7 disjointness — deterministically, in milliseconds, so they are
  checked *every* time rather than whenever someone remembers to run
  `consistency-check`. Errors block the checkpoint at autonomy `medium`/`high`
  (fix the artifact, re-run); warnings are surfaced and continue. Advisory at
  `low`. See `${CLAUDE_PLUGIN_ROOT}/references/ontology.md`.
- **Handoff-as-gate.** A checkpoint is not complete until its handoff exists, has `status: complete`, and asserts every `exit_criteria` entry `met: true`. A skill that advances checkpoint N+1 MUST verify checkpoint N is complete before starting — run `${CLAUDE_PLUGIN_ROOT}/scripts/dae_handoff.py <feature> --through N`. On a non-zero exit, stop and surface the gap to the human; do not proceed and do not auto-fix.

Full schema: [DAE Foundation Design](https://www.notion.so/3585ecdee0e2811bbc67ff4913c03207), Section 5.
