import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { BacktestRequest, BacktestResult, BacktestStatus, BacktestSummary } from '@/types'
import { fetchBacktest, launchBacktest, listBacktests } from '@/services/api'

export const useBacktestStore = defineStore('backtest', () => {
  const summaries = ref<BacktestSummary[]>([])
  const results = ref<Record<string, BacktestResult>>({})
  const loading = ref(false)
  const polling = ref<Record<string, NodeJS.Timeout>>({})

  const runningCount = computed(() => summaries.value.filter((s) => s.status === 'running' || s.status === 'queued').length)

  const refreshHistory = async () => {
    loading.value = true
    try {
      summaries.value = await listBacktests()
    } finally {
      loading.value = false
    }
  }

  const getResult = async (id: string) => {
    if (!results.value[id]) {
      const data = await fetchBacktest(id)
      results.value[id] = data
    }
    return results.value[id]
  }

  const pollBacktest = (id: string, interval = 3_000) => {
    clearTimeout(polling.value[id])
    const tick = async () => {
      const data = await fetchBacktest(id)
      results.value[id] = data
      const status: BacktestStatus = data.summary.status
      summaries.value = summaries.value.map((s) => (s.id === id ? data.summary : s))
      if (status === 'running' || status === 'queued') {
        polling.value[id] = setTimeout(tick, interval)
      }
    }
    polling.value[id] = setTimeout(tick, interval)
  }

  const runBacktest = async (payload: BacktestRequest) => {
    const { task_id } = await launchBacktest(payload)
    await refreshHistory()
    pollBacktest(task_id)
    return task_id
  }

  return {
    summaries,
    results,
    loading,
    runningCount,
    refreshHistory,
    getResult,
    runBacktest,
    pollBacktest
  }
})
