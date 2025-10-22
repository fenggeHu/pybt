<template>
  <div class="layout">
    <el-container>
      <el-aside width="220px" class="aside">
        <div class="logo">pybt</div>
        <el-menu :default-active="activeMenu" router class="menu" collapse-transition>
          <el-menu-item index="/">
            <el-icon><DataAnalysis /></el-icon>
            <span>仪表盘</span>
          </el-menu-item>
          <el-menu-item index="/data">
            <el-icon><Folder /></el-icon>
            <span>数据管理</span>
          </el-menu-item>
          <el-menu-item index="/strategy">
            <el-icon><MagicStick /></el-icon>
            <span>策略配置</span>
          </el-menu-item>
          <el-menu-item index="/backtest">
            <el-icon><Cpu /></el-icon>
            <span>回测执行</span>
          </el-menu-item>
          <el-menu-item index="/history">
            <el-icon><Collection /></el-icon>
            <span>回测历史</span>
          </el-menu-item>
        </el-menu>
      </el-aside>
      <el-container>
        <el-header class="header">
          <div class="header-left">
            <el-breadcrumb separator="/">
              <el-breadcrumb-item v-for="item in breadcrumb" :key="item.path">{{ item.label }}</el-breadcrumb-item>
            </el-breadcrumb>
          </div>
          <div class="header-right">
            <el-switch v-model="darkMode" inline-prompt active-text="🌙" inactive-text="☀️" @change="toggleTheme" />
          </div>
        </el-header>
        <el-main class="main">
          <router-view v-slot="{ Component }">
            <transition name="fade" mode="out-in">
              <component :is="Component" />
            </transition>
          </router-view>
        </el-main>
      </el-container>
    </el-container>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watchEffect } from 'vue'
import { useRoute } from 'vue-router'
import { DataAnalysis, Folder, MagicStick, Cpu, Collection } from '@element-plus/icons-vue'

const route = useRoute()

const darkMode = ref(false)

const breadcrumb = computed(() => {
  const matched = route.matched.filter((m) => !!m.meta.title)
  return matched.map((m) => ({ label: m.meta.title as string, path: m.path }))
})

const activeMenu = computed(() => route.matched[0]?.path ?? '/')

const toggleTheme = () => {
  document.documentElement.classList.toggle('dark', darkMode.value)
}

watchEffect(() => toggleTheme())
</script>

<style scoped lang="scss">
.layout {
  min-height: 100vh;
}

.logo {
  height: var(--layout-header-height);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  font-weight: 700;
  letter-spacing: 2px;
  color: #409eff;
}

.aside {
  background: #fff;
  border-right: 1px solid rgba(0, 0, 0, 0.05);
  display: flex;
  flex-direction: column;
}

.menu {
  border-right: none;
}

.header {
  height: var(--layout-header-height);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  background: #fff;
  border-bottom: 1px solid rgba(0, 0, 0, 0.05);
}

.main {
  padding: 24px;
  background: transparent;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.15s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

html.dark .aside,
html.dark .header {
  background: #1e1e1e;
  border-color: rgba(255, 255, 255, 0.08);
}
</style>
