# Host capabilities — what DAE needs, versus what this host calls it

DAE is a **methodology**, not a Claude Code plugin that happens to describe one.
The pipeline, the checkpoints, the handoff-as-gate contract, and the artifact
ontology are host-independent. What varies between hosts is the *mechanism* each
capability is reached through.

This file is the seam. It names the capabilities the methodology depends on, and
binds each to whatever the current host provides. **Porting DAE to another agent
runtime is editing the binding column of one table** — not rewriting nineteen
skills.

## The rule

Elsewhere in this kit, skills name host mechanisms directly ("dispatch via the
Agent tool", "the TodoWrite panel"). Read those as **the current binding of a
capability, not the contract**. The contract is the capability column below. A
skill that says "Agent tool" means *dispatch a fresh agent with this brief*; if
your host spells that differently, spell it differently and the methodology is
unchanged.

The same discipline as `${CLAUDE_PLUGIN_ROOT}/references/model-classes.md`: name
the class, resolve the product at the point of use.

## Required capabilities

Without these, the pipeline cannot run as designed.

| Capability | What DAE needs it for | Current binding | If absent |
|---|---|---|---|
| **dispatch** | Run a fresh agent against a self-contained brief. The structural basis of Principle 7 (verifier ≠ implementer) and of every checkpoint handoff. | the Agent tool | The human opens a new session per checkpoint and pastes the brief. Slower, same discipline. |
| **filesystem** | Read and write `features/NNN-slug/*`, `.engineer/`, and run the `dae_*` scripts. Artifacts *are* the methodology's state. | Read/Write/Edit/Bash | Hard requirement — no substitute. |
| **script execution** | Run the stdlib-only Python validators (`dae_resolve`, `dae_handoff`, `dae_ontology`, …). Deliberately plain Python 3 with no dependencies so any host with a shell can run them. | Bash | Hard requirement. |

## Optional capabilities — use when present, degrade when not

Every one of these is an *enhancement*. A skill that depends on one without a
fallback is a bug.

| Capability | What DAE uses it for | Current binding | Degrades to |
|---|---|---|---|
| **role agents** | Recurring DAE roles with enforced tool limits and turn caps, so "don't edit" and "one-shot" are properties of the agent, not wishes in a prompt. | the plugin's `agents/` (`engineer:reviewer`, `engineer:panel-adviser`, `engineer:panel-advocate`, `engineer:gauntlet-critic`, `engineer:formal-verifier`, `engineer:verifier`), dispatched as the Agent tool's `subagent_type` | A general-purpose agent whose brief pastes the role body from `agents/<name>.md`. The same discipline, but enforced by prose only. |
| **progress-surface** | The live in-skill step tracker (Indicator 2) | TodoWrite | Print the step list once at the start, and say which step you're on as you go. |
| **structured-ask** | Batched multiple-choice questions — the AC coverage checklists, autonomy prompts | AskUserQuestion | Ask in prose, one batched message. |
| **orchestrate** | Large-N or quality-pattern fan-out (parallelism Tier 3) | the Workflow tool | Tier 2 parallel agents, then Tier 1 sequential. Already specified in `parallelism.md`. |
| **isolate** | Give a file-editing agent its own working copy so parallel agents don't clobber | `isolation: "worktree"` | Serialize the edits. |
| **remote** | Run a checkpoint off-machine, opening a PR | `isolation: "remote"` / cloud routines | Local subagent. Already specified in `handoff-dispatch.md`. |
| **peer-message** | A dispatched agent reporting back mid-run to a named parent | SendMessage | The agent's final text as its return value — which is why the reporting contract names the channel explicitly. |
| **tool-channel** | Reaching trackers, roadmaps, issue systems | MCP servers | The driver-preflight fallback: a CLI, an API, or `type: none`. Already specified in `tracker.md` / `roadmap.md`. |
| **render** | Publishing a rendered, shareable view — see below | Artifacts | Terminal text. Always the default. |

## Role agents — plugin default, project override

The plugin ships one agent per recurring role. They're project-agnostic: each
carries the posture, its tool limits and its output shape. Project specifics
(charter, stack, run commands, read set) still travel in the brief, so the
agent definitions stay generic.

- **Model.** Every role agent says `model: inherit`. Pass the class-resolved
  `model` on each dispatch (`model-classes.md`); a per-dispatch model beats the
  frontmatter. Never pin a product name in an agent file.
- **Overriding.** Plugin agents have the lowest precedence. A project that needs
  a different posture (extra tools, a stricter reviewer) copies
  `agents/<name>.md` into its own `.claude/agents/`, keeps the `name`, and
  edits it. When dispatching a role, use the project's `<name>` if
  `.claude/agents/<name>.md` exists, else `engineer:<name>`. `onboard` does not
  scaffold overrides; add one only when the charter asks for it.
- **Limits.** Plugin agents ignore `hooks`, `mcpServers` and `permissionMode`.
  A role that needs any of those must be a project override.

## `render` — the one worth reaching for

Some DAE output is genuinely a *view*, not a message: it is scanned, returned
to, and shared, and it loses most of its value squeezed into terminal text. Where
the host can publish a rendered document, these four are worth it:

| What | Why rendered beats terminal |
|---|---|
| **Feature + roadmap position** | The recurring "is this done, what's next, where does this sit?" is a question about a *structure* — checkpoints across features, features against roadmap horizons. One glanceable view answers it; four lines of breadcrumb answer it one feature at a time. |
| **`next` project survey** | Eight buckets of in-flight work is a dashboard wearing a list's clothing. |
| **Panel findings** | A findings table with severity, location, and disposition is read like a review queue, not a paragraph. |
| **Ontology / consistency report** | Cross-feature constraint violations are inherently tabular. |

Rules, so this stays an enhancement:

1. **Terminal text is always emitted.** The rendered view is *additional*. A
   skill must never answer only through a channel the human might not open.
2. **Never render as a gate.** No checkpoint blocks on a view being published.
3. **Content comes from the same source** the terminal output uses — the
   `dae_*` scripts' JSON. Do not compute a second, divergent version of the
   truth for the pretty one.
4. **Ask once per session** at autonomy `low`; at `medium`/`high` publish and
   mention it in one line.
5. **Nothing sensitive.** These views carry feature names, checkpoint states, and
   file paths. That is fine for a private view; it is not fine for anything a
   host publishes to a shared or public URL by default. Check the host's default
   visibility before enabling it on a client project.

## Porting checklist

To move DAE to another agent runtime:

1. Rebind the two tables above. Everything in the **Required** table must exist;
   everything in **Optional** may be dropped to its degradation.
2. Replace the plugin-root variable (`${CLAUDE_PLUGIN_ROOT}`, 150+ uses) with the
   host's equivalent — it is a path prefix, not a semantic dependency.
3. Rewrite `examples/*.md` — those are host hook configs by definition.
4. Leave everything else. The skills, the checkpoint contract, the artifact
   schemas, and the `dae_*` scripts are host-independent by construction; the
   scripts are stdlib-only Python 3 precisely so this stays true.

MCP is not a portability problem — it is an open protocol with implementations
beyond this host.

## References

- `${CLAUDE_PLUGIN_ROOT}/references/model-classes.md` — the same name-the-class discipline, applied to models
- `${CLAUDE_PLUGIN_ROOT}/references/parallelism.md` — the 3→2→1 degradation this generalizes
- `${CLAUDE_PLUGIN_ROOT}/references/driver-preflight.md` — probe-before-write, the tool-channel analogue
