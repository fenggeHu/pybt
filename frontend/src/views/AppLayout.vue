<template>
  <NLayout has-sider style="min-height: 100vh;">
    <NLayoutSider width="220" bordered>
      <div style="padding: 16px; font-weight: 700;">PyBT</div>
      <NMenu :options="menuOptions" :value="active" @update:value="handleMenu" />
    </NLayoutSider>
    <NLayout>
      <NLayoutHeader bordered style="display: flex; align-items: center; justify-content: space-between; padding: 10px 16px;">
        <div style="display: flex; gap: 10px; align-items: center;">
          <NTag type="success" size="small">{{ $t("runs") }}</NTag>
          <NTag type="info" size="small">{{ $t("configs") }}</NTag>
        </div>
        <div style="display: flex; gap: 8px; align-items: center;">
          <NSelect style="width: 120px;" size="small" v-model:value="ui.language" :options="langOptions" />
          <NSelect style="width: 140px;" size="small" v-model:value="ui.theme" :options="themeOptions" />
          <NDropdown :options="userOptions" trigger="hover" @select="handleUser">
            <NButton quaternary>{{ auth.user?.username || $t("user") }}</NButton>
          </NDropdown>
        </div>
      </NLayoutHeader>
      <NLayoutContent style="padding: 16px;">
        <router-view />
      </NLayoutContent>
    </NLayout>
  </NLayout>
</template>

<script setup lang="ts">
import { computed, watch, onMounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import { NButton, NDropdown, NLayout, NLayoutContent, NLayoutHeader, NLayoutSider, NMenu, NSelect, NTag } from "naive-ui";
import { useAuthStore } from "../stores/auth";
import { useUiStore } from "../stores/ui";
import { useI18n } from "vue-i18n";

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();
const ui = useUiStore();
const { t, locale } = useI18n();

const menuOptions = computed(() => [
  { label: t("overview"), key: "overview", path: "/" },
  { label: t("configs"), key: "configs", path: "/configs" },
  { label: t("dataSources"), key: "data-sources", path: "/data-sources" },
  { label: t("runs"), key: "runs", path: "/runs" },
  { label: t("definitions"), key: "definitions", path: "/definitions" },
  { label: t("audit"), key: "audit", path: "/audit" },
  { label: t("settings"), key: "settings", path: "/settings" },
]);

const active = computed(() => (route.name as string) || "overview");

const handleMenu = (key: string) => {
  const item = menuOptions.value.find((m) => m.key === key);
  if (item?.path) router.push(item.path);
};

const langOptions = computed(() => [
  { label: t("langZh"), value: "zh" },
  { label: t("langEn"), value: "en" },
]);

const themeOptions = computed(() => [
  { label: t("system"), value: "system" },
  { label: t("light"), value: "light" },
  { label: t("dark"), value: "dark" },
]);

const userOptions = computed(() => [
  { label: t("logout"), key: "logout" },
]);

const handleUser = (key: string) => {
  if (key === "logout") {
    auth.logout();
    router.replace("/login");
  }
};

// 主题同步已在 App.vue 中处理

watch(
  () => ui.language,
  (val) => {
    locale.value = val;
  },
  { immediate: true },
);

onMounted(() => {
  if (auth.token && !auth.user) {
    auth.fetchMe().catch(() => {});
  }
});
</script>
