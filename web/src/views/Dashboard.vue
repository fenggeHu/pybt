<template>
  <div class="page">
    <el-row :gutter="16">
      <el-col :span="6" v-for="item in metrics" :key="item.label">
        <el-card shadow="hover" class="metric-card">
          <div class="metric-label">{{ item.label }}</div>
          <div class="metric-value">{{ item.value }}</div>
          <div class="metric-desc">{{ item.desc }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" class="mt">
      <el-col :span="16">
        <el-card shadow="hover" class="chart-card">
          <template #header>
            <span>权益曲线</span>
          </template>
          <LineChart :series="equitySeries" />
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover">
          <template #header>
            <span>运行概览</span>
          </template>
          <el-timeline>
            <el-timeline-item v-for="item in timeline" :key="item.time" :timestamp="item.time" :type="item.type">
              {{ item.message }}
            </el-timeline-item>
          </el-timeline>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useBacktestStore } from '@/store/useBacktestStore'
import LineChart from '@/components/charts/LineChart.vue'

const backtestStore = useBacktestStore()

onMounted(() => {
  backtestStore.refreshHistory().catch(() => undefined)
})

const metrics = computed(() => {
  const last = backtestStore.summaries[0]
  return [
    { label: '进行中的任务', value: backtestStore.runningCount, desc: '排队 + 执行' },
    { label: '最新回测年化', value: last?.sharpe?.toFixed?.(2) ?? '--', desc: 'Sharpe Ratio' },
    { label: '最新回测收益', value: last?.totalReturn ? `${(last.totalReturn * 100).toFixed(2)}%` : '--', desc: last?.name ?? '—' },
    { label: '可用数据集', value: '-', desc: '数据管理页查看' }
  ]
})

const equitySeries = computed(() => {
  const anyResult = Object.values(backtestStore.results)[0]
  if (!anyResult) return []
  return [
    {
      name: 'Equity',
      data: anyResult.equity.map((item) => [item.dt, item.equity])
    }
  ]
})

const timeline = computed(() => {
  return backtestStore.summaries.slice(0, 5).map((s) => ({
    time: s.startedAt,
    message: `${s.name} [${s.status}]`,
    type: s.status === 'success' ? 'success' : s.status === 'failed' ? 'danger' : 'info'
  }))
})
</script>

<style scoped lang="scss">
.page {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.metric-card {
  border-radius: 12px;
}

.metric-label {
  font-size: 14px;
  color: #888;
  margin-bottom: 6px;
}

.metric-value {
  font-size: 24px;
  font-weight: 600;
}

.metric-desc {
  font-size: 13px;
  color: #a0a0a0;
}

.mt {
  margin-top: 8px;
}
</style>
