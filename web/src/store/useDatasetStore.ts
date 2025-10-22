import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { Dataset } from '@/types'
import { deleteDataset, listDatasets, uploadDataset } from '@/services/api'

export const useDatasetStore = defineStore('dataset', () => {
  const datasets = ref<Dataset[]>([])
  const loading = ref(false)

  const fetchDatasets = async () => {
    loading.value = true
    try {
      datasets.value = await listDatasets()
    } finally {
      loading.value = false
    }
  }

  const removeDataset = async (id: string) => {
    await deleteDataset(id)
    await fetchDatasets()
  }

  const createDataset = async (file: File) => {
    const fd = new FormData()
    fd.append('file', file)
    await uploadDataset(fd)
    await fetchDatasets()
  }

  return { datasets, loading, fetchDatasets, removeDataset, createDataset }
})
