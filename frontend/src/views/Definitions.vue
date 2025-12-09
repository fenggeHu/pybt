<template>
  <div class="card">
    <div style="display: flex; justify-content: space-between; align-items: center;">
      <h3 style="margin: 0;">{{ $t("definitions") }}</h3>
      <n-button @click="loadDefs">{{ $t("retry") }}</n-button>
    </div>
    <n-data-table :columns="columns" :data="defs" :loading="loading" />
  </div>
</template>

<script setup lang="ts">
import { computed, h, onMounted, ref } from "vue";
import { NButton, NDataTable, NTag, useMessage } from "naive-ui";
import { api } from "../modules/api";
import type { DefinitionItem } from "../types";
import { useI18n } from "vue-i18n";

const defs = ref<DefinitionItem[]>([]);
const loading = ref(false);
const msg = useMessage();
const { t } = useI18n();

const loadDefs = async () => {
  loading.value = true;
  try {
    defs.value = await api.definitions();
  } catch {
    msg.error(t("loadFailed"));
  } finally {
    loading.value = false;
  }
};

const columns = computed(() => [
  { title: t("type"), key: "type" },
  { title: t("category"), key: "category", render: (row: any) => h(NTag, { size: "small" }, { default: () => row.category }) },
  { title: t("summary"), key: "summary" },
  {
    title: t("parameters"),
    key: "params",
    render(row: any) {
      if (!row.params?.length) return "-";
      return h(
        "div",
        { style: "display:flex;flex-direction:column;gap:4px;" },
        row.params.map((p: any) =>
          h("span", null, `${p.name}${p.required ? "*" : ""} (${p.type})${p.default !== undefined ? `=${p.default}` : ""}`),
        ),
      );
    },
  },
]);

onMounted(loadDefs);
</script>
