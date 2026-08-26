---
name: control
description: Use to open the control surface — a live, local web view of the project's feature pipeline + architecture map. Triggers — "/engineer.control", "open the control surface", "show the dashboard", "visualize the project", "pipeline board", "architecture map".
---

# control

Serve the **control surface**: a read-only, live web view of the project — a
feature × checkpoint **pipeline board** and an **architecture map** (layer nodes
+ import edges + health). It reads the same artifacts the pipeline writes; it
does not dispatch, edit, or write anything. This is the `render` capability
(`${CLAUDE_PLUGIN_ROOT}/references/host-capabilities.md`) as a served page.

## When to use

- `/engineer.control` — "where does everything stand?" across the whole project.
- After a work session, to eyeball pipeline progress and architecture health.

**Not for:** running/assigning/pausing work (management is not built yet — this
is visualization only); a single feature's status (`prime-context` / `next`).

## Workflow

1. **Resolve** the methodology root + effective `autonomy_level` via
   `${CLAUDE_PLUGIN_ROOT}/scripts/dae_resolve.py` (see `references/resolving.md`).
2. **Render rules** (`references/host-capabilities.md`): the served view is an
   **enhancement, never a gate**, and stays on `127.0.0.1` (feature names/paths
   are fine locally, never on a shared URL). A **terminal fallback always
   exists**: `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/dae_control.py --json <root>`
   prints the same state blob — use it when a browser isn't wanted or available.
3. **Launch** the server, keyed by autonomy:
   - `low` → ask once ("open the live control surface at 127.0.0.1?"), then go.
   - `medium`/`high` → launch and announce in one line.
   Run it backgrounded so the session stays interactive, e.g.
   `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/dae_control.py --port 8770 <root> &`,
   then surface the printed `http://127.0.0.1:PORT/` URL. If the port is taken
   the server falls back to an ephemeral one and prints that URL instead.
4. **Report** the URL and that it is read-only + live (auto-refreshes every few
   seconds). Remind the human to stop it (Ctrl-C / kill the process) when done.

## Notes

- Two tabs: **Pipeline** (every feature × the 9 checkpoints, status-colored,
  click a row for detail) and **Architecture** (layer nodes, actual import
  edges, `may_not_import` rules, violated edges in red, cycles flagged).
- The architecture map only shows real edges for languages `dae_arch` parses
  (`.py`/`.js`/`.ts`/…); layers over other languages render as nodes with no
  edges. Feature-relationship and roadmap views are not built yet.

## References

- `${CLAUDE_PLUGIN_ROOT}/references/host-capabilities.md` — the `render` capability + rules this obeys
- `${CLAUDE_PLUGIN_ROOT}/scripts/dae_control.py` — the server (reuses `dae_dashboard` + `dae_arch.graph`)
- `${CLAUDE_PLUGIN_ROOT}/references/resolving.md` — root + autonomy resolution
- [Direction — Human at the Ends & the Control Surface](https://app.notion.com/p/3c35ecdee0e2814f9f4bcdd21c7f206d) — why the surface exists (observability replaces middle gates)
