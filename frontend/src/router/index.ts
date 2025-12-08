import { createRouter, createWebHistory, type NavigationGuardNext, type RouteLocationNormalized } from "vue-router";

import AuthLayout from "../views/AuthLayout.vue";
import Login from "../views/Login.vue";
import AppLayout from "../views/AppLayout.vue";
import Overview from "../views/Overview.vue";
import Configs from "../views/Configs.vue";
import DataSources from "../views/DataSources.vue";
import Runs from "../views/Runs.vue";
import RunDetail from "../views/RunDetail.vue";
import Definitions from "../views/Definitions.vue";
import Audit from "../views/Audit.vue";
import Settings from "../views/Settings.vue";
import type { Pinia } from "pinia";
import { useAuthStore } from "../stores/auth";

const routes = [
  {
    path: "/login",
    component: AuthLayout,
    children: [{ path: "", name: "login", component: Login }],
  },
  {
    path: "/",
    component: AppLayout,
    children: [
      { path: "", name: "overview", component: Overview },
      { path: "configs", name: "configs", component: Configs },
      { path: "data-sources", name: "data-sources", component: DataSources },
      { path: "runs", name: "runs", component: Runs },
      { path: "runs/:id", name: "run-detail", component: RunDetail, props: true },
      { path: "definitions", name: "definitions", component: Definitions },
      { path: "audit", name: "audit", component: Audit },
      { path: "settings", name: "settings", component: Settings },
    ],
  },
];

export const router = createRouter({
  history: createWebHistory(),
  routes,
});

export const setupRouterGuards = (pinia: Pinia) => {
  router.beforeEach((to: RouteLocationNormalized, _from: RouteLocationNormalized, next: NavigationGuardNext) => {
    const auth = useAuthStore(pinia);
    const isAuthed = !!auth.token;

    if (to.name === "login") {
      if (isAuthed) return next({ name: "overview" });
      return next();
    }
    if (!isAuthed) {
      return next({ name: "login", query: { redirect: to.fullPath } });
    }
    return next();
  });
};
