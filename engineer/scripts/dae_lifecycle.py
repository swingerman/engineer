#!/usr/bin/env python3
"""dae_lifecycle.py — publish the DAE pipeline as machine-readable lifecycles.

DAE's pipeline is a fact about DAE. Every tool that wants to show where a piece
of work sits — a board, a dashboard, another agent — otherwise keeps its own
copy of the nine checkpoints and their order, and that copy is wrong the day
CP1.5 is renamed. This prints the pipeline instead, so those tools can ask.

The stage order and names come from `dae_progress.CHECKPOINTS`, which is already
this repo's single source of truth for them. Nothing here restates them.

Exit criteria are deliberately absent. DAE's real criteria live in each
project's charter and arrive on the handover at runtime, so a definition that
carried them would be describing one project rather than the process.

Usage:
  dae_lifecycle.py            print the lifecycles as JSON on stdout
"""
import json
import sys

from dae_progress import CHECKPOINTS

# Per checkpoint: the skills that own it, the gate that follows it, and what an
# agent picking the work up there is told. Keyed by the checkpoint numbers in
# dae_progress.CHECKPOINTS so a renamed stage cannot silently lose its brief.
#
# CP0 Onboard is excluded: it is project scope, not feature scope, and runs
# without a feature folder. Listed as stage zero it would make every new feature
# read "not started: adopt the methodology".
FEATURE = {
    1.5: (["/engineer.clarify"], "decision", "decision",
          "Resolve what is still ambiguous, and stop when a decision is needed "
          "rather than guessing."),
    2: (["/engineer.discover-acs"], "review", "decision",
        "Discover the acceptance criteria. They are the contract everything "
        "downstream is graded on."),
    3: (["/engineer.atdd"], "none", "decision",
        "Formalise the criteria as specs and generate the test pipeline."),
    4: (["/engineer.plan"], "approval", "decision",
        "Plan the implementation against the specs, then stop for approval "
        "before writing code."),
    5: (["atdd:atdd-team"], "none", "decision",
        "Implement against the specs. The specs decide when this is finished, "
        "not your judgement of it."),
    6: (["/engineer.refine"], "none", "decision",
        "Refine the changed code without changing what it does."),
    7: (["/engineer.arch-check", "/crap-analyzer"], "review", "review",
        "Verify the work against the charter. You did not implement this; do "
        "not defend it."),
    8: (["atdd:atdd-mutate"], "none", "shipping",
        "Harden: check the tests actually fail when the code is wrong."),
}

# What prototype-first changes, and only that. Same checkpoints, entered
# differently — see references/two-paths.md. CP5 onward is identical, which is
# why it is absent here.
PROTOTYPE_OVERRIDES = {
    2: (["/engineer.discover-acs"], "review", "decision",
        "Reverse-engineer the acceptance criteria from the converged "
        "prototype. The prototype is the evidence; do not invent criteria it "
        "does not demonstrate."),
    3: (["/engineer.atdd"], "none", "decision",
        "Derive the specs from the prototype and the criteria. The prototype "
        "is the gauntlet bar the result must match."),
    4: (["/engineer.plan"], "approval", "decision",
        "Retrofit the architecture from the prototype's shape, then stop for "
        "approval."),
    5: (["atdd:atdd-team"], "none", "decision",
        "Read `prototype_disposition` on feature.md. `in-place` — the "
        "prototype code is the starting implementation. `rebuild` — implement "
        "fresh against the derived spec and throw the prototype away."),
}

# Every agentic stage opens the same way. A stage whose agent has not said what
# done looks like has no way to know when to stop, and the human reviewing it
# has nothing to review against.
GOAL_PREAMBLE = (
    "Start by setting the goal for this stage with `/goal`, including an "
    "explicit definition of done. State it before you touch anything.\n\n"
)


def stage(sid, label, skills, gate, attention, pick_up, blurb):
    return {
        "id": sid,
        "label": label,
        "blurb": blurb,
        "owner": "agent",
        "detect": [{"from": "record"}],
        "artifacts": [{"label": "A handover record", "required": True}],
        "exit": [],
        "gate": {"kind": gate},
        "pickUp": GOAL_PREAMBLE + pick_up,
        "skills": skills,
        "attention": attention,
    }


def sid(num):
    """The id the handover writes: '1.5' stays '1.5', 2.0 becomes '2'."""
    return str(num)


def entry_stage():
    """The entry, which is not a checkpoint: feature-init creates the folder.

    Prototype-first skips it — there the folder is created by the convert pivot
    once the prototype has converged.
    """
    return stage(
        "feature", "Feature", ["/engineer.feature-init"], "none", "decision",
        "Create the feature and state the outcome it is meant to produce.",
        "The folder exists and the outcome is written down.",
    )


def feature_stages(overrides=None):
    """The pipeline from CHECKPOINTS, with prototype-first substitutions."""
    table = dict(FEATURE)
    table.update(overrides or {})
    out = []
    for num, label in CHECKPOINTS:
        if num == 0:  # Onboard — project scope, see the note above.
            continue
        if num not in table:
            continue
        skills, gate, attention, pick_up = table[num]
        out.append(stage(sid(num), label, skills, gate, attention, pick_up,
                         f"CP{sid(num)} — {label}."))
    return out


def prototype_stages():
    """Iteration 0 in front, then the pipeline entered as derive-from-artifact."""
    zero = stage(
        "prototype", "Prototype",
        ["/engineer.prototype"], "decision", "decision",
        "Iterate a rough artifact fast, concept only, until it answers what "
        "this should be. No feature list, no stories. Stop when it converges "
        "and say so — a human decides whether it has.",
        "Iteration 0: build the thing until the concept is proven.",
    )
    return [zero] + feature_stages(PROTOTYPE_OVERRIDES)


FIX_STAGES = [
    ("reported", "Reported", "Someone says it is broken.", "none", "decision",
     "Establish what is actually broken, in terms of observed behaviour."),
    ("reproduced", "Reproduced", "It fails on demand.", "review", "decision",
     "Reproduce it, ideally as a failing test. Stop and show the failure."),
    ("fixed", "Fixed", "It passes, and the suite still does.", "none", "decision",
     "Fix it. The reproduction is what says you are done."),
    ("gap_closed", "Gap closed", "Why the tests let it through.", "review",
     "shipping",
     "Answer why this was not caught — missing criterion, missing spec, or "
     "missing test — and close that gap."),
]


def lifecycles():
    return [
        {
            "id": "feature",
            "label": "DAE feature",
            "blurb": "Spec-first: decide the criteria up front, then build to them.",
            "stages": [entry_stage()] + feature_stages(),
        },
        {
            "id": "prototype",
            "label": "DAE feature (prototype-first)",
            "blurb": "Build first, then derive the criteria from what converged.",
            "stages": prototype_stages(),
        },
        {
            "id": "fix",
            "label": "DAE fix",
            "blurb": "A defect through reproduction, fix, and why it was not caught.",
            "stages": [
                stage(s, label, ["/engineer.fix"], gate, attention, pick_up, blurb)
                for s, label, blurb, gate, attention, pick_up in FIX_STAGES
            ],
        },
    ]


def main():
    json.dump(lifecycles(), sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
