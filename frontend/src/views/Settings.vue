<template>
  <div class="card">
    <h3 style="margin-top: 0;">{{ $t("settings") }}</h3>
    <n-space vertical>
      <div>API Base (只读，env VITE_API_BASE): {{ apiBase }}</div>
      <n-select v-model:value="ui.theme" :options="themeOptions" label-field="label" value-field="value" />
      <n-select v-model:value="ui.language" :options="langOptions" label-field="label" value-field="value" />
    </n-space>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { NSelect, NSpace } from "naive-ui";
import { useUiStore } from "../stores/ui";

const ui = useUiStore();
const apiBase = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000/api";

const themeOptions = [
  { label: "跟随系统", value: "system" },
  { label: "亮色", value: "light" },
  { label: "暗色", value: "dark" },
];

const langOptions = [
  { label: "中文", value: "zh" },
  { label: "English", value: "en" },
];
</script>
