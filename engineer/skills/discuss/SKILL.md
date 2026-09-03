---
name: discuss
description: Use when exploring a feature idea before committing, or revisiting a parked one. Triggers — "/engineer.discuss", "/engineer.discuss <slug>", "I have an idea about", "should we build", "let's think about".
---

# discuss

The upstream funnel of DAE — a divergent brainstorm (forked from `superpowers:brainstorming`) that ends in one of three outcomes: **drop**, **park**, or **promote**. Most ideas die here; some park as `features/NNN-slug/` with `status: parked`; survivors promote to `status: ready`.

## When to use

- **Fresh** — `/engineer.discuss`, no argument. New exploration.
- **Continue** — `/engineer.discuss <slug>`. Resume a parked feature.

**Not for:** feature-work prep on an already-Ready feature (`prime-context`), or editing a committed feature (`feature-edit`).

## Workflow

1. **Resolve + load** — resolve the methodology root + manifest via `${CLAUDE_PLUGIN_ROOT}/scripts/dae_resolve.py` (see `references/resolving.md`). Load `CHARTER.md` and the last ~20 lines of `.engineer/discussions.log`. With a slug arg: also load that feature's `feature.md` + prior `handoffs/*-discuss.md`; reject if its status is `ready`/`in-progress` (→ `feature-edit`) or `done`.
2. **Open** — **if handed an `intent.md`** (an originator-authored intent, see `${CLAUDE_PLUGIN_ROOT}/references/intent.md`), read it as the opening context instead of a cold prompt, reflect the synthesis back, and continue from there — the async front door for originators who don't want an interactive session. Otherwise, fresh: "What are you thinking about?" After the first prompt, soft-match the topic against parked feature titles/areas **and against roadmap items** (driver per `references/roadmap.md`; `local` = `${CLAUDE_PLUGIN_ROOT}/scripts/dae_roadmap.py list`); if it matches a planned roadmap item, say so and offer to promote *that* item (carry its `id` as `roadmap_ref`) rather than starting a disconnected idea. Continue mode: echo prior state in one line, then resume.
3. **Brainstorm (divergent)** — explore intent, scope, alternatives; one question per turn. Surface charter signals (e.g. payment paths cap autonomy), ADR connections, and "too big — decompose?" flags as they arise.
4. **Surface the outcome** — at a natural inflection, recommend an outcome (promote / prototype / park / drop); the user confirms. Never auto-execute. If the user says "drop" but there's a concrete reason it's worth parking, ask once. **When the idea is fuzzy, UX-heavy, or "I'll know it when I see it" — better answered by building than by talking — recommend the prototype path** (`${CLAUDE_PLUGIN_ROOT}/references/two-paths.md`): iterate a rough artifact fast, convert to spec later, same hardened end state.
5. **Execute the outcome:**
   - **Drop** — append one line to `.engineer/discussions.log`: `<ISO-timestamp> | <slug> | dropped | <one-line why>`. Draft the "why" from context; user confirms/edits.
   - **Prototype** — the idea is better built than specced: hand to the `prototype` skill (`/engineer.prototype "<idea>"`) instead of `feature-init`. It iterates fast, then *converts to spec* (promote) into the pipeline later — the prototype-first entry (`${CLAUDE_PLUGIN_ROOT}/references/two-paths.md`). Do not create a feature here; `prototype`'s promote does that on convergence.
   - **Park** — invoke `feature-init` with `feature_intake { status: parked, autonomy_level: null, ... }`.
   - **Promote** — first resolve `autonomy_level` (low/medium/high, charter caps surfaced); if the user can't decide, fall back to park. Then invoke `feature-init` with `status: ready`. **If the idea came from a roadmap item**, pass its `roadmap_ref` so `feature-init` back-links and marks it in-progress (see `references/roadmap.md`).
   - **Keep the roadmap alive** — when an idea is too big and decomposes into several future features, or you park something strategically worth tracking at the feature-list altitude, offer once to add it as a **roadmap item** (driver `upsert`, `status: planned`, a horizon) so the strategic layer stays current beyond onboard-time. The user's call — never auto-add. Skip silently if `manifest.roadmap.type` is `none`/unreachable.
6. **Handoff** — for park/promote, write a `<timestamp>-discuss.md` handoff into the new feature folder. For drop, the log line is the record — no handoff.

**Continuing a parked feature:** each session appends a new discuss handoff; `feature.md` is refined in place. Promoting a continued feature flips status to `ready` directly — `feature-init` is not re-invoked.

## Handoff

For park/promote, emit per `${CLAUDE_PLUGIN_ROOT}/references/handoff-summary.md`. `checkpoint: null`. Drop emits no handoff.

## References

- [Discuss & Upstream Funnel](https://www.notion.so/35a5ecdee0e281eaa35fced0c4e23384) — funnel, drop-log format, park/promote paths
- [Foundation Design](https://www.notion.so/3585ecdee0e2811bbc67ff4913c03207) — feature.md schema, autonomy levels
- `references/roadmap.md` — the roadmap ↔ feature funnel (promote from / keep alive)
- Sister skill: `feature-init` (invoked for park/promote).
