<template>
  <div class="page">
    <el-card shadow="never" class="header-card">
      <div class="header-row">
        <div>
          <h2>回测历史</h2>
          <p>按时间排序浏览全部回测任务，可快速跳转查看详情或下载结果。</p>
        </div>
        <el-button text @click="reload" :loading="backtestStore.loading">刷新</el-button>
      </div>
    </el-card>

    <el-card shadow="hover">
      <el-table :data="backtestStore.summaries" v-loading="backtestStore.loading" empty-text="暂无记录" stripe>
        <el-table-column prop="name" label="名称" />
        <el-table-column prop="status" label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="statusTag(row.status)">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="startedAt" label="开始时间" width="180" />
        <el-table-column prop="finishedAt" label="结束时间" width="180" />
        <el-table-column prop="totalReturn" label="收益" width="120">
          <template #default="{ row }">{{ formatPct(row.totalReturn) }}</template>
        </el-table-column>
        <el-table-column prop="sharpe" label="Sharpe" width="100">
          <template #default="{ row }">{{ row.sharpe?.toFixed?.(2) ?? '--' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="220">
          <template #default="{ row }">
            <el-button link type="primary" @click="view(row.id)">详情</el-button>
            <el-divider direction="vertical" />
<el-dropdown @command="(cmd: string) => download(row.id, cmd as 'metrics' | 'equity' | 'trades')">
          <span class="el-dropdown-link">
                下载 <el-icon><ArrowDown /></el-icon>
          </span>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="metrics">指标</el-dropdown-item>
                  <el-dropdown-item command="equity">权益</el-dropdown-item>
                  <el-dropdown-item command="trades">交易</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowDown } from '@element-plus/icons-vue'
import { useBacktestStore } from '@/store/useBacktestStore'
import { downloadArtifact } from '@/services/api'

const backtestStore = useBacktestStore()
const router = useRouter()

onMounted(() => {
  backtestStore.refreshHistory().catch(() => undefined)
})

const reload = () => backtestStore.refreshHistory()

const statusTag = (status: string) => {
  switch (status) {
    case 'success':
      return 'success'
    case 'failed':
      return 'danger'
    case 'running':
      return 'primary'
    default:
      return 'info'
  }
}

const formatPct = (val?: number) => (val !== undefined && val !== null ? `${(val * 100).toFixed(2)}%` : '--')

const view = (id: string) => router.push({ name: 'result-detail', params: { id } })

const download = async (id: string, type: 'metrics' | 'equity' | 'trades') => {
  const { data } = await downloadArtifact(id, type)
  const url = window.URL.createObjectURL(new Blob([data]))
  const a = document.createElement('a')
  a.href = url
  a.download = `${id}-${type}.csv`
  a.click()
  window.URL.revokeObjectURL(url)
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
</style>
