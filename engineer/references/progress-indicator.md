# Pipeline progress indicator — shared contract

Every checkpoint-advancing engineer skill surfaces *where you are* — passively,
as it runs — through two indicators. This file is the canonical contract;
skills reference it instead of inlining.

## Indicator 1 — the pipeline breadcrumb

At **Step 0**, after the entry gate passes (or, for `feature-init`, at the
start of the workflow), run:

    ${CLAUDE_PLUGIN_ROOT}/scripts/dae_progress.py <feature-dir>

and show its output to the human verbatim. It renders the feature's position
across the nine-stop DAE pipeline, plus where the feature sits *above* the
checkpoint altitude:

    DAE ▸ 015-image-formats
    ✓0 Onboard · ✓1.5 Ready · ✓2 ACs · ▶3 Spec · ·4 Plan · ·5 Implement · ·6 Refine · ·7 Verify · ·8 Harden
    CP3 Spec — 2/4 criteria met · NEXT: write spec.md
    ROADMAP ▸ image-formats (ready) · child of 012-media-pipeline

**Advisory, never blocking.** Unlike the `dae_handoff.py` entry gate, a
non-zero exit or a missing `progress.md` never stops the skill — the breadcrumb
is orientation, not a gate. Show whatever it prints and continue.

Where the engineer mods load, the same breadcrumb also sits in a band above
the prompt and redraws on every handoff write. Print it anyway: the band is an
enhancement, the printed breadcrumb is the contract.

### Render it on the way *out*, too

Run the breadcrumb again as the **last thing the skill does**, after the
handoff is written, and name the next checkpoint alongside it:

    DAE ▸ 015-image-formats
    ✓0 Onboard · ✓1.5 Ready · ✓2 ACs · ✓3 Spec · ▶4 Plan · ·5 Implement · ·6 Refine · ·7 Verify · ·8 Harden
    CP3 Spec — done · NEXT: /engineer.plan
    ROADMAP ▸ image-formats (ready) · child of 012-media-pipeline

Entry-only rendering answers "where am I" at the moment the human already
knows, and stays silent at the moment they don't: right after a checkpoint
closes. "Is this feature done? What's the next feature? How does this fit the
roadmap?" is a question asked *at a checkpoint boundary* — answer it there.

### The ROADMAP line

`dae_progress.py` is stdlib-only and offline, so it renders this line from
`feature.md` frontmatter alone — `roadmap_ref`, `status`, `parent_feature`,
`child_features`. A feature with no `roadmap_ref` renders `not linked to a
roadmap item`, which is itself actionable (`discuss` / `feature-init` can
promote one).

**Neighbouring items are the skill's job, not the script's.** Skills that
already hold a roadmap driver connection — `next`, `discuss`, `feature-init` —
extend the line with the item's position among its siblings ("2 of 5 in `now`,
next up: bulk-export") per `${CLAUDE_PLUGIN_ROOT}/references/roadmap.md`. Skip
silently when `manifest.roadmap.type` is `none` or the host is unreachable.

### Indicator 3 (optional) — the rendered board

"Where are we" is a question about a *structure*: several features, each at a
checkpoint, against a roadmap of horizons. Four lines of breadcrumb answer it one
feature at a time; a rendered board answers it at a glance and can be returned to
without re-running anything.

When the host provides the **render** capability (see
`${CLAUDE_PLUGIN_ROOT}/references/host-capabilities.md`), offer a board on a
project-scope survey — `next`, `progress-log --project`, or an explicit ask. Feed
it from the same JSON the terminal output already uses (`dae_handoff.py
--status`, `dae_progress.py`, the roadmap driver) — never compute a second
version of the truth for the pretty one.

Three rules keep it an enhancement rather than a dependency:

- **The terminal text is always emitted.** The board is additional. Never answer
  only through a channel the human may not open.
- **Never a gate.** No checkpoint waits on a board.
- **Ask once per session** at autonomy `low`; publish and mention it in one line
  at `medium`/`high`.

Hosts without the capability skip this silently — Indicators 1 and 2 are the
contract.

`onboard` (Checkpoint 0) is project-scope — it has no feature folder — so it
does NOT call the breadcrumb. It uses Indicator 2 only.

## Indicator 2 — the in-skill step tracker

At the start of the skill, create **one TodoWrite todo per workflow step**, all
at once — the full list up front, so it doubles as a roadmap of the journey
ahead. Flip each todo to `in_progress` when its step begins and `completed`
when it ends. The TodoWrite panel is the live position indicator.

A step that spans many turns — an interview-style step such as the four-pass
AC interview — is split into **one sub-todo per pass**, so a long step shows
visible movement instead of sitting at `in_progress` for ten turns.

**Parallelism check (planning-time reflex).** As you build the roadmap, run each
set-valued step through the parallelism reflex —
`${CLAUDE_PLUGIN_ROOT}/references/parallelism.md`. It decides, from *this*
feature's actual work, whether the step decomposes into independent units (or
would gain from a multi-agent quality pattern) and, if so, offers the right
substrate — parallel subagents or a dynamic workflow — per the feature's
`autonomy_level`. Scalar or single-item steps skip it silently: no offer, no
noise. Discovery is per-run — never hardcode which steps fan out.

## The canonical pipeline

`0 Onboard · 1.5 Ready · 2 ACs · 3 Spec · 4 Plan · 5 Implement · 6 Refine ·
7 Verify · 8 Harden`. `dae_progress.py` holds this list as its source of truth;
`5 Implement` and `8 Harden` are pipeline stops with no dedicated skill.
