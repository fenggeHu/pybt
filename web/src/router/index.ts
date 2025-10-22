import { createRouter, createWebHistory, RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'dashboard',
    component: () => import('@/views/Dashboard.vue'),
    meta: { title: '仪表盘' }
  },
  {
    path: '/data',
    name: 'data-manager',
    component: () => import('@/views/DataManager.vue'),
    meta: { title: '数据管理' }
  },
  {
    path: '/strategy',
    name: 'strategy-builder',
    component: () => import('@/views/StrategyBuilder.vue'),
    meta: { title: '策略配置' }
  },
  {
    path: '/backtest',
    name: 'backtest-runner',
    component: () => import('@/views/BacktestRunner.vue'),
    meta: { title: '回测执行' }
  },
  {
    path: '/history',
    name: 'history',
    component: () => import('@/views/History.vue'),
    meta: { title: '回测历史' }
  },
  {
    path: '/result/:id',
    name: 'result-detail',
    component: () => import('@/views/ResultDetail.vue'),
    meta: { title: '回测详情' }
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'not-found',
    component: () => import('@/views/NotFound.vue'),
    meta: { title: '未找到' }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
