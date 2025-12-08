<template>
  <NConfigProvider :theme="isDark ? darkTheme : null" :theme-overrides="themeOverrides">
    <NMessageProvider>
      <NDialogProvider>
        <router-view />
      </NDialogProvider>
    </NMessageProvider>
  </NConfigProvider>
</template>

<script setup lang="ts">
import { computed, watchEffect } from "vue";
import { darkTheme, useOsTheme, NConfigProvider, NMessageProvider, NDialogProvider, type GlobalThemeOverrides } from "naive-ui";
import { useUiStore } from "./stores/ui";

const ui = useUiStore();
const osTheme = useOsTheme();

const isDark = computed(() => ui.theme === "dark" || (ui.theme === "system" && osTheme.value === "dark"));

// 同步主题到 HTML 属性
watchEffect(() => {
  document.documentElement.dataset.theme = isDark.value ? "dark" : "light";
});

// Naive UI 主题覆盖 - 确保组件在浅色和深色模式下都清晰可见
const lightOverrides: GlobalThemeOverrides = {
  common: {
    primaryColor: "#10b981",
    primaryColorHover: "#34d399",
    primaryColorPressed: "#059669",
    borderColor: "#d1d5db",
    borderRadius: "8px",
  },
  Input: {
    border: "1px solid #d1d5db",
    borderHover: "1px solid #10b981",
    borderFocus: "1px solid #10b981",
    boxShadowFocus: "0 0 0 2px rgba(16, 185, 129, 0.2)",
    color: "#ffffff",
    colorFocus: "#ffffff",
    textColor: "#1f2937",
    placeholderColor: "#9ca3af",
    caretColor: "#10b981",
  },
  Button: {
    colorPrimary: "#10b981",
    colorHoverPrimary: "#34d399",
    colorPressedPrimary: "#059669",
    borderRadiusMedium: "8px",
    textColorPrimary: "#ffffff",
  },
  Card: {
    borderRadius: "12px",
    borderColor: "#e5e7eb",
  },
  Menu: {
    itemTextColorActive: "#10b981",
    itemTextColorActiveHover: "#10b981",
    itemIconColorActive: "#10b981",
    itemIconColorActiveHover: "#10b981",
  },
};

const darkOverrides: GlobalThemeOverrides = {
  common: {
    primaryColor: "#10b981",
    primaryColorHover: "#34d399",
    primaryColorPressed: "#059669",
    borderColor: "#374151",
    borderRadius: "8px",
  },
  Input: {
    border: "1px solid #374151",
    borderHover: "1px solid #10b981",
    borderFocus: "1px solid #10b981",
    boxShadowFocus: "0 0 0 2px rgba(16, 185, 129, 0.3)",
    color: "#1f2937",
    colorFocus: "#1f2937",
    textColor: "#e5e7eb",
    placeholderColor: "#6b7280",
    caretColor: "#10b981",
  },
  Button: {
    colorPrimary: "#10b981",
    colorHoverPrimary: "#34d399",
    colorPressedPrimary: "#059669",
    borderRadiusMedium: "8px",
    textColorPrimary: "#ffffff",
  },
  Card: {
    borderRadius: "12px",
    borderColor: "#374151",
  },
  Menu: {
    itemTextColorActive: "#10b981",
    itemTextColorActiveHover: "#10b981",
    itemIconColorActive: "#10b981",
    itemIconColorActiveHover: "#10b981",
  },
};

const themeOverrides = computed(() => isDark.value ? darkOverrides : lightOverrides);
</script>
