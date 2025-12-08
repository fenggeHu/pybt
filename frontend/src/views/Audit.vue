<template>
  <div class="card">
    <div style="display: flex; justify-content: space-between; align-items: center;">
      <h3 style="margin: 0;">{{ $t("audit") }}</h3>
      <n-button @click="loadAudit">{{ $t("retry") }}</n-button>
    </div>
    <n-data-table :columns="columns" :data="logs" :loading="loading" />
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { NButton, NDataTable, useMessage } from "naive-ui";
import { api } from "../modules/api";

const msg = useMessage();
const logs = ref<any[]>([]);
const loading = ref(false);

const loadAudit = async () => {
  loading.value = true;
  try {
    logs.value = await api.audit();
  } catch {
    msg.error("加载失败");
  } finally {
    loading.value = false;
  }
};

const columns = [
  { title: "时间", key: "timestamp" },
  { title: "用户", key: "actor" },
  { title: "动作", key: "action" },
  { title: "目标", key: "target" },
  { title: "详情", key: "detail" },
];

onMounted(loadAudit);
</script>
