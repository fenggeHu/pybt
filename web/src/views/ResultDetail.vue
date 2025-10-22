<template>
  <div class="page" v-loading="loading">
    <template v-if="result">
      <el-page-header @back="goBack" content="回测详情" class="page-header">
        <template #title>{{ result.summary.name }}</template>
        <template #extra>
          <el-tag :type="statusTag(result.summary.status)">{{ result.summary.status }}</el-tag>
        </template>
      </el-page-header>

      <el-row :gutter="16">
        <el-col :span="8" v-for="metric in metricList" :key="metric.label">
          <el-card shadow="hover" class="metric-card">
            <div class="metric-label">{{ metric.label }}</div>
            <div class="metric-value">{{ metric.value }}</div>
            <div class="metric-desc">{{ metric.desc }}</div>
          </el-card>
        </el-col>
      </el-row>

      <el-row :gutter="16" class="mt">
        <el-col :span="16">
          <el-card shadow="hover" class="chart-card">
            <template #header>权益曲线</template>
            <LineChart :series="equitySeries" />
          </el-card>
        </el-col>
        <el-col :span="8">
          <el-card shadow="hover">
            <template #header>交易统计</template>
            <el-descriptions :column="1" border size="small">
              <el-descriptions-item label="笔数">{{ trades.length }}</el-descriptions-item>
              <el-descriptions-item label="胜率">{{ formatPct(metrics.trade_win_rate) }}</el-descriptions-item>
              <el-descriptions-item label="盈亏因子">{{ metrics.trade_profit_factor?.toFixed?.(2) ?? '--' }}</el-descriptions-item>
              <el-descriptions-item label="平均持有天">{{ metrics.trade_avg_hold_days?.toFixed?.(1) ?? '--' }}</el-descriptions-item>
            </el-descriptions>
          </el-card>
        </el-col>
      </el-row>

      <el-card shadow="hover" class="mt">
        <template #header>成交明细</template>
        <el-table :data="trades" height="360">
          <el-table-column prop="symbol" label="标的" width="120" />
          <el-table-column prop="side" label="方向" width="100" />
          <el-table-column prop="qty" label="数量" width="100" />
          <el-table-column prop="entry_dt" label="开仓" width="180" />
          <el-table-column prop="exit_dt" label="平仓" width="180" />
          <el-table-column prop="pnl" label="盈亏" width="120">
            <template #default="{ row }">{{ row.pnl.toFixed(2) }}</template>
          </el-table-column>
          <el-table-column prop="tag" label="标签" />
        </el-table>
      </el-card>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useBacktestStore } from '@/store/useBacktestStore'
import LineChart from '@/components/charts/LineChart.vue'

const route = useRoute()
const router = useRouter()
const backtestStore = useBacktestStore()

const loading = ref(false)
const resultId = route.params.id as string
const result = ref(await backtestStore.getResult(resultId).catch(() => undefined))

onMounted(async () => {
  if (!result.value) {
    loading.value = true
    try {
      const data = await backtestStore.getResult(resultId)
      result.value = data
    } finally {
      loading.value = false
    }
  }
})

const metrics = computed(() => result.value?.metrics ?? {})
const trades = computed(() => result.value?.trades ?? [])

const metricList = computed(() => {
  if (!result.value) return []
  const summary = result.value.summary
  return [
    { label: '总收益', value: formatPct(summary.totalReturn), desc: 'Total Return' },
    { label: '年化收益', value: formatPct(result.value.metrics.cagr), desc: 'CAGR' },
    { label: 'Sharpe', value: result.value.metrics.sharpe?.toFixed?.(2) ?? '--', desc: 'Sharpe Ratio' },
    { label: '最大回撤', value: formatPct(result.value.metrics.max_drawdown), desc: 'Max Drawdown' }
  ]
})

const equitySeries = computed(() => {
  if (!result.value) return []
  return [
    {
      name: 'Equity',
      data: result.value.equity.map((it) => [it.dt, it.equity])
    }
  ]
})

const statusTag = (status: string) => {
  if (status === 'success') return 'success'
  if (status === 'failed') return 'danger'
  if (status === 'running') return 'primary'
  return 'info'
}

const formatPct = (val?: number) => (val !== undefined && val !== null ? `${(val * 100).toFixed(2)}%` : '--')

const goBack = () => router.back()
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
  color: #808080;
  margin-bottom: 6px;
}

.metric-value {
  font-size: 22px;
  font-weight: 600;
}

.metric-desc {
  color: #a0a0a0;
  font-size: 12px;
}

.page-header {
  background: none;
  padding: 0;
}

.mt {
  margin-top: 8px;
}
</style>
