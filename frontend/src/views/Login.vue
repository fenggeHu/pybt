<template>
  <div class="login-container">
    <h2>{{ isRegister ? $t("register") : $t("login") }}</h2>
    <NInput
      v-model:value="username"
      :placeholder="$t('username')"
      size="large"
      clearable
    >
      <template #prefix>
        <span style="color: var(--muted);">👤</span>
      </template>
    </NInput>
    <NInput
      v-model:value="password"
      type="password"
      :placeholder="$t('password')"
      size="large"
      show-password-on="click"
    >
      <template #prefix>
        <span style="color: var(--muted);">🔒</span>
      </template>
    </NInput>
    <NInput
      v-if="isRegister"
      v-model:value="confirmPassword"
      type="password"
      :placeholder="$t('confirmPassword')"
      size="large"
      show-password-on="click"
    >
      <template #prefix>
        <span style="color: var(--muted);">✅</span>
      </template>
    </NInput>
    <NButton
      type="primary"
      size="large"
      block
      :loading="loading"
      @click="onSubmit"
    >
      {{ isRegister ? $t("register") : $t("login") }}
    </NButton>
    <div class="small auth-switch">
      <template v-if="isRegister">
        <span>{{ $t("haveAccount") }}</span>
        <a href="#" @click.prevent="switchMode('login')">{{ $t("goLogin") }}</a>
      </template>
      <template v-else>
        <span>{{ $t("noAccount") }}</span>
        <a href="#" @click.prevent="switchMode('register')">{{ $t("goRegister") }}</a>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { useRouter, useRoute } from "vue-router";
import { useMessage, NButton, NInput } from "naive-ui";
import { useAuthStore } from "../stores/auth";
import { useI18n } from "vue-i18n";

const username = ref("");
const password = ref("");
const confirmPassword = ref("");
const mode = ref<"login" | "register">("login");
const loading = ref(false);
const msg = useMessage();
const auth = useAuthStore();
const router = useRouter();
const route = useRoute();
const { t } = useI18n();

const isRegister = computed(() => mode.value === "register");

const switchMode = (nextMode: "login" | "register") => {
  mode.value = nextMode;
  loading.value = false;
  confirmPassword.value = "";
};

const onSubmit = async () => {
  if (!username.value || !password.value || (isRegister.value && !confirmPassword.value)) {
    msg.error(isRegister.value ? t("registerMissingFields") : t("loginMissingFields"));
    return;
  }
  if (isRegister.value && password.value !== confirmPassword.value) {
    msg.error(t("passwordMismatch"));
    return;
  }
  loading.value = true;
  try {
    if (isRegister.value) {
      await auth.register(username.value, password.value);
      msg.success(t("registerSuccess"));
    } else {
      await auth.login(username.value, password.value);
      msg.success(t("loginSuccess"));
    }
    await auth.fetchMe();
    const redirect = (route.query.redirect as string) || "/";
    router.replace(redirect);
  } catch (err: any) {
    const fallback = isRegister.value ? t("registerFailed") : t("loginFailed");
    msg.error(err?.response?.data?.detail || fallback);
  } finally {
    loading.value = false;
  }
};
</script>
