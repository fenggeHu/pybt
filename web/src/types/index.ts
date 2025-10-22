export interface Dataset {
  id: string
  name: string
  path: string
  symbols: string[]
  rows: number
  start: string
  end: string
}

export interface StrategyConfig {
  id: string
  name: string
  type: 'sma' | 'breakout' | 'weighted'
  params: Record<string, unknown>
  updatedAt: string
}

export interface BacktestRequest {
  datasetId: string
  strategyIds: string[]
  cash: number
  slipBps: number
  commission: number
  commissionRate: number
  volumeLimit: number
  risk: {
    maxUnits: number
    stopLossPct: number
  }
  allocator?: {
    maxLeverage: number
    lotSize: number
    rounding: 'round' | 'floor' | 'ceil'
  }
  notes?: string
}

export type BacktestStatus = 'queued' | 'running' | 'success' | 'failed'

export interface BacktestSummary {
  id: string
  name: string
  status: BacktestStatus
  startedAt: string
  finishedAt?: string
  totalReturn?: number
  sharpe?: number
  maxDrawdown?: number
}

export interface BacktestResult {
  summary: BacktestSummary
  metrics: Record<string, number>
  equity: Array<{ dt: string; equity: number }>
  trades: Array<{
    symbol: string
    side: string
    qty: number
    entry_dt: string
    exit_dt: string
    pnl: number
    tag?: string
  }>
  logs: string[]
}
