<template>
  <div class="card">
    <h3 style="margin-top: 0;">{{ $t("settings") }}</h3>
    <n-space vertical>
      <div>{{ $t("apiBase") }}: {{ apiBase }}</div>
      <n-select v-model:value="ui.theme" :options="themeOptions" label-field="label" value-field="value" />
      <n-select v-model:value="ui.language" :options="langOptions" label-field="label" value-field="value" />
    </n-space>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { NSelect, NSpace } from "naive-ui";
import { useUiStore } from "../stores/ui";
import { useI18n } from "vue-i18n";

const ui = useUiStore();
const apiBase = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000/api";
const { t } = useI18n();

const themeOptions = computed(() => [
  { label: t("system"), value: "system" },
  { label: t("light"), value: "light" },
  { label: t("dark"), value: "dark" },
]);

const langOptions = computed(() => [
  { label: t("langZh"), value: "zh" },
  { label: t("langEn"), value: "en" },
]);
</script>
