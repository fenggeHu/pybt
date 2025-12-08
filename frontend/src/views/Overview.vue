<template>
  <div class="card">
    <h3 style="margin-top: 0;">{{ $t("overview") }}</h3>
    <n-grid :cols="3" x-gap="12" y-gap="12">
      <n-gi>
        <n-statistic label="运行中任务" :value="runningCount" />
      </n-gi>
      <n-gi>
        <n-statistic label="配置模板" :value="configsCount" />
      </n-gi>
      <n-gi>
        <n-statistic label="数据源" :value="dataSourceCount" />
      </n-gi>
    </n-grid>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { NGrid, NGi, NStatistic } from "naive-ui";
import { api } from "../modules/api";

const runs = ref<any[]>([]);
const configs = ref<any[]>([]);
const dataSources = ref<any[]>([]);

const runningCount = computed(() => runs.value.filter((r) => r.status === "running").length);
const configsCount = computed(() => configs.value.length);
const dataSourceCount = computed(() => dataSources.value.length);

onMounted(async () => {
  runs.value = await api.runs().catch(() => []);
  configs.value = await api.configs().catch(() => []);
  dataSources.value = await api.dataSources().catch(() => []);
});
</script>
