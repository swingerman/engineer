// engineer mods: Claude Code function hooks that enhance the DAE pipeline.
// Every one is optional (references/host-capabilities.md): on a host without
// function hooks the skills run unchanged and the coordinator dispatches the
// progress sync itself.
import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import type { EngineerAgent, EngineerFeature } from '../types'
import {
  dispatchDeny, EXTERNAL_RULE, externalWrites, featureScope, isDae, isVerifier, kTok, modelClass,
  parseBrief, slugOf, VERIFIER_RULE,
} from './dae'

type $ = EngineInterface

const feature = atom({ plugin: 'engineer', key: 'feature' } as const, null)
const agents = atom({ plugin: 'engineer', key: 'agents' } as const, [])

const PANE = 'dae'
const SYNC = 'DAE progress sync'
const ICON = { running: '▶', done: '✓', failed: '✗' } as const

type LedgerRow = { role: string; modelClass: string; shape: string; runs: number; tokens: number; ms: number }

// Set at load from the plugin's options (defaults live in plugin.json) and the
// project's manifest. Classes, not products (model-classes.md).
let economy = ''
let frontier = /$^/
let root = 'features'
let scope = featureScope()

// Per-process state; a reload forgets it and at worst runs one sync twice.
const syncs = new Map<string, { agentId?: string; isPending: boolean }>() // feature dir → its running sync
let shownDir: string | undefined
let ticker: { cancel: () => void } | undefined

function py($: $, script: string, ...args: string[]) {
  return $.process.run(['python3', `${$.plugin.root}/scripts/${script}`, ...args], { timeoutMs: 60_000 })
}

function alert($: $, text: string) {
  $.ui.toast(text, { timeoutMs: 8000 })
  void $.audio.play({ asset: 'hooks/gate.wav' }).catch(() => undefined)
}

/** `dae_progress.py --json`: the one source for crumb, CP, segment, latest handoff. */
async function loadFeature($: $, dir: string): Promise<EngineerFeature | null> {
  return py($, 'dae_progress.py', dir, '--json')
    .then(r => ({ dir, slug: slugOf(dir), ...JSON.parse(r.stdout) }) as EngineerFeature)
    .catch(() => null)
}

function drawStatus($: $, f: EngineerFeature | null, rows: readonly EngineerAgent[]) {
  if (f === null) return $.ui.status(undefined)
  const running = rows.filter(a => a.status === 'running').length
  $.ui.status([
    f.cp !== null ? `CP${f.cp} ▸ ${f.met}/${f.total}` : f.slug,
    `${running} agent${running === 1 ? '' : 's'}`,
    `${kTok(rows.reduce((n, a) => n + a.tokens, 0))} tok`,
  ].join(' · '))
}

async function updateStatus($: $) {
  const [f, rows] = await Promise.all([read($, feature), read($, agents)])
  drawStatus($, f, rows)
}

async function show($: $, f: EngineerFeature | null) {
  if (f === null) return
  shownDir = f.dir
  await update($, feature, () => f)
  await updateStatus($)
}

async function startSync($: $, dir: string, handoff: string): Promise<string> {
  const running = syncs.get(dir)
  if (running !== undefined) {
    running.isPending = true
    return 'a progress sync is already running for this feature and re-runs when it ends'
  }
  const slug = slugOf(dir)
  syncs.set(dir, { isPending: false })
  const spawned = await $.agent.spawn({
    description: `${SYNC}: ${slug}`,
    model: economy,
    prompt:
      `Run the engineer:progress-log skill (Skill tool, skill "engineer:progress-log", args "${slug}") ` +
      `for the DAE feature at ${dir}. A handoff was just written: ${handoff}. Project it into ` +
      'progress.md and the tracker exactly as the skill says; edit nothing else. ' +
      'Your final text is the return value: one line saying what changed, or that the sync failed and why.',
  })
  if (spawned.deny !== undefined || spawned.agentId === undefined) {
    syncs.delete(dir)
    return `the progress sync could not start (${spawned.deny ?? 'no agent'}): dispatch an economy /engineer.progress-log ${slug} yourself`
  }
  syncs.set(dir, { agentId: spawned.agentId, isPending: false })
  return `progress sync dispatched (agent ${spawned.agentId}); do not dispatch /engineer.progress-log yourself for this handoff`
}

async function onHandoff($: $, dir: string, path: string): Promise<string> {
  const [check, f] = await Promise.all([
    py($, 'dae_handoff.py', dir).catch(err => ({ exitCode: 1, stdout: String(err) })),
    loadFeature($, dir),
  ])
  const verdict = check.stdout.trim().split('\n')[0] ?? ''
  if (check.exitCode !== 0) alert($, `DAE ${slugOf(dir)}: handoff check failed: ${verdict}`)
  if (f?.human_action_needed) alert($, `DAE ${f.slug}: a gate needs you (human_action_needed: yes)`)
  await show($, f)
  const sync = await startSync($, dir, path)
  return `engineer mod: dae_handoff.py ${check.exitCode === 0 ? 'passed' : `FAILED: ${verdict}`}; ${sync}.`
}

/** The carve-out holds only for the feature's own PR: we are on its branch and its bar is green. */
async function mergeReady($: $): Promise<boolean> {
  const f = await read($, feature)
  if (f === null) return false
  // fail-closed: a branch mismatch, or anything but a parsed `ready: true`, keeps the gate
  const [onBranch, ready] = await Promise.all([
    py($, 'dae_branch.py', f.dir).then(r => r.exitCode === 0, () => false),
    py($, 'dae_mergeready.py', f.dir, '--json').then(r => JSON.parse(r.stdout).ready === true).catch(() => false),
  ])
  return onBranch && ready
}

async function getLedger($: $): Promise<Record<string, LedgerRow>> {
  return ((await $.store.get('ledger')) ?? {}) as Record<string, LedgerRow>
}

async function addToLedger($: $, row: EngineerAgent, tokens: number, ms: number) {
  const ledger = await getLedger($)
  const { role, modelClass, shape } = row
  const key = `${role}|${modelClass}|${shape}`
  const was = ledger[key] ?? { role, modelClass, shape, runs: 0, tokens: 0, ms: 0 }
  // ponytail: read-modify-write, two agents ending in the same tick can lose one row's add
  ledger[key] = { ...was, runs: was.runs + 1, tokens: was.tokens + tokens, ms: was.ms + ms }
  await $.store.set('ledger', ledger)
}

async function anchorFor($: $, agentId: string | undefined): Promise<string | undefined> {
  const [rows, f] = await Promise.all([read($, agents), read($, feature)])
  const row = rows.find(a => a.id === agentId)
  if (agentId !== undefined && row === undefined) return undefined
  const target = row?.feature !== undefined && row.feature !== f?.slug ? await loadFeature($, `${root}/${row.feature}`) : f
  if (target === null) return undefined
  const cp = row?.cp ?? target.cp
  return [
    '[engineer re-anchor after compaction]',
    `Role: ${row?.role ?? 'main session'} · Checkpoint: ${cp !== null ? `CP${cp}` : 'unknown'} · Autonomy: ${target.autonomy_level ?? 'unset'}`,
    `Feature: ${target.dir}`,
    `Latest handoff: ${target.last_handoff ?? 'none yet'}`,
    'Keep this role. Re-read the latest handoff before acting; if the next action is unclear, run /engineer.reorient.',
  ].join('\n')
}

export const register: Register = (on, options) => {
  economy = String(options.economyModel)
  frontier = new RegExp(String(options.frontierModels).split(/[,\s]+/).filter(Boolean).join('|') || '$^', 'i')

  // --- session --------------------------------------------------------------

  on('session.start', async ($, e, next) => {
    const [resolved] = await Promise.all([
      py($, 'dae_resolve.py', e.cwd).catch(() => undefined),
      $.command.register({ name: PANE, description: 'DAE coordinator pane: running agents, segment, cost' }),
      $.tool.register({
        name: 'cost_ledger',
        description:
          'DAE cost ledger: actual tokens and minutes per role × model class × shape, across sessions. ' +
          'Use it in place of the priors when proposing a run shape (coordinator.md "Estimates").',
      }),
    ])
    try {
      root = JSON.parse(resolved?.stdout ?? '').manifest.features_root || root
      scope = featureScope(root)
    } catch {
      // no manifest: keep the default root
    }
    return next(e)
  })

  on('command.run', { command: PANE }, async $ => {
    await $.ui.open({ id: PANE, title: 'DAE' })
    return { text: 'DAE pane opened.' }
  })

  on('tool.call', { tool: 'mcp__engineer__cost_ledger' }, async $ => {
    const rows = Object.values(await getLedger($)).map(r => ({
      ...r, avgTokens: Math.round(r.tokens / r.runs), avgMinutes: +(r.ms / r.runs / 60000).toFixed(1),
    }))
    return { result: rows.length ? JSON.stringify(rows, null, 1) : 'No runs recorded yet: use the priors.' }
  })

  // --- 1. handoff-write hook: validate, then sync deterministically ----------

  on('tool.call', { tool: ['Write', 'Edit'] }, async ($, e, next) => {
    const ran = await next(e)
    const dir = scope.handoffFeature(e.file_path)
    if (dir === undefined || ran.deny !== undefined || ran.isError) return ran
    const note = await onHandoff($, dir, e.file_path)
    return { ...ran, context: [...(ran.context ?? []), note] } as typeof ran
  })

  // Feature scope: the band and status line follow the feature last touched.
  on('tool.call', { tool: ['Read', 'Write', 'Edit', 'NotebookEdit'] }, async ($, e, next) => {
    const ran = await next(e)
    const path = 'file_path' in e ? e.file_path : e.notebook_path
    const dir = scope.featureOf(path)
    if (dir !== undefined && dir !== shownDir && scope.handoffFeature(path) === undefined) await show($, await loadFeature($, dir))
    return ran
  })

  // --- 2. hard guards ---------------------------------------------------------

  // A permission decision, so the host shows its own one-click Allow/Deny with the
  // command. A hook's ask is the person's alone: no classifier or rule settles it,
  // and where nobody can be asked it is a deny carrying this reason.
  on('tool.check', { tool: 'Bash' }, async ($, e, next) => {
    const actions = await externalWrites((e.input as { command: string }).command, () =>
      // A bare push goes to @{push}, `push <remote> HEAD` to the branch's own name: gate on either.
      Promise.all(['@{push}', 'HEAD'].map(ref =>
        $.process.run(['git', 'rev-parse', '--abbrev-ref', ref])
          .then(r => r.exitCode === 0 && /(^|\/)(main|master)$/.test(r.stdout.trim()), () => false)))
        .then(hits => hits.some(Boolean)))
    if (actions.length === 0) return next(e)
    // The one carve-out: verify:auto may open and merge its own PR when the bar is green.
    if (actions.every(a => a.endsWith('(current branch)')) && (await mergeReady($))) return next(e)
    return { decision: 'ask', reason: `DAE: ${actions.join(' + ')} needs an explicit OK. ${EXTERNAL_RULE}` }
  }).catch(() => ({ decision: 'deny', reason: `DAE: the external-write guard failed. ${EXTERNAL_RULE}` }))

  on('tool.call', { tool: ['Write', 'Edit', 'NotebookEdit'] }, async ($, e, next) => {
    if (e.agentId === undefined) return next(e)
    const row = (await read($, agents)).find(a => a.id === e.agentId)
    if (row === undefined || !isVerifier(row.role)) return next(e)
    const path = 'file_path' in e ? e.file_path : e.notebook_path
    return scope.handoffFeature(path) !== undefined ? next(e) : { deny: `DAE: the verifier may not edit ${path}. ${VERIFIER_RULE}` }
  }).catch(($, e, next) =>
    next.called || e.agentId === undefined ? next(e) : { deny: `DAE: the verifier guard failed. ${VERIFIER_RULE}` })

  on('agent.spawn', async ($, e, next) => {
    if (e.resume !== undefined) return next(e)
    const deny = dispatchDeny(e.prompt, e.model, frontier)
    if (deny !== undefined) return { deny }
    const ran = await next(e)
    // Our own sync is known by its description: its agentId only arrives after this hook.
    const isSync = (e.description ?? '').startsWith(SYNC)
    const slug = scope.briefFeature(e.prompt)
    if (ran.agentId === undefined || !(isSync || isDae(e.subagentType, e.prompt, slug))) return ran
    const row: EngineerAgent = {
      id: ran.agentId, role: isSync ? 'progress-log' : e.subagentType, feature: slug, ...parseBrief(e.prompt),
      modelClass: modelClass(e.model, frontier), startedAt: await $.clock.now(), tokens: 0, status: 'running',
    }
    await update($, agents, list => [...list.filter(a => a.id !== row.id), row])
    ticker ??= $.clock.every(5000, () => $.ui.invalidate('ui.render')) // elapsed time in the pane
    await updateStatus($)
    return ran
  }).catch(($, e, next) => (next.called ? next(e) : { deny: 'DAE: the dispatch guard failed (model-classes.md, gauntlet.md).' }))

  // --- 4/5/6. agent ends: pane, toast + sound, cost ledger ---------------------

  on('turn.complete', async ($, e, next) => {
    if (e.agentId === undefined) return next(e)
    const row = (await read($, agents)).find(a => a.id === e.agentId)
    if (row === undefined) return next(e)
    const u = e.usage
    const tokens = u ? u.input_tokens + u.output_tokens + (u.cache_creation_input_tokens ?? 0) + (u.cache_read_input_tokens ?? 0) : 0
    const isFailed = e.reason !== 'answer'
    const now = await $.clock.now()
    await Promise.all([
      update($, agents, list => list.map(a => a.id === row.id
        ? { ...a, tokens: a.tokens + tokens, status: isFailed ? 'failed' : 'done', endedAt: now } : a)),
      addToLedger($, row, tokens, e.durationMs),
    ])
    if (row.role !== 'progress-log' || isFailed) {
      alert($, `DAE: ${row.role}${row.cp ? ` (CP${row.cp})` : ''} ${isFailed ? `failed: ${e.reason}` : 'finished'}`)
    }
    if (!(await read($, agents)).some(a => a.status === 'running')) {
      ticker?.cancel()
      ticker = undefined
    }
    const dir = [...syncs].find(([, s]) => s.agentId === row.id)?.[0]
    if (dir === undefined) await updateStatus($)
    else {
      const isPending = syncs.get(dir)?.isPending === true
      syncs.delete(dir)
      await show($, await loadFeature($, dir))
      if (isPending) await startSync($, dir, 'the newest one under handoffs/')
    }
    return next(e)
  })

  on('tool.call', { tool: 'AskUserQuestion' }, async ($, e, next) => {
    if (e.agentId === undefined && shownDir !== undefined) alert($, 'DAE: a gate needs you')
    return next(e)
  })

  // --- 7. role re-anchor after compaction --------------------------------------

  on('session.compact', async ($, e, next) => {
    const done = await next(e)
    if (done.skip !== undefined || e.trigger === 'precompute') return done
    const text = await anchorFor($, e.agentId)
    if (text !== undefined) {
      await $.session.append({ message: { type: 'user', content: [{ type: 'text', text }] }, agentId: e.agentId })
    }
    return done
  })

  // --- 3. pipeline band + 5. coordinator pane -----------------------------------

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    const f = await read($, feature)
    if (e.props.hasSurvey || f === null) return next(e)
    const { Box, Text } = $.ui.resolve(e)
    return (
      <Box flexDirection="column">
        {f.breadcrumb.split('\n').map((line, i) => (
          <Text dimColor={i > 0} bold={i === 0}>{line}</Text>
        ))}
      </Box>
    )
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const { Box, Text } = $.ui.resolve(e)
    const [f, rows, now] = await Promise.all([read($, feature), read($, agents), $.clock.now()])
    const room = Math.max(1, e.props.scroll.bodyRows - 2)
    return (
      <Box flexDirection="column">
        <Text bold>{f ? `${f.slug}${f.segment ? ` · segment ${f.segment}` : ''}` : 'No DAE feature in scope'}</Text>
        {rows.length === 0 && <Text dimColor>No DAE agents dispatched this session.</Text>}
        {rows.slice(-room).map(a => (
          <Text dimColor={a.status !== 'running'} color={a.status === 'failed' ? 'red' : undefined}>
            {ICON[a.status]} {a.role}
            {a.cp ? ` CP${a.cp}` : ''} · {a.modelClass} · {Math.round(((a.endedAt ?? now) - a.startedAt) / 1000)}s · {kTok(a.tokens)} tok
          </Text>
        ))}
      </Box>
    )
  })
}
