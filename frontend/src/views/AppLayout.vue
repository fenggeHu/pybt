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
            <NButton quaternary>{{ auth.user?.username || "user" }}</NButton>
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
const { locale } = useI18n();

const menuOptions = [
  { label: "概览", key: "overview", path: "/" },
  { label: "配置", key: "configs", path: "/configs" },
  { label: "数据源", key: "data-sources", path: "/data-sources" },
  { label: "任务", key: "runs", path: "/runs" },
  { label: "组件", key: "definitions", path: "/definitions" },
  { label: "审计", key: "audit", path: "/audit" },
  { label: "设置", key: "settings", path: "/settings" },
];

const active = computed(() => (route.name as string) || "overview");

const handleMenu = (key: string) => {
  const item = menuOptions.find((m) => m.key === key);
  if (item?.path) router.push(item.path);
};

const langOptions = [
  { label: "中文", value: "zh" },
  { label: "English", value: "en" },
];

const themeOptions = [
  { label: "跟随系统", value: "system" },
  { label: "亮色", value: "light" },
  { label: "暗色", value: "dark" },
];

const userOptions = [
  { label: "退出登录", key: "logout" },
];

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
