# Roadmap drivers

How DAE skills read and write the **roadmap** — the strategic feature-list
altitude. The roadmap answers *"what do we intend to build, in what order"*; it
is a **feature list, not a task list**. It sits *above* the tracker:

| Layer | Artifact | Altitude | Driver |
|---|---|---|---|
| **Roadmap** | `RoadmapItem`s | strategic — candidate features by horizon | this reference |
| **Tracker** | `TrackedFeature`s | execution — in-flight features + checkpoints | `references/tracker.md` |

A roadmap item is a *candidate* feature. When work begins it **promotes** into a
`features/NNN-slug/` (via `discuss` / `feature-init`); the item then carries a
`feature_slug` back-link and tracks its lifecycle (`planned → in-progress →
shipped`). The roadmap is the forward-looking complement to
`.engineer/consolidation.md` (which is the *backward*-looking coverage backlog
for features that already exist).

`manifest.roadmap.type` selects the driver: `local | notion | confluence |
gdoc | github-projects | other | none`. It is chosen **independently of the
tracker** — the two live in separate manifest blocks and routinely differ (a
project's roadmap may be a Notion *page* while its tracker is a Notion *DB*).

## The reachability precondition

**A roadmap can only be onboarded if DAE can reach its host
programmatically** — a connected **MCP**, an installed+authed **CLI**, or a
usable **API**. A roadmap DAE cannot read can't answer "what's next from the
roadmap," so there is no half-support: if the host is manual-only, the roadmap
is **not onboarded** (`type: none`), and `onboard` surfaces exactly what to
connect to enable it later. This mirrors the tracker's "MCP-backed and not
connected → fail fast" rule.

`local` is the only always-reachable host (it's a repo file, zero deps) — so it
is the greenfield default and the safe fallback.

## The `RoadmapItem` record

One per candidate feature. DAE-managed fields:

`id`, `title`, `area`, `horizon` (`now | next | later`), `priority` (int, lower
= sooner within a horizon), `status` (`planned | in-progress | shipped |
dropped`), `feature_slug` (back-link once promoted, else null), `notes`.

`id` is a stable kebab identifier — DAE assigns it (derived from the title) the
same way it owns feature slugs. Deliberately lighter than `TrackedFeature`: no
checkpoint, no autonomy, no assignee — those belong to the execution layer the
item promotes *into*.

## Two host shapes

Hosts fall into two shapes, which the driver treats differently:

- **Structured** — Notion DB, the `local` file, (later) GitHub Projects, Linear
  / Jira epics. DAE reads/writes `RoadmapItem` **fields** directly.
- **Doc** (prose) — a Notion *page*, Confluence, a Google Doc, a markdown file.
  DAE owns a delimited **managed block** and parses/rewrites only that block,
  never the human's surrounding prose. The markers:

  ```
  <!-- DAE-ROADMAP -->
  ... DAE-managed RoadmapItems ...
  <!-- /DAE-ROADMAP -->
  ```

  This managed-block discipline is what makes **read+write safe on a prose
  page** — the same contract the tracker uses ("write only DAE-managed fields,
  never touch human comments/labels").

## The `local` driver

The feature folder's repo *is* the roadmap host: items live in
`<root>/.engineer/roadmap.md` inside the managed block. A stdlib-only script:

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/dae_roadmap.py list [START_DIR]
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/dae_roadmap.py read ID [START_DIR]
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/dae_roadmap.py next-unstarted [START_DIR]
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/dae_roadmap.py upsert [START_DIR]   # JSON on stdin
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/dae_roadmap.py mark ID STATUS [FEATURE_SLUG] [START_DIR]
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/dae_roadmap.py init [START_DIR]     # create empty block
```

`list` → sorted `RoadmapItem` array; `next-unstarted` → the top startable item
(`status: planned`, no `feature_slug`, by horizon then priority) or `null`;
`upsert` / `mark` write the managed block, preserving any human prose outside
it.

## The `notion` driver

Requires a **Notion MCP connected**. `manifest.roadmap` carries the page or
database ref (`url` for a page, `database_id` for a DB — auto-detect by which is
present). Map the operations onto whatever the connected Notion MCP exposes:

| Operation | Notion (page / doc-host) | Notion (database) |
|-----------|--------------------------|-------------------|
| `list` / `read` | fetch the page, parse the `<!-- DAE-ROADMAP -->` block | query the data source, map columns ↔ `RoadmapItem` |
| `upsert` | rewrite only the managed block, leave surrounding blocks | create/update the row matched by `id` |
| `mark` | update the item's line in the managed block | patch `status` / `feature_slug` on the row |
| `next-unstarted` | first `planned` + unpromoted in the block | filter the query the same way |

Exact MCP tool names vary by version (page-fetch, page-update, …). Use whatever
the connected Notion MCP exposes.

## Reserved hosts — `confluence`, `gdoc`, `github-projects`

Named and selectable today; onboardable **iff** the matching MCP/CLI is present
(a Confluence MCP, a Google Docs/Drive MCP, the `gh` CLI). When the channel is
present DAE drives them generically via the doc-host or structured contract
above — no hand-written native driver required. When it is absent, `onboard`
records the intent but sets `type: none` until the channel is connected.

## The `other` host

The graceful catch-all for a platform DAE has no named entry for (Trello,
Monday, Asana, …). Because of the reachability precondition, `other` **must
declare its access channel** so DAE knows *how* to reach it. Manifest:

```yaml
roadmap:
  type: other
  platform: Trello            # required — the hosting platform's name
  url: https://trello.com/b/… # required — pointer to the roadmap
  access: mcp                 # required — mcp | cli | api
```

Missing `platform` / `url` / `access` → the manifest is invalid (see
`dae_resolve.py` `_validate_roadmap`). `other` is **upgradeable in place** — once
a host gets a named entry, swap `type: other` → the named type; no data move.

## `none`

Explicit opt-out, **or** the forced result when no reachable channel exists.
`next` simply omits the roadmap altitude and notes why.

## Migration — `onboard`'s three paths

The roadmap is light (a feature list), so unlike per-feature ATDD-coverage
migration it is done **inside `onboard`**, not deferred. After the host is
chosen, `onboard` branches on what it discovers:

| Situation | Path |
|---|---|
| Source already in DAE shape on the chosen host | **Link** — record the ref |
| Source exists in a different place/shape/platform (`ROADMAP.md`, a prose Notion page, GH milestones) | **Migrate** — parse → write `RoadmapItem`s to the chosen host |
| No source found | **Create** — seed from the triaged feature discovery |

**Migration mechanics:**

- **Discover** roadmap-shaped sources read-only, like feature discovery:
  `ROADMAP.md` / `docs/roadmap.md` / a `## Roadmap` README section; a Notion
  page or DB named "Roadmap"; GitHub milestones, a Projects board, or
  `epic`/`roadmap`-labelled issues; an existing `manifest.roadmap` ref.
- **Parse** the source into `RoadmapItem`s best-effort (prose/bullets →
  `{title, area, horizon, priority, status, notes}`); the human confirms/edits
  the parsed list — it's a strategy artifact, same sign-off discipline as the
  charter.
- **Cross-host is supported** — source and target needn't match (a markdown
  `ROADMAP.md` *into* a Notion managed block, or vice versa).
- **Join to discovered features** — items that map to already-shipped /
  in-progress code (from `onboard` Step 7) get `status: shipped` /
  `in-progress` + a `feature_slug` back-link, so the roadmap reflects reality on
  day one rather than re-listing done work as "planned."
- **Source disposition** — leave the original in place and link it
  (`migrated_from`), or, with consent, replace it with a pointer. **Never
  silently delete.**

## The roadmap ↔ feature funnel

- **Promote** — `discuss` / `feature-init` turns a roadmap item into a feature:
  write `roadmap_ref: <id>` into `feature.md`, and `mark <id> in-progress
  <slug>` back on the roadmap (no duplicate item — reuse it, exactly like
  *Tracker-as-intake*).
- **Ship** — the ship commit (`dae_ship.py`, last commit on the feature branch,
  written by harden / express) marks the roadmap item `shipped`
  (`dae_roadmap.py mark <ref> shipped`), so it reaches main with the merge.
  Post-merge writes no roadmap change.
- **Keep alive** — when `discuss` parks an idea or scope decomposes into several
  features, offer to record them as roadmap items so the strategic layer stays
  current beyond onboard-time.

## Sync direction — local-wins, prose preserved

Like the tracker: two-way, **local-wins on DAE-managed fields**
(`feature.md`/`progress.md` are authoritative; the roadmap item's lifecycle
follows them). Human prose outside the managed block — and on structured hosts,
human-owned columns/comments — is never touched and survives every sync.

If the host later goes unreachable (MCP disconnected, CLI removed), `next`
**degrades gracefully**: it skips the roadmap altitude with a one-line note
rather than erroring.

## References

- `references/tracker.md` — the execution-layer sibling; `TrackedFeature`,
  local-wins, tracker-as-intake (the funnel pattern reused here)
- `scripts/dae_roadmap.py` — the `local` driver (+ `test_dae_roadmap.py`)
- [Foundation Design](https://www.notion.so/3585ecdee0e2811bbc67ff4913c03207) —
  feature.md schema (`roadmap_ref`), storage layout
