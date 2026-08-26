---
name: prototype
description: Use to rough out a working thing fast, zero ceremony, before committing to the pipeline — the prototype IS the spec. Triggers — "/engineer.prototype", "prototype this", "quick prototype", "spike it", "rough it out", "throwaway version", "let's prototype".
---

# prototype

The **prototype-first path** to a feature (see
`${CLAUDE_PLUGIN_ROOT}/references/two-paths.md`). Build a **rough working thing
fast** and **iterate it** — no feature list, no stories, just the concept and
rounds — until it converges. No ACs, no plan, no tests, no gates, no gauntlet:
there is nothing to grade against yet, because **the prototype is what
everything else will be graded against.** Most prototypes are learning; the ones
worth keeping **convert to spec** — reaching the *same* fully-specced, hardened
feature as spec-first, by build-then-spec instead of spec-then-build.

The **iteration loop is the point** — it is where the speed comes from. Expect
several rounds; the "one thing it must demonstrate" sharpens as you go.

Sits *before* `discuss`/`feature-init` in ceremony: `discuss` talks an idea
through; `prototype` builds it to find out. `discuss` and `feature-init` offer
this path as a first-class entry.

## When to use

- `/engineer.prototype "<idea>"` — spike an idea into a runnable rough cut.
- The core question is "what would this even look like / feel like / do?" and a
  paragraph of spec won't answer it but ten minutes of code will.

**Not for:** the real build (that's the pipeline, post-promote); anything that
must be correct, tested, or hardened; grading a prototype with the gauntlet
(there is no bar yet — this *is* the bar).

## Workflow

1. **Resolve + load** — methodology root + manifest via
   `${CLAUDE_PLUGIN_ROOT}/scripts/dae_resolve.py` (see `references/resolving.md`).
   Load `CHARTER.md` for the stack/conventions to build in, and the last ~15
   lines of `.engineer/prototypes.log` to soft-match against existing prototypes
   and Ready features (don't re-spike something that already exists).
2. **Frame in two lines** — the rough idea, and the **one thing it must
   demonstrate** (the question the prototype answers). Not a spec. Derive a
   kebab `slug` from the idea. If an idea arg was given, use it; otherwise ask
   once.
3. **Build rough** — construct the minimum runnable thing that answers the
   question. **Speed over quality:** hardcode, stub, fake data, skip error
   paths, no abstractions, no tests. Match the charter's stack so it's
   recognizable, but nothing here is load-bearing. Keep it **runnable** — a
   prototype that can't be opened/run is worthless as a bar. Build directly (or
   one born-die builder for a big one); **no multi-agent gauntlet, no CP gates.**
   Land it in `prototypes/<slug>/`; ensure `prototypes/` is in `.gitignore`
   (throwaway by default).
4. **Capture** — write `prototypes/<slug>/PROTOTYPE.md`: the idea, the one thing
   it demonstrates, **how to run it**, what's faked/stubbed/hardcoded, and the
   open questions it surfaced. This is the "prototype is the spec" record — the
   human-readable intent + result. Show the user how to see it (run command, or
   `SendUserFile` for a visual artifact). Append one line to
   `.engineer/prototypes.log`: `<ISO-timestamp> | <slug> | built | <one-line what>`.
5. **Decide (human)** — recommend an outcome; the user confirms. Never
   auto-execute.
   - **Iterate (the default while learning)** — rebuild with feedback, same dir,
     still zero ceremony (iteration 0.x). Update `PROTOTYPE.md`. Stay here for as
     many rounds as it takes — **convergence, not round count, is the exit.**
     This loop is where the speed lives; don't rush out of it.
   - **Discard** — `rm -rf prototypes/<slug>/`; log line
     `... | discarded | <why>`. The learning stays in the log.
   - **Convert to spec (promote)** — the concept has converged and earned a real
     build. This is the pivot from prototype-first into the pipeline (see
     `${CLAUDE_PLUGIN_ROOT}/references/two-paths.md`):
     a. Invoke `feature-init` with `feature_intake { status: ready, ... }` —
        seed `outcome`/`title` from `PROTOTYPE.md`, carry `size` if obvious.
     b. Copy `prototypes/<slug>/` → `features/NNN-<slug>/prototype/` (**tracked**,
        so the bar travels with the feature to any agent/host), and record
        `prototype: prototype/` in `feature.md` frontmatter. Discard the
        gitignored original.
     c. **Set the disposition (size-dialed)** — record
        `prototype_disposition: in-place | rebuild` in `feature.md` (defaulted
        from `size`, overridable): **S/M → `in-place`** (the prototype code is
        CP5's starting implementation; refine + verify + harden clean it);
        **L/XL or risky → `rebuild`** (CP5 implements fresh against the derived
        spec, with the prototype as the `gauntlet:` bar; its code is discarded).
     d. Hand off to `discover-acs` **in reverse-engineer mode** with the
        prototype + `PROTOTYPE.md` as the seed — this is "convert the artifact to
        ACs," the same RE mode onboarding uses. The prototype is **iteration
        0**; `plan` (CP4) reads `prototype:` and declares it as the `gauntlet:`
        bar (see `references/gauntlet.md`).
     e. Log `... | promoted | features/NNN-<slug>/`.

## Handoff

Promote emits per `${CLAUDE_PLUGIN_ROOT}/references/handoff-summary.md`,
`checkpoint: null` (pre-pipeline, like `discuss`). Iterate stays in the loop and
emits nothing. Discard is recorded by the log line only.

## References

- `references/two-paths.md` — the prototype-first vs spec-first model + the size-dialed convert disposition
- `references/gauntlet.md` — where a promoted prototype becomes the reference bar
- `references/resolving.md` — root + manifest resolution
- Sister skills: `discuss` (talk it through instead of building it), `feature-init`
  (invoked on promote), `discover-acs` (the handoff target).
- [Direction — Human at the Ends & the Control Surface](https://app.notion.com/p/3c35ecdee0e2814f9f4bcdd21c7f206d) — prototype = iteration 0, prototype-as-spec
