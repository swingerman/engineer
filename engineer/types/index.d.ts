/** A feature in scope: its folder plus `dae_progress.py --json` for it. */
export type EngineerFeature = {
  dir: string
  slug: string
  breadcrumb: string
  cp: number | null
  met: number | null
  total: number | null
  segment: string | null
  autonomy_level: string | null
  last_handoff: string | null
  human_action_needed: boolean
}

export type EngineerAgent = {
  id: string
  role: string
  cp?: string
  feature?: string
  modelClass: 'economy' | 'inherit' | 'frontier'
  shape: string
  startedAt: number
  endedAt?: number
  tokens: number
  status: 'running' | 'done' | 'failed'
}

declare module 'claude-code' {
  interface PluginState {
    engineer: {
      feature: EngineerFeature | null
      agents: EngineerAgent[]
    }
  }
}
