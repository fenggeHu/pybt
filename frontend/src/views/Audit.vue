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
import { computed, onMounted, ref } from "vue";
import { NButton, NDataTable, useMessage } from "naive-ui";
import { api } from "../modules/api";
import { useI18n } from "vue-i18n";

const msg = useMessage();
const logs = ref<any[]>([]);
const loading = ref(false);
const { t } = useI18n();

const loadAudit = async () => {
  loading.value = true;
  try {
    logs.value = await api.audit();
  } catch {
    msg.error(t("loadFailed"));
  } finally {
    loading.value = false;
  }
};

const columns = computed(() => [
  { title: t("time"), key: "timestamp" },
  { title: t("user"), key: "actor" },
  { title: t("action"), key: "action" },
  { title: t("target"), key: "target" },
  { title: t("detail"), key: "detail" },
]);

onMounted(loadAudit);
</script>
