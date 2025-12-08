<template>
  <div class="login-container">
    <h2>{{ $t("login") }}</h2>
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
    <NButton
      type="primary"
      size="large"
      block
      :loading="loading"
      @click="onSubmit"
    >
      {{ $t("login") }}
    </NButton>
  </div>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { useRouter, useRoute } from "vue-router";
import { useMessage, NButton, NInput } from "naive-ui";
import { useAuthStore } from "../stores/auth";

const username = ref("");
const password = ref("");
const loading = ref(false);
const msg = useMessage();
const auth = useAuthStore();
const router = useRouter();
const route = useRoute();

const onSubmit = async () => {
  if (!username.value || !password.value) {
    msg.error("请输入用户名和密码");
    return;
  }
  loading.value = true;
  try {
    await auth.login(username.value, password.value);
    await auth.fetchMe();
    msg.success("登录成功");
    const redirect = (route.query.redirect as string) || "/";
    router.replace(redirect);
  } catch (err: any) {
    msg.error(err?.response?.data?.detail || "登录失败");
  } finally {
    loading.value = false;
  }
};
</script>
