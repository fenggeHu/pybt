import axios from 'axios'
import type { BacktestRequest, BacktestResult, BacktestSummary, Dataset, StrategyConfig } from '@/types'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  timeout: 15_000
})

export const listDatasets = async (): Promise<Dataset[]> => {
  const { data } = await api.get('/datasets')
  return data
}

export const uploadDataset = async (payload: FormData) => {
  const { data } = await api.post('/datasets', payload)
  return data
}

export const deleteDataset = async (id: string) => {
  await api.delete(`/datasets/${id}`)
}

export const listStrategies = async (): Promise<StrategyConfig[]> => {
  const { data } = await api.get('/strategies')
  return data
}

export const saveStrategy = async (payload: Partial<StrategyConfig>) => {
  const { data } = await api.post('/strategies', payload)
  return data
}

export const launchBacktest = async (payload: BacktestRequest) => {
  const { data } = await api.post('/backtests', payload)
  return data as { task_id: string }
}

export const fetchBacktest = async (id: string): Promise<BacktestResult> => {
  const { data } = await api.get(`/backtests/${id}`)
  return data
}

export const listBacktests = async (): Promise<BacktestSummary[]> => {
  const { data } = await api.get('/backtests')
  return data
}

export const downloadArtifact = (id: string, type: 'metrics' | 'equity' | 'trades') => {
  return api.get(`/backtests/${id}/download`, {
    params: { type },
    responseType: 'blob'
  })
}

export default api
