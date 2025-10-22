<template>
  <div class="page">
    <el-card shadow="never" class="header-card">
      <div class="header-row">
        <div>
          <h2>回测执行</h2>
          <p>选择数据集与策略，配置执行参数后启动回测。</p>
        </div>
        <el-button type="primary" :loading="submitting" @click="run">立即回测</el-button>
      </div>
    </el-card>

    <el-row :gutter="16">
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header>基础配置</template>
          <el-form :model="form" label-width="120px">
            <el-form-item label="数据集">
              <el-select v-model="form.datasetId" placeholder="选择数据集">
                <el-option v-for="item in datasetStore.datasets" :key="item.id" :label="item.name" :value="item.id" />
              </el-select>
            </el-form-item>
            <el-form-item label="策略">
              <el-select v-model="form.strategyIds" multiple placeholder="选择策略">
                <el-option v-for="item in strategyStore.strategies" :key="item.id" :label="item.name" :value="item.id" />
              </el-select>
            </el-form-item>
            <el-form-item label="初始资金">
              <el-input-number v-model="form.cash" :min="10_000" :step="10_000" />
            </el-form-item>
            <el-form-item label="滑点 (bps)">
              <el-input-number v-model="form.slipBps" :min="0" :max="50" />
            </el-form-item>
            <el-form-item label="佣金/股">
              <el-input-number v-model="form.commission" :min="0" :step="0.001" />
            </el-form-item>
            <el-form-item label="佣金比例">
              <el-input-number v-model="form.commissionRate" :min="0" :max="0.01" :step="0.0005" />
            </el-form-item>
            <el-form-item label="成交量占比">
              <el-slider v-model="form.volumeLimit" :min="0.1" :max="1" :step="0.05" :format-tooltip="(v) => `${Math.round(v * 100)}%`" />
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>

      <el-col :span="12">
        <el-card shadow="hover">
          <template #header>风控与分配</template>
          <el-form :model="form" label-width="120px">
            <el-form-item label="最大持仓 (单位)">
              <el-input-number v-model="form.risk.maxUnits" :min="1" />
            </el-form-item>
            <el-form-item label="止损比例">
              <el-input-number v-model="form.risk.stopLossPct" :min="0" :max="0.5" :step="0.01" />
            </el-form-item>
            <el-divider content-position="left">Allocator (可选)</el-divider>
            <el-form-item label="最大杠杆">
              <el-input-number v-model="form.allocator.maxLeverage" :min="0" :max="5" :step="0.1" />
            </el-form-item>
            <el-form-item label="最小手数">
              <el-input-number v-model="form.allocator.lotSize" :min="1" />
            </el-form-item>
            <el-form-item label="取整模式">
              <el-select v-model="form.allocator.rounding">
                <el-option label="四舍五入" value="round" />
                <el-option label="向下取整" value="floor" />
                <el-option label="向上取整" value="ceil" />
              </el-select>
            </el-form-item>
            <el-form-item label="备注">
              <el-input v-model="form.notes" type="textarea" :rows="3" />
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="hover">
      <template #header>近期结果</template>
      <el-table :data="backtestStore.summaries" empty-text="暂无记录" v-loading="backtestStore.loading">
        <el-table-column prop="name" label="任务" />
        <el-table-column prop="status" label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="statusTag(row.status)">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="startedAt" label="开始时间" width="180" />
        <el-table-column prop="totalReturn" label="收益" width="120">
          <template #default="{ row }">{{ formatPct(row.totalReturn) }}</template>
        </el-table-column>
        <el-table-column prop="sharpe" label="Sharpe" width="100">
          <template #default="{ row }">{{ row.sharpe?.toFixed?.(2) ?? '--' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="160">
          <template #default="{ row }">
            <el-button link type="primary" @click="view(row.id)">查看</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import { useBacktestStore } from '@/store/useBacktestStore'
import { useDatasetStore } from '@/store/useDatasetStore'
import { useStrategyStore } from '@/store/useStrategyStore'

const backtestStore = useBacktestStore()
const datasetStore = useDatasetStore()
const strategyStore = useStrategyStore()
const router = useRouter()
const submitting = ref(false)

const form = reactive({
  datasetId: '',
  strategyIds: [] as string[],
  cash: 100_000,
  slipBps: 1,
  commission: 0,
  commissionRate: 0,
  volumeLimit: 0.3,
  risk: {
    maxUnits: 5,
    stopLossPct: 0.1
  },
  allocator: {
    maxLeverage: 1.0,
    lotSize: 1,
    rounding: 'round' as 'round' | 'floor' | 'ceil'
  },
  notes: ''
})

onMounted(() => {
  Promise.all([
    datasetStore.fetchDatasets(),
    strategyStore.fetchStrategies(),
    backtestStore.refreshHistory()
  ]).catch(() => undefined)
})

const run = async () => {
  if (!form.datasetId || form.strategyIds.length === 0) {
    ElMessage.warning('请选择数据集与策略')
    return
  }
  submitting.value = true
  try {
    const payload = { ...form }
    const taskId = await backtestStore.runBacktest(payload)
    ElMessage.success(`已提交任务 ${taskId}`)
  } catch (err) {
    ElMessage.error('提交失败')
  } finally {
    submitting.value = false
  }
}

const statusTag = (status: string) => {
  if (status === 'success') return 'success'
  if (status === 'failed') return 'danger'
  if (status === 'running') return 'primary'
  return 'info'
}

const formatPct = (val?: number) => {
  if (val === undefined || val === null) return '--'
  return `${(val * 100).toFixed(2)}%`
}

const view = (id: string) => router.push({ name: 'result-detail', params: { id } })
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
