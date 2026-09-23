---
name: onboard
description: Use to bring a project into the DAE methodology, or to check an onboarded project for gaps. Triggers — "/engineer.onboard", "onboard this project", "set up DAE here", "adopt the methodology", or when a DAE skill fails because no manifest exists.
---

# onboard

Checkpoint 0 — the DAE adoption ceremony. Establishes the charter, manifest, storage layout, and tracker. Project-scope, run once. Every other DAE skill depends on what it produces.

**The goal.** Onboarding a project to DAE succeeds when there is a clear path to **full ATDD coverage of every feature — existing and new.** A new feature is born covered by going through the pipeline. An *existing* feature is covered retroactively.

**Onboarding is discovery and goal-setting — not the ATDD adoption itself.** It discovers what's there (documented *and* undocumented), triages it by importance, assigns each feature a status, and produces a **consolidation backlog**. Bringing any one feature to full ATDD coverage is a *follow-up task per feature* — bounded, automatable, and a good candidate for remote-agent dispatch. Onboarding sets the path; it does not walk it.

A feature is **fully ATDD-covered** when its folder has `feature.md`, `acs.md`, `spec.md` (+ `.build/spec.json` IR), and **generated acceptance tests that pass against the code**.

## When to use

- **No `.engineer/manifest.yml`** → full onboard (Steps 1–11)
- **Manifest exists** → gap-check mode (validate, report gaps, don't re-onboard)

**Not for:** starting a feature (`discuss` / `feature-init`, after onboard); changing an existing charter (edit it directly, PR'd).

## Human-decision checkpoints

Onboarding is a **ceremony**, not a mechanical scaffold. Three of its outputs are *design decisions* reserved for the human — the agent drafts, the human decides:

- **The charter** (Step 3) — architecture, conventions, scope, quality and autonomy stance.
- **The tracking decision** (Step 5) — which tracker the project uses.
- **The roadmap decision** (Step 5b) — which platform hosts the strategic roadmap, and (if one already exists) how it's migrated in. Strategy is a human call, like the charter.

Pre-filling from an existing codebase is encouraged. **Rubber-stamping is not.** Onboarding does NOT complete until the human has explicitly signed off on the charter and chosen the tracker and roadmap host — exactly as `plan` does for architecture (agent proposes, human confirms before proceeding). If the human is not available to decide, stop and emit a handoff with `human_action_needed: decision` — do not auto-decide and move on.

## Workflow (full onboard)

Before the steps below, create one TodoWrite todo per workflow step (the full
list up front, as a roadmap) — see
`${CLAUDE_PLUGIN_ROOT}/references/progress-indicator.md`, Indicator 2. `onboard`
is project-scope and has no feature folder, so it does not show the pipeline
breadcrumb.

1. **Repo topology** — ask single- vs multi-repo. Set `methodology_root` (and `repos[]` for multi-repo).
2. **Discover validation infrastructure.** Before drafting the charter, probe what's available — the findings inform the autonomy stance.
   - **LSP probe.** Walk the repo for language signals (file extensions; package files: `requirements.txt`, `pyproject.toml`, `package.json`, `Cargo.toml`, `go.mod`, `pom.xml`, `*.csproj`, …). Aggregate primary languages. Inspect the agent's available tool list for an LSP capability (per `${CLAUDE_PLUGIN_ROOT}/references/code-lookup.md`). Report per-language: LSP backing reachable? For absent ones, suggest the standard install (`pyright`, `gopls`, `typescript-language-server`, `rust-analyzer`, etc.). Inform-only — never blocks. Record the per-language map in `manifest.validation.lsp.servers` (languages the user skips are omitted; the fallback ladder handles them).
   - **CLI probe.** Walk the repo for tooling signals → likely CLIs (`gh`, `aws`, `gcloud`, `az`, `kubectl`, `helm`, `terraform`, `docker`, …) per `${CLAUDE_PLUGIN_ROOT}/references/cli-probe.md`. `which`-check each candidate. Report two lists: **available** (found on PATH) and **suggested** (project signals indicate it'd be useful but it's missing — surface the install command from the reference). Record both in `manifest.validation.clis.{available, suggested}`. Inform-only — never blocks; the human installs. Don't suggest CLIs without project signals (no `aws` smell → don't ask about `aws`). The CLI probe runs **before** the environments interview because the available CLIs can help with that next step.
   - **Environments interview** (all optional, batched in one `AskUserQuestion`): staging URL + deploy process; prod URL + deploy process + monitoring dashboards + alerting; feature-flag tool (`launchdarkly | unleash | flagsmith | growthbook | other`) + rollout policy. Record in `manifest.validation.{staging, prod, feature_flags}`. "Not yet" / "n/a" is a valid answer that omits the field. Where a relevant CLI from the probe is **available**, the agent should ask (consent-gated) whether to use it to discover or confirm env info — `gh` for deploy workflows, `gcloud` for GCP envs, `kubectl` for namespaces, etc. — rather than asking the human to type everything. **Capture what actually ships, not a prose summary:** read the real deploy config (`deploy.yaml`, the CI release job) and record the precise model — *which artifact ships on which trigger* (e.g. "ships `master`'s latest build regardless of the release tag"). An inaccurate deploy summary once nearly shipped untested hotfix code. If the project has **no staging**, also record a safe-deploy recipe in `manifest.validation.prod`: verify the exact artifact/commit that will ship *before* shipping (cherry-pick or build-and-inspect) — there's no staging to catch a wrong artifact.
   - **Remote-agent readiness.** Probe whether the project can delegate checkpoints to *cloud* Claude agents (vs. local subagents only):
     - **Automatable signals:** `git remote get-url origin` — is the repo on a clonable host (github.com / a connected GHES)? Scan the repo's `.mcp.json` for `type: stdio` servers — a **project-wide cloud blocker** (stdio MCPs don't exist in the cloud VM), so flag it. These mirror the per-feature `dae_delegable.py` gate.
     - **Human one-time setup** (DAE cannot automate this — surface it as a checklist the human confirms once): connect GitHub to claude.ai (`/web-setup`); create a cloud environment at claude.ai/code. *Optional:* install the Claude GitHub App on the repo (for PR/webhook triggers); create a routine (for `RemoteTrigger`-fired async/scheduled work — there is **no create API**, only the claude.ai UI).
     - Record `manifest.remote`: `ready: <true|false>` (human confirms the one-time setup is done), `channel: <isolation-remote | routine | none>` (primary cloud vehicle; default `isolation-remote` — it needs no pre-created routine), `stdio_mcp_blocker: <true|false>`, and free-text `notes`. Inform-only — never blocks onboarding; when `ready` is false the dispatch router simply stays local (see `references/handoff-dispatch.md`).
   - **Autonomy proposal** for Step 3's charter draft, based on what was found:
     - staging + monitoring + feature flags → "high autonomy is well-supported by the validation infrastructure"
     - staging + monitoring, no feature flags → "medium-to-high; pre-declare rollout paths in plans"
     - staging only, no monitoring → "medium; add monitoring to expand the ceiling"
     - none of the above → "low-to-medium until validation surface grows; recommend setting up staging + monitoring as an upstream backlog item"

     The proposal is a recommendation — the human signs off (or overrides) at Step 3.
   - **Probe for project infrastructure.** Before drafting the manifest, scan the repo for declarable infra dependencies and propose entries the human can accept/edit:

     | Signal in repo | Suggested infra entry |
     |---|---|
     | `firebase.json` present | One entry per emulator group (`firebase emulators:start --only <group>`), health probe on the documented port (auth: 9099, firestore: 8080, functions: 5001) |
     | `docker-compose.yml` / `compose.yml` | One entry per published service, health probe on the published port |
     | `package.json` scripts matching `dev*`, `start:dev`, `emulator*`, `serve*` | Entry using `npm run <script>`, with health probe on the documented port |
     | `Makefile` targets matching `dev`, `up`, `start-*`, `emulator*` | Entry using `make <target>` |
     | chromedriver-related deps in `package.json` / `requirements.txt` / `Gemfile` | Entry for chromedriver with TCP probe on 9515 |

     Present each draft entry to the human for confirmation, then add the approved entries to the manifest's `infra:` section per the schema (see `engineer/references/handoff-dispatch.md` + the schema in `engineer/scripts/dae_resolve.py:_validate_infra`).

     Discovery is best-effort. If a project's infra doesn't fit the patterns above, ask the human to declare it manually — the declaration discipline is what makes downstream skills reliable.

   - **Capture infra quirks.** After the infra entries are confirmed, batch one `AskUserQuestion` covering project-level runtime quirks that downstream skills need to know but can't discover from files:

     | Quirk | Why it matters |
     |---|---|
     | `runtime_pins` (e.g. `java: 21`, `node: 20.x`) | Wrong version → silent runtime failures (nexthq: Java 21 was rediscovered every session). |
     | `port_map_file` (path or "none") | If the user keeps a port-allocation file (e.g. `~/.<project>-ports.md`), record its path so fix/atdd consult it before booting (nexthq). |
     | `framework_constraints` (free-text list) | Things like "Flutter web has no hot-reload", "Apache opcache requires cold restart after schema changes" — surface to the agent before it loops on confusing symptoms (mmc Apache, nexthq Flutter). |
     | `recovery_commands` (map of `symptom: command`) | Known fixes for known hangs (e.g. `coresimulator_wedged: killall -9 com.apple.CoreSimulator.CoreSimulatorService`). |
     | `worktree_preview` (str, or omit) | If the running app is served from a checkout via a mount (a `THEME_PATH`/`.env` pointer, a bind-mount, a symlink), record how to point it at a **worktree/branch** — otherwise previewing a DAE worktree forces a costly live mount-switch every design chunk (modugon `THEME_PATH`). Omit when the worktree is served directly. |

     Write the answers into `manifest.infra_quirks` — a project-level block consulted by `engineer:fix` Step 4, `atdd:atdd` test runs, and `engineer:onboard` gap-check. `dae_resolve.py` validates schema. Quirks are advisory metadata, not health probes — they exist so the next agent doesn't rediscover the same friction.
3. **Draft the charter, get sign-off** — draft `CHARTER.md`'s 7 mandatory sections (methodology, architecture, conventions, scope, agent team, quality stance, autonomy stance). For an existing codebase, pre-fill what's inferable from the repo. Then present it and get the human's explicit confirmation — section by section for the judgment-heavy ones (scope, quality stance, autonomy stance + path overrides). Do not proceed to Step 4 until the charter is signed off.
4. **Create the manifest** — fill `.engineer/manifest.yml` (paths, roadmap/tracker, team, repos, quality thresholds, mutation, verification, autonomy, remote, agentic_summary). Optional `introversion:` block tunes the harden-time vacuous-test scan (`backend:` = a test-introversion analyzer command like `deintroverter`; `skip: true` to opt out) — see `engineer/scripts/dae_introvert.py`. Optional `harden:` block: `required: true` makes every check the CP8 refinement-advisor recommends mandatory (the human can add checks but not drop them; default `false`). Who picks the checks is not configured here: it follows effective autonomy, and at `high` the advisor decides alone. `mutation.default_per_feature` is retired; `dae_resolve` warns if it is still set. `quality_thresholds.mutation_score_min` is a percentage, 0–100.
5. **Tracking decision** — this is a human decision, not an agent default. Surface what the project appears to use (e.g. a repo full of Notion links → Notion) and ask the human to choose: `notion | github-projects | linear | jira | local`. `notion`: requires a connected Notion MCP — use it to create the tracker database (the `TrackedFeature` schema) or validate an existing one; DAE stores no API key (the MCP owns auth). `local`: feature folders are the tracker. Others: reserved — emit "not yet implemented". Never silently default to `local` to keep things moving. **Pre-flight the chosen host before writing it into the manifest** — confirm auth + connectivity + plan-tier (e.g. Notion's data/query tools need a Business plan; a Jira-only Atlassian grant 404s on Confluence) per `${CLAUDE_PLUGIN_ROOT}/references/driver-preflight.md`; fall back rather than commit a host DAE can't actually drive. When creating or validating the schema, include a `Type` column (`bug | idea | task`, optional) and an `Inbox` value in the status options, and tell the human the **capture flow**: add a task directly to the tracker as a row with no `Slug` (and optionally `Status: Inbox`) and `next` will triage it — see *Tracker-as-intake* in `references/tracker.md`. See `references/tracker.md`.
5b. **Roadmap decision** — the strategic feature-list altitude, chosen *independently* of the tracker (see `references/roadmap.md`). A human design decision.
   - **Reachability precondition first.** A roadmap is onboardable only if DAE can reach its host programmatically — a connected **MCP**, an installed **CLI**, or a usable **API** (reuse the Step 2 CLI/MCP probe results). A manual-only host **cannot be onboarded**: record `roadmap.type: none` and tell the human exactly what to connect to enable it later. No half-support. Beyond reachability, **pre-flight auth + plan-tier of the specific product** per `${CLAUDE_PLUGIN_ROOT}/references/driver-preflight.md` (Notion data tools need Business; a Jira-only grant 404s on Confluence). The **Jira driver is reserved/unimplemented** — a Jira source of truth falls back to `local` until it's built; that's a declared limitation, not a bug.
   - **Choose & record the host** — surface what the repo appears to use, then ask the human to pick `roadmap.type`: `local | notion | confluence | gdoc | github-projects | other | none`. `local` (a managed block in `.engineer/roadmap.md`) is always reachable and the greenfield default — don't force a host prompt on an empty project. `notion` needs the Notion MCP. `confluence | gdoc | github-projects` are onboardable iff their MCP/CLI is present (else `none`). `other` requires `platform:` + `url:` + `access: mcp|cli|api` in the manifest. Write the chosen block to `manifest.roadmap`.
   - **Then link / migrate / create** (see *Migration* in `references/roadmap.md`):
     - **Discover** roadmap-shaped sources read-only — `ROADMAP.md` / `docs/roadmap.md` / a `## Roadmap` README section; a Notion page or DB named "Roadmap"; GitHub milestones / Projects / `epic`-labelled issues; an existing `manifest.roadmap` ref.
     - **Link** if a source is already in DAE shape on the chosen host. **Migrate** if a source exists elsewhere/in another shape — parse it into `RoadmapItem`s (human confirms/edits), write to the chosen host; cross-host is fine; join items to discovered features so shipped/in-progress work back-links its `feature_slug` instead of re-listing as "planned"; leave the source in place as `migrated_from` (never delete). **Create** (seed from the Step 8 triage) if nothing is found — for `local`, `dae_roadmap.py init` then `upsert` the seeds.
6. **Bootstrap layout** — create `features/`, empty `.engineer/discussions.log`; ensure `.build/` is gitignored.
7. **Discover features** — walk the repo (read-only) for every feature-shaped chunk, **documented and undocumented**:
   - *Documented* — Speckit `specs/NNN-slug/`, feature branches, `docs/specs/*.md`, GitHub Issues used as specs, informal README specs.
   - *Undocumented* — feature-shaped code with no spec at all: scan the packages/modules for coherent capabilities (a route group, a service, a UI surface) that no document covers.
   For each, record: source (or "code-only"), slug, state (spec-only / in-progress / shipped / merged), **code co-locations** (which packages/dirs the code lives in), and current DAE coverage (which of `feature.md` / `acs.md` / `spec.md` / acceptance tests exist — usually none). Greenfield project → discovery is empty; skip to Step 11.
8. **Triage** — with the human, rank the discovered features by importance to the project, and assign each a status (`done` shipped / `in-progress` / `ready` spec-only / `parked` dormant). Triage order drives the consolidation backlog's priority and which features get formalized first. Importance is a human judgement — surface a proposed ranking, let the human reorder.
9. **Write the consolidation backlog + seed the tracker** — two views of the triaged inventory:
   - `.engineer/consolidation.md`: the inventory as a **coverage table** (one row per feature, a column per coverage artifact) plus consolidation tasks in triage-priority order. Goal stated at the top: every row all-✅. Each task — "bring feature X to full ATDD coverage" — is bounded and **dispatchable to a remote agent**; note the suggested execution mode per task.
   - **Seed the tracker** — upsert a `TrackedFeature` row for *every* discovered feature (driver per `references/tracker.md`), not just the formalized ones, so the tracker shows the whole consolidation effort at a glance from day one. `status` from triage; `checkpoint` blank for features not yet in the DAE pipeline (`consolidation.md` tracks their coverage until they enter it).
10. **Formalize the starting features** — with the human, pick the 1–2 highest-triage features and run `feature-init` (onboarding-intake mode) on each now, so the project leaves onboarding with momentum. The rest stay as backlog tasks — do NOT formalize all of them in one onboard run.
11. **Handoff** — emit a summary; `recommended_next` points at the top consolidation-backlog task.

**Migration is not done inside `onboard`.** Moving `specs/NNN-slug/` → `features/NNN-slug/`, backfilling `acs.md`/`spec.md`, and generating acceptance tests are *consolidation tasks* — worked down feature by feature after onboarding, via the pipeline (`feature-init` → `discover-acs` reverse-engineer mode → `atdd:atdd` → pipeline generation), and dispatchable to remote agents. `onboard` only discovers, triages, and plans.

## Gap-check mode

Manifest exists → don't re-onboard. Validate: `CHARTER.md` has all 7 sections; `manifest.yml` schema-valid; `features/` numbering monotonic; tracker config resolves; **roadmap config resolves and its host is still reachable** (MCP/CLI/API present; if it went unreachable, flag it — `next` will be running blind to the roadmap); charter roles == `manifest.team.default_roles`. If a *new* external roadmap source has appeared since onboarding (e.g. a `ROADMAP.md` was added), surface it as a re-migration offer rather than acting. Report gaps with suggested fixes (mirrors `consistency-check --project`).

**Strictly read-only. Forbidden:**
- `git checkout`, `git pull`, `git fetch`, `git merge`, `git rebase`, `git branch -d/-D` — no git state mutations of any kind.
- `git stash` — even apparently-safe stashing changes working-tree state.
- Writing, editing, or deleting any file outside `/tmp` (no charter edits, no `.engineer/` writes, no feature-folder touches).

If gap-check would benefit from a sync (e.g. the user is on a feature branch with merged remote), surface the suggestion in the report and stop. The caller invokes `/engineer.post-merge` or the manual git commands themselves. **Do not infer "the user wants a sync" from "the user typed /engineer.onboard".**

## Full-onboard precondition

Full-onboard mutates the repo: writes `CHARTER.md`, `.engineer/`, `features/`. It must start from a clean state:

- HEAD on `main`/`master` (or the repo's default branch — read from `git symbolic-ref refs/remotes/origin/HEAD`).
- Clean working tree (`git status --porcelain` empty).
- Either: no current branch is a feature branch with unpushed work, **or** the user explicitly confirms "onboard on this branch".

If those conditions don't hold, stop and surface the situation — never auto-checkout, never auto-stash. Suggested wording: "Onboarding writes new files into the repo root. You're on `<branch>` with `<N>` unpushed commits — confirm you want to onboard here, or switch to main yourself first."

## Handoff

Emit per `${CLAUDE_PLUGIN_ROOT}/references/handoff-summary.md`. onboard is project-scope — its handoff goes to `.engineer/handoffs/` (no feature folder exists). `checkpoint: 0`; `artifacts`: `CHARTER.md`, `.engineer/manifest.yml`. `recommended_next`: "per feature, /engineer.prime-context then /engineer.discover-acs; new ideas, /engineer.discuss".

If onboarding stopped because the human wasn't available to sign off the charter or choose the tracker, emit `status: interrupted` with `human_action_needed: decision` — naming exactly which decisions are outstanding.

## References

- [Foundation Design](https://www.notion.so/3585ecdee0e2811bbc67ff4913c03207) — charter format (§3), manifest schema (§2), storage layout (§1)
- [Discuss & Upstream Funnel](https://www.notion.so/35a5ecdee0e281eaa35fced0c4e23384) — methodology_root, onboarding intake
- `references/tracker.md` — the tracker drivers, setup, the Notion mapping
- `references/roadmap.md` — the roadmap drivers, the reachability precondition, link/migrate/create
- [Tracker Integration](https://www.notion.so/35a5ecdee0e28168b1aee324c267fd13) — the full contract
- `engineer/scripts/dae_infra.py` — what the manifest infra entries feed
