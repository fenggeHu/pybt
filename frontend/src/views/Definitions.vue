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
import { h, onMounted, ref } from "vue";
import { NButton, NButtonGroup, NDataTable, NTag, useMessage } from "naive-ui";
import { api } from "../modules/api";
import type { DefinitionItem } from "../types";

const defs = ref<DefinitionItem[]>([]);
const loading = ref(false);
const msg = useMessage();

const loadDefs = async () => {
  loading.value = true;
  try {
    defs.value = await api.definitions();
  } catch {
    msg.error("加载失败");
  } finally {
    loading.value = false;
  }
};

const columns = [
  { title: "类型", key: "type" },
  { title: "类别", key: "category", render: (row: any) => h(NTag, { size: "small" }, { default: () => row.category }) },
  { title: "摘要", key: "summary" },
  {
    title: "参数",
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
];

onMounted(loadDefs);
</script>
