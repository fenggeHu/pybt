import { createApp } from "vue";
import { createPinia } from "pinia";

import App from "./App.vue";
import { router, setupRouterGuards } from "./router";
import { i18n } from "./modules/i18n";
import "./assets/styles.css";

const app = createApp(App);
const pinia = createPinia();

setupRouterGuards(pinia);
app.use(pinia);
app.use(router);
app.use(i18n);
app.mount("#app");
