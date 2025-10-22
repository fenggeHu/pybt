<template>
  <div class="page">
    <el-card shadow="never" class="header-card">
      <div class="header-row">
        <div>
          <h2>策略配置</h2>
          <p>维护 SMA、Breakout、Weighted 等参数模板。</p>
        </div>
        <el-button type="primary" @click="openDialog()">新建策略</el-button>
      </div>
    </el-card>

    <el-card shadow="hover">
      <el-table :data="strategyStore.strategies" v-loading="strategyStore.loading" empty-text="暂无策略">
        <el-table-column prop="name" label="名称" width="200" />
        <el-table-column prop="type" label="类型" width="120" />
        <el-table-column prop="updatedAt" label="更新时间" width="180" />
        <el-table-column label="参数">
          <template #default="{ row }">
            <pre class="params">{{ formatParams(row.params) }}</pre>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120">
          <template #default="{ row }">
            <el-button link type="primary" @click="openDialog(row)">编辑</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="480px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="名称">
          <el-input v-model="form.name" placeholder="策略名称" />
        </el-form-item>
        <el-form-item label="类型">
          <el-select v-model="form.type" placeholder="选择类型">
            <el-option label="SMA" value="sma" />
            <el-option label="Breakout" value="breakout" />
            <el-option label="Weighted" value="weighted" />
          </el-select>
        </el-form-item>
        <el-form-item label="参数 (JSON)">
          <el-input type="textarea" v-model="paramsJson" :rows="8" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { useStrategyStore } from '@/store/useStrategyStore'
import type { StrategyConfig } from '@/types'

const strategyStore = useStrategyStore()
const dialogVisible = ref(false)
const form = reactive<Partial<StrategyConfig>>({ type: 'sma' })
const paramsJson = ref('{}')

onMounted(() => {
  strategyStore.fetchStrategies().catch(() => undefined)
})

const openDialog = (row?: StrategyConfig) => {
  if (row) {
    Object.assign(form, row)
    paramsJson.value = JSON.stringify(row.params, null, 2)
  } else {
    Object.assign(form, { id: undefined, name: '', type: 'sma', params: {} })
    paramsJson.value = '{\n  "fast": 10,\n  "slow": 30\n}'
  }
  dialogVisible.value = true
}

const dialogTitle = computed(() => (form?.id ? '编辑策略' : '新建策略'))

const submit = async () => {
  try {
    form.params = JSON.parse(paramsJson.value || '{}')
  } catch (err) {
    return ElMessage.error('参数 JSON 格式错误')
  }
  await strategyStore.upsertStrategy(form)
  dialogVisible.value = false
}

const formatParams = (params: Record<string, unknown>) => JSON.stringify(params, null, 2)
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

.params {
  white-space: pre-wrap;
  font-size: 12px;
  margin: 0;
}
</style>
