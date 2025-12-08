import { createApp } from "vue";
import { createPinia } from "pinia";
import { createI18n } from "vue-i18n";

import App from "./App.vue";
import { router, setupRouterGuards } from "./router";
import { messages } from "./modules/i18n";
import "./assets/styles.css";

const i18n = createI18n({
  legacy: false,
  locale: "zh",
  fallbackLocale: "en",
  messages,
});

const app = createApp(App);
const pinia = createPinia();

setupRouterGuards(pinia);
app.use(pinia);
app.use(router);
app.use(i18n);
app.mount("#app");
