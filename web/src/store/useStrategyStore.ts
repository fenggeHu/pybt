import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { StrategyConfig } from '@/types'
import { listStrategies, saveStrategy } from '@/services/api'

export const useStrategyStore = defineStore('strategy', () => {
  const strategies = ref<StrategyConfig[]>([])
  const loading = ref(false)

  const fetchStrategies = async () => {
    loading.value = true
    try {
      strategies.value = await listStrategies()
    } finally {
      loading.value = false
    }
  }

  const upsertStrategy = async (payload: Partial<StrategyConfig>) => {
    const data = await saveStrategy(payload)
    const idx = strategies.value.findIndex((s) => s.id === data.id)
    if (idx >= 0) {
      strategies.value[idx] = data
    } else {
      strategies.value.push(data)
    }
  }

  return { strategies, loading, fetchStrategies, upsertStrategy }
})
