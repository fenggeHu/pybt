<template>
  <div class="card">
    <div style="display: flex; justify-content: space-between; align-items: center;">
      <h3 style="margin: 0;">{{ $t("configs") }}</h3>
      <NSpace>
        <NButton type="primary" @click="openCreate">{{ $t("create") }}</NButton>
        <NButton @click="loadConfigs">{{ $t("retry") }}</NButton>
      </NSpace>
    </div>
    <NDataTable :columns="columns" :data="configs" :loading="loading" :empty="emptyRender" />
  </div>

  <NModal v-model:show="showCreate" preset="card" :title="$t('newConfig')" style="width: 720px;">
    <NSpace vertical>
      <NInput v-model:value="form.name" :placeholder="$t('nameRequired')" />
      <NInput v-model:value="form.description" :placeholder="$t('descriptionOptional')" />
      <NInput type="textarea" rows="10" v-model:value="form.json" :placeholder="$t('configJsonRequired')" />
      <div v-if="formError" style="color: red;">{{ formError }}</div>
      <NSpace>
        <NButton secondary @click="validateConfig">{{ $t('validate') }}</NButton>
        <NButton type="primary" :loading="saving" @click="saveConfig">{{ $t('save') }}</NButton>
      </NSpace>
      <div v-if="validateMsg" :style="{ color: validateOk ? 'green' : 'red' }">{{ validateMsg }}</div>
    </NSpace>
  </NModal>
</template>

<script setup lang="ts">
import { computed, h, onMounted, ref } from "vue";
import { NButton, NButtonGroup, NDataTable, NInput, NModal, NSpace, useMessage, NEmpty } from "naive-ui";
import { api } from "../modules/api";
import { useI18n } from "vue-i18n";

const msg = useMessage();
const configs = ref<any[]>([]);
const loading = ref(false);
const showCreate = ref(false);
const saving = ref(false);
const validateMsg = ref<string | null>(null);
const validateOk = ref(false);
const formError = ref<string | null>(null);
const { t } = useI18n();

const form = ref({
  name: "",
  description: "",
  json: "",
});

const emptyRender = () => h(NEmpty, { description: t("empty") });

const loadConfigs = async () => {
  loading.value = true;
  try {
    configs.value = await api.configs();
  } catch {
    msg.error(t("loadFailed"));
  } finally {
    loading.value = false;
  }
};

const parseJson = () => {
  try {
    const body = JSON.parse(form.value.json || "{}");
    return body;
  } catch (err: any) {
    formError.value = err.message || t("jsonParseFailed");
    return null;
  }
};

const validateConfig = async () => {
  try {
    formError.value = null;
    if (!form.value.name) {
      formError.value = t("nameRequiredError");
      return;
    }
    if (!form.value.json) {
      formError.value = t("configJsonRequiredError");
      return;
    }
    const body = parseJson();
    if (!body) return;
    const res = await api.validateConfig(body);
    validateOk.value = res.ok;
    validateMsg.value = res.detail || (res.ok ? t("validateResultValid") : t("validateResultInvalid"));
  } catch (err: any) {
    validateOk.value = false;
    validateMsg.value = err.message || t("validateFailed");
  }
};

const saveConfig = async () => {
  formError.value = null;
  if (!form.value.name) {
    formError.value = t("nameRequiredError");
    return;
  }
  if (!form.value.json) {
    formError.value = t("configJsonRequiredError");
    return;
  }
  const body = parseJson();
  if (!body) return;
  saving.value = true;
  try {
    await api.createConfig({ name: form.value.name, description: form.value.description, config: body });
    msg.success(t("createSuccess"));
    showCreate.value = false;
    validateMsg.value = null;
    await loadConfigs();
  } catch (err: any) {
    msg.error(err?.response?.data?.detail || err.message || t("saveFailed"));
  } finally {
    saving.value = false;
  }
};

const handleDelete = async (row: any) => {
  await api.deleteConfig(row.id);
  msg.success(t("deleteSuccess"));
  await loadConfigs();
};

const openCreate = () => {
  form.value = { name: "", description: "", json: "" };
  validateMsg.value = null;
  validateOk.value = false;
  formError.value = null;
  showCreate.value = true;
};

const columns = computed(() => [
  { title: t("name"), key: "name" },
  { title: t("description"), key: "description" },
  { title: t("updatedAt"), key: "updated_at" },
  {
    title: t("actions"),
    key: "actions",
    render(row: any) {
      return h(
        NButtonGroup,
        null,
        {
          default: () => [
            h(
              NButton,
              { size: "small", onClick: () => handleDelete(row) },
              { default: () => t("delete") },
            ),
          ],
        },
      );
    },
  },
]);

onMounted(loadConfigs);
</script>
