import { expect, mock, test } from 'claude-code/testing'

const said = (r: unknown) => JSON.stringify(r)

// What `dae_progress.py <dir> --json` prints for a feature at CP5.
const STATE = JSON.stringify({
  breadcrumb: 'DAE ▸ 012-x\n▶5 Implement', cp: 5, met: 3, total: 4, segment: 'middle',
  autonomy_level: 'medium', last_handoff: 'features/012-x/handoffs/05-implement.md', human_action_needed: false,
})

// --- 2. hard guards: one deny each -------------------------------------------

test('force-push is denied without an explicit OK', async $ => {
  const r = await $.tool.call({ tool: 'Bash', command: 'git push --force origin feat' })
  expect(said(r)).toContain('External-write gate')
})

test('push to main is denied without an explicit OK', async $ => {
  const r = await $.tool.call({ tool: 'Bash', command: 'git push origin main' })
  expect(said(r)).toContain('push to main/master')
})

test('PR create is denied without an explicit OK (no verify:auto carve-out in scope)', async $ => {
  const r = await $.tool.call({ tool: 'Bash', command: 'gh pr create --fill' })
  expect(said(r)).toContain('PR create')
})

test('push bypass spellings still hit the gate', async $ => {
  for (const command of [
    'git push origin HEAD:refs/heads/main',
    "git push origin 'main'",
    'git push origin $(echo main)',
    'git push --repo=origin main',
    'git push origin $BRANCH',
  ]) {
    const r = await $.tool.call({ tool: 'Bash', command })
    expect(said(r), command).toContain('External-write gate')
  }
})

test('an ordinary feature-branch push passes', async ($, on) => {
  on('tool.call', { tool: 'Bash' }, () => ({ result: { stdout: 'ok', stderr: '', interrupted: false } }))
  const r = await $.tool.call({ tool: 'Bash', command: 'git push -u origin feat' })
  expect(said(r)).not.toContain('External-write gate')
})

test('frontier-class model on a loop dispatch is denied', async $ => {
  const r = await $.agent.spawn({ prompt: 'Run the CP5 green loop. max_rounds: 6', model: 'fable' } as never)
  expect(r.deny).toContain('model-classes.md')
})

test('a loop dispatch with no cap is denied', async $ => {
  const r = await $.agent.spawn({ prompt: 'Kill mutants loop-until the score holds.' } as never)
  expect(r.deny).toContain('no cap')
})

test('the verifier role editing code is denied', async ($, on) => {
  mock.clock(on)
  on('agent.spawn', () => ({ model: 'sonnet', agentId: 'v1' }))
  await $.agent.spawn({ subagentType: 'engineer:verifier', prompt: 'CP7 for features/012-x' } as never)
  const r = await $.tool.call({ tool: 'Write', file_path: 'src/app.ts', content: 'x', agentId: 'v1' } as never)
  expect(said(r)).toContain('verifier may not edit')
})

test('the verifier cannot escape handoffs/ with dot segments', async ($, on) => {
  mock.clock(on)
  on('agent.spawn', () => ({ model: 'sonnet', agentId: 'v2' }))
  await $.agent.spawn({ subagentType: 'engineer:verifier', prompt: 'CP7 for features/012-x' } as never)
  const path = 'features/012-x/../../src/handoffs/x.md'
  const r = await $.tool.call({ tool: 'Write', file_path: path, content: 'x', agentId: 'v2' } as never)
  expect(said(r)).toContain('verifier may not edit')
})

// --- 1/3/6. handoff write → validate, sync, band; agent end → ledger ------------

test('a handoff write validates, syncs, draws the band and feeds the ledger', async ($, on) => {
  mock.clock(on)
  mock.store(on)
  const spawned: string[] = []
  on('process.run', ($, e) => ({ value: {
    exitCode: 0,
    stdout: e.argv.includes('--json') ? STATE : 'ok',
    stderr: '', isStdoutTruncated: false, isStderrTruncated: false,
  } }))
  on('ui.status', () => ({ value: undefined }))
  on('ui.toast', () => ({ value: undefined }))
  on('audio.play', () => ({ value: undefined }))
  on('turn.complete', () => ({ text: '' }))
  on('agent.spawn', ($, e) => (spawned.push(e.description), { model: 'sonnet', agentId: 's1' }))
  on('tool.call', { tool: 'Write' }, () => ({ result: { type: 'create', filePath: 'x', content: 'x', structuredPatch: [] } }))

  await $.tool.call({ tool: 'Write', file_path: '/p/features/012-x/handoffs/cp5.md', content: '---\n---' } as never)
  expect(spawned[0]).toContain('DAE progress sync: 012-x')

  for (const surface of ['terminal', 'desktop'] as const) {
    const ui = await $.ui.mount({
      plugin: 'engineer', surface, component: 'AbovePrompt',
      props: {
        hasSurvey: false, isWorking: false, maxRows: 10, bodyColumns: 80,
        scroll: { offset: 0, bodyRows: 10 }, view: {},
      } as never,
    })
    expect(JSON.stringify(await ui.findAll({ type: 'Text' }))).toContain('DAE ▸ 012-x')
    await ui.unmount()
  }

  await $.turn.complete({
    answer: 'synced', durationMs: 60000, isAborted: false, turnId: 't', agentId: 's1', reason: 'answer',
    usage: { input_tokens: 1000, output_tokens: 500, cache_creation_input_tokens: 0, cache_read_input_tokens: 0, model: 'sonnet' },
  } as never)
  const ledger = await $.tool.call({ tool: 'mcp__engineer__cost_ledger' } as never)
  expect(said(ledger)).toContain('progress-log')

  for (const surface of ['terminal', 'desktop'] as const) {
    const pane = await $.ui.mount({
      plugin: 'engineer', surface, component: 'Pane', requestId: 'dae',
      props: {
        title: 'DAE', isFocused: false, bodyColumns: 60, placement: 'dock',
        scroll: { offset: 0, bodyRows: 10 }, view: {},
      } as never,
    })
    const drawn = JSON.stringify(await pane.findAll({ type: 'Text' }))
    expect(drawn).toContain('progress-log')
    expect(drawn).toContain('economy')
    await pane.unmount()
  }
})

// --- 7. role re-anchor after compaction ------------------------------------------

test('a compacted DAE agent gets its role, checkpoint and handoff back', async ($, on) => {
  mock.clock(on)
  const session = mock.session(on)
  on('process.run', () => ({ value: { exitCode: 0, stdout: STATE, stderr: '', isStdoutTruncated: false, isStderrTruncated: false } }))
  on('agent.spawn', () => ({ model: 'sonnet', agentId: 'b1' }))
  const kept = [{ role: 'user' as const, text: 'summary', toolUses: [] }]
  on('session.compact', () => ({ messages: kept }))
  await $.agent.spawn({ subagentType: 'atdd:atdd-team', prompt: 'Checkpoint 5 for features/012-x' } as never)
  await $.session.compact({ trigger: 'auto', agentId: 'b1', messages: kept } as never)
  const text = said(session.appended())
  expect(text).toContain('Role: atdd:atdd-team')
  expect(text).toContain('CP5')
  expect(text).toContain('Autonomy: medium')
  expect(text).toContain('features/012-x/handoffs/05-implement.md')
})
