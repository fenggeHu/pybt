<template>
  <div class="page">
    <el-card shadow="never" class="header-card">
      <div class="header-row">
        <div>
          <h2>数据管理</h2>
          <p>上传或查看可用的 OHLCV 数据集。</p>
        </div>
        <el-upload action="" :auto-upload="false" :show-file-list="false" @change="onUpload">
          <el-button type="primary" :loading="uploading">上传 CSV</el-button>
        </el-upload>
      </div>
    </el-card>

    <el-card shadow="hover">
      <el-table :data="datasets" v-loading="datasetStore.loading" empty-text="暂未加载数据">
        <el-table-column prop="name" label="名称" width="180" />
        <el-table-column prop="symbols" label="标的" :formatter="(row) => row.symbols?.join(', ')" />
        <el-table-column prop="start" label="起始" width="120" />
        <el-table-column prop="end" label="结束" width="120" />
        <el-table-column prop="rows" label="行数" width="100" />
        <el-table-column label="操作" width="120">
          <template #default="{ row }">
            <el-popconfirm title="确认删除该数据集？" @confirm="() => remove(row.id)">
              <template #reference>
                <el-button link type="danger">删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useDatasetStore } from '@/store/useDatasetStore'
import type { UploadFile } from 'element-plus'

const datasetStore = useDatasetStore()
const uploading = ref(false)

const datasets = datasetStore.datasets

onMounted(() => {
  datasetStore.fetchDatasets().catch(() => undefined)
})

const onUpload = async (file: UploadFile) => {
  if (!file.raw) return
  uploading.value = true
  try {
    await datasetStore.createDataset(file.raw)
  } finally {
    uploading.value = false
  }
}

const remove = async (id: string) => {
  await datasetStore.removeDataset(id)
}
</script>

<style scoped lang="scss">
.page {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

h2 {
  margin: 0 0 4px;
}

p {
  margin: 0;
  color: #808080;
}
</style>
