<template>
  <div class="card">
    <div style="display: flex; justify-content: space-between; align-items: center;">
      <h3 style="margin: 0;">{{ $t("dataSources") }}</h3>
      <NSpace>
        <NButton type="primary" @click="openCreate">{{ $t("create") }}</NButton>
        <NButton @click="loadDataSources">{{ $t("retry") }}</NButton>
      </NSpace>
    </div>
    <NDataTable :columns="columns" :data="dataSources" :loading="loading" :empty="emptyRender" />
  </div>

  <NModal v-model:show="showCreate" preset="card" :title="$t('newDataSource')" style="width: 640px;">
    <NSpace vertical>
      <NInput v-model:value="form.name" :placeholder="$t('nameRequired')" />
      <NInput v-model:value="form.type" :placeholder="$t('typeRequiredPlaceholder')" />
      <NInput v-model:value="form.path" :placeholder="$t('pathOptional')" />
      <NInput v-model:value="form.symbol" :placeholder="$t('symbolOptional')" />
      <NInput v-model:value="form.description" :placeholder="$t('descriptionOptional')" />
      <div v-if="formError" style="color: red;">{{ formError }}</div>
      <NButton type="primary" :loading="saving" @click="saveDataSource">{{ $t('save') }}</NButton>
    </NSpace>
  </NModal>
</template>

<script setup lang="ts">
import { computed, h, onMounted, ref } from "vue";
import { NButton, NButtonGroup, NDataTable, NInput, NModal, NSpace, NTag, useMessage, NEmpty } from "naive-ui";
import { api } from "../modules/api";
import { useI18n } from "vue-i18n";

const msg = useMessage();
const dataSources = ref<any[]>([]);
const loading = ref(false);
const showCreate = ref(false);
const saving = ref(false);
const formError = ref<string | null>(null);
const { t } = useI18n();

const form = ref({
  name: "",
  type: "",
  path: "",
  symbol: "",
  description: "",
});

const emptyRender = () => h(NEmpty, { description: t("empty") });

const loadDataSources = async () => {
  loading.value = true;
  try {
    dataSources.value = await api.dataSources();
  } catch {
    msg.error(t("loadFailed"));
  } finally {
    loading.value = false;
  }
};

const saveDataSource = async () => {
  formError.value = null;
  if (!form.value.name) {
    formError.value = t("nameRequiredError");
    return;
  }
  if (!form.value.type) {
    formError.value = t("typeRequiredError");
    return;
  }
  saving.value = true;
  try {
    await api.createDataSource(form.value);
    msg.success(t("createSuccess"));
    showCreate.value = false;
    await loadDataSources();
  } catch (err: any) {
    msg.error(err?.response?.data?.detail || t("saveFailed"));
  } finally {
    saving.value = false;
  }
};

const handleProbe = async (row: any) => {
  const res = await api.probeDataSource(row.id);
  const result = res.healthy ? t("healthyStatusNormal") : t("healthyStatusAbnormal");
  msg.success(t("probeResult", { result }));
  await loadDataSources();
};

const columns = computed(() => [
  { title: t("name"), key: "name" },
  { title: t("type"), key: "type" },
  { title: t("path"), key: "path" },
  {
    title: t("healthy"),
    key: "healthy",
    render(row: any) {
      return row.healthy === null || row.healthy === undefined
        ? t("healthyStatusUnknown")
        : h(NTag, { type: row.healthy ? "success" : "error", size: "small" }, { default: () => (row.healthy ? t("healthyStatusNormal") : t("healthyStatusAbnormal")) });
    },
  },
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
              { size: "small", onClick: () => handleProbe(row) },
              { default: () => t("probe") },
            ),
          ],
        },
      );
    },
  },
]);

onMounted(loadDataSources);

const openCreate = () => {
  form.value = { name: "", type: "", path: "", symbol: "", description: "" };
  formError.value = null;
  showCreate.value = true;
};
</script>
