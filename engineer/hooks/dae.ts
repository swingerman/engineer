// Pure DAE rules the hooks module applies. Each deny names the rule and the
// doc it comes from: the guards enforce what the docs say, nothing new.
// Artifact state (CP, segment, latest handoff) is not parsed here: it comes
// from `dae_progress.py --json`, which owns those formats.
import type { EngineerAgent } from '../types'

const escape = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

/** Path matchers for a project's `features_root` (manifest; `features/` by default). */
export function featureScope(root = 'features') {
  const base = `(?:^|/)${escape(root.replace(/\/+$/, ''))}`
  const dir = new RegExp(`^(.*?${base}/\\d{3}-[^/]+)/`)
  const slug = new RegExp(`(?:^|[^\\w-])${escape(root.replace(/\/+$/, ''))}/(\\d{3}-[\\w.-]+)`)
  const featureOf = (path: string): string | undefined => dir.exec(path)?.[1]
  return {
    featureOf,
    /** The feature folder of a handoff file, if the path is one. */
    handoffFeature: (path: string): string | undefined =>
      /\/handoffs\/[^/]+\.md$/.test(path) && !/(^|\/)\.\.?(\/|$)/.test(path) ? featureOf(path) : undefined,
    /** The feature slug a brief names, if any. */
    briefFeature: (prompt: string): string | undefined => slug.exec(prompt)?.[1],
  }
}

export const slugOf = (featureDir: string): string => featureDir.slice(featureDir.lastIndexOf('/') + 1)

// --- dispatch guards (agent.spawn) -----------------------------------------

// A brief declares itself a loop through the coordinator's node contract
// (`Loop cap: max_rounds <N>`, `shape: loop|feedback`) or the loop patterns the
// pipeline names (loop-until, the CP5 green loop, kill-mutants).
const LOOP = /\b(loop-until|green loop|kill[- ]mutants|shape:\s*(?:loop|feedback)|max_rounds)\b/i
const CAP = /\bmax_rounds\b\s*[:=]?\s*\d+/i

export function dispatchDeny(prompt: string, model: string | undefined, frontier: RegExp): string | undefined {
  if (!LOOP.test(prompt)) return undefined
  if (model !== undefined && frontier.test(model)) {
    return `DAE: frontier-class model "${model}" on a looping dispatch. ` +
      'model-classes.md: "Never put `frontier` in an agentic harness." Use `inherit` (omit model) or `economy`.'
  }
  if (!CAP.test(prompt)) {
    return 'DAE: loop dispatch with no cap. A loop declares `max_rounds: <N>` and a no-progress stop ' +
      '(gauntlet.md: "default 5, never unbounded"; coordinator.md "Loop caps"). Add it to the brief.'
  }
  return undefined
}

export const modelClass = (model: string | undefined, frontier: RegExp): EngineerAgent['modelClass'] =>
  model === undefined || model === 'inherit' ? 'inherit' : frontier.test(model) ? 'frontier' : 'economy'

/** The checkpoint and shape a DAE brief states (handoff-dispatch.md's template). */
export const parseBrief = (prompt: string): { cp?: string; shape: string } => ({
  cp: /\b(?:Checkpoint\s+|CP\s?)(\d+(?:\.5)?)\b/i.exec(prompt)?.[1],
  shape: /\bshape:\s*([\w-]+)/i.exec(prompt)?.[1]?.toLowerCase() ?? (LOOP.test(prompt) ? 'loop' : 'single'),
})

/** A dispatch the coordinator view tracks: a DAE role, or a brief about a feature. */
export const isDae = (type: string, prompt: string, feature: string | undefined): boolean =>
  /^(engineer|atdd):/.test(type) || feature !== undefined || /\bcoordinated: true\b/.test(prompt)

export const isVerifier = (type: string): boolean => /(^|:)verifier$/.test(type)

// --- external-write gate (handoff-dispatch.md) -------------------------------

// gh pr merge flags that take no value; anything else may name another PR.
const MERGE_FLAGS = /^(--auto|--squash|--merge|--rebase|--delete-branch|--admin|-[dsmr])$/

/**
 * The PR merges in a shell command, the one external write the hook asks about:
 * `PR merge (current branch)` is the only kind the verify:auto carve-out may waive;
 * one with any other argument (a PR number, `$N`) always asks.
 * ponytail: a net over shell text, not a wall (an alias or `$GH pr merge` slips by);
 * pushes to main and force-pushes are left to server-side branch protection.
 */
export const prMerges = (command: string): string[] =>
  command.split(/&&|\|\||;|\||\n/).flatMap(part => {
    const m = /\bgh\s+pr\s+merge\b(.*)$/.exec(part)
    if (!m) return []
    const isCurrent = m[1].trim().split(/\s+/).filter(Boolean).every(a => MERGE_FLAGS.test(a))
    return [`PR merge${isCurrent ? ' (current branch)' : ''}`]
  })

export const EXTERNAL_RULE =
  'handoff-dispatch.md, "External-write gate": pushing to main/master, force-pushing, and creating or ' +
  'merging a PR need explicit human authorization every time, regardless of autonomy.'

export const VERIFIER_RULE =
  'agents/verifier.md: the verifier must not modify code, tests or specs; the only file it writes is ' +
  'the CP7 handoff (charter §6, Principle 7: verifier ≠ implementer).'

export const kTok = (n: number): string => (n >= 1000 ? `${Math.round(n / 1000)}k` : `${n}`)
