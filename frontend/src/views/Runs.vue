<template>
  <div class="card">
    <div style="display: flex; justify-content: space-between; align-items: center;">
      <h3 style="margin: 0;">{{ $t("runs") }}</h3>
      <NSpace>
        <NButton type="primary" @click="openCreate">{{ $t("create") }}</NButton>
        <NButton @click="loadRuns">{{ $t("retry") }}</NButton>
      </NSpace>
    </div>
    <NDataTable :columns="columns" :data="runs" :loading="loading" :empty="emptyRender" />
  </div>

  <NModal v-model:show="showCreate" preset="card" :title="$t('newRun')" style="width: 720px;">
    <NSpace vertical>
      <NInput v-model:value="form.name" :placeholder="$t('nameRequired')" />
      <NInput v-model:value="form.config_id" :placeholder="$t('configIdOptional')" />
      <NInput type="textarea" rows="8" v-model:value="form.json" :placeholder="$t('configJsonOptional')" />
      <div v-if="formError" style="color: red;">{{ formError }}</div>
      <NButton type="primary" :loading="saving" @click="createRun">{{ $t('run') }}</NButton>
    </NSpace>
  </NModal>
</template>

<script setup lang="ts">
import { computed, h, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { NButton, NButtonGroup, NDataTable, NInput, NModal, NSpace, NTag, useMessage, NEmpty } from "naive-ui";
import { api } from "../modules/api";
import { useI18n } from "vue-i18n";

const router = useRouter();
const msg = useMessage();
const runs = ref<any[]>([]);
const loading = ref(false);
const showCreate = ref(false);
const saving = ref(false);
const formError = ref<string | null>(null);
const { t } = useI18n();

const form = ref({
  name: "",
  config_id: "",
  json: "",
});

const emptyRender = () => h(NEmpty, { description: t("empty") });

const loadRuns = async () => {
  loading.value = true;
  try {
    runs.value = await api.runs();
  } catch {
    msg.error(t("loadFailed"));
  } finally {
    loading.value = false;
  }
};

const createRun = async () => {
  formError.value = null;
  if (!form.value.name) {
    formError.value = t("nameRequiredError");
    return;
  }
  saving.value = true;
  try {
    const body: any = { name: form.value.name };
    if (form.value.config_id) body.config_id = form.value.config_id;
    if (form.value.json) body.config = JSON.parse(form.value.json);
    const run = await api.createRun(body);
    msg.success(t("createSuccess"));
    showCreate.value = false;
    await loadRuns();
    router.push(`/runs/${run.id}`);
  } catch (err: any) {
    msg.error(err?.response?.data?.detail || t("createFailed"));
  } finally {
    saving.value = false;
  }
};

const handleCancel = async (row: any) => {
  await api.cancelRun(row.id);
  msg.success(t("cancelSuccess"));
  await loadRuns();
};

const columns = computed(() => [
  { title: t("name"), key: "name" },
  { title: t("status"), key: "status", render: (row: any) => h(NTag, { type: row.status === "succeeded" ? "success" : row.status === "failed" ? "error" : "info", size: "small" }, { default: () => row.status }) },
  { title: t("progress"), key: "progress", render: (row: any) => `${Math.round((row.progress || 0) * 100)}%` },
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
              { size: "small", onClick: () => router.push(`/runs/${row.id}`) },
              { default: () => t("details") },
            ),
            h(
              NButton,
              { size: "small", onClick: () => handleCancel(row) },
              { default: () => t("cancel") },
            ),
          ],
        },
      );
    },
  },
]);

onMounted(loadRuns);

const openCreate = () => {
  form.value = { name: "", config_id: "", json: "" };
  formError.value = null;
  showCreate.value = true;
};
</script>
