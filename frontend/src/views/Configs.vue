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

  <NModal v-model:show="showCreate" preset="card" title="新建配置" style="width: 720px;">
    <NSpace vertical>
      <NInput v-model:value="form.name" placeholder="名称（必填）" />
      <NInput v-model:value="form.description" placeholder="描述" />
      <NInput type="textarea" rows="10" v-model:value="form.json" placeholder="粘贴配置 JSON（必填）" />
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
import { h, onMounted, ref } from "vue";
import { NButton, NButtonGroup, NDataTable, NInput, NModal, NSpace, useMessage, NEmpty } from "naive-ui";
import { api } from "../modules/api";

const msg = useMessage();
const configs = ref<any[]>([]);
const loading = ref(false);
const showCreate = ref(false);
const saving = ref(false);
const validateMsg = ref<string | null>(null);
const validateOk = ref(false);
const formError = ref<string | null>(null);

const form = ref({
  name: "",
  description: "",
  json: "",
});

const emptyRender = () => h(NEmpty, { description: "暂无配置" });

const loadConfigs = async () => {
  loading.value = true;
  try {
    configs.value = await api.configs();
  } catch {
    msg.error("加载失败");
  } finally {
    loading.value = false;
  }
};

const parseJson = () => {
  try {
    const body = JSON.parse(form.value.json || "{}");
    return body;
  } catch (err: any) {
    formError.value = err.message || "JSON 解析失败";
    return null;
  }
};

const validateConfig = async () => {
  try {
    formError.value = null;
    if (!form.value.name) {
      formError.value = "名称必填";
      return;
    }
    if (!form.value.json) {
      formError.value = "配置 JSON 必填";
      return;
    }
    const body = parseJson();
    if (!body) return;
    const res = await api.validateConfig(body);
    validateOk.value = res.ok;
    validateMsg.value = res.detail || (res.ok ? "有效" : "无效");
  } catch (err: any) {
    validateOk.value = false;
    validateMsg.value = err.message || "校验失败";
  }
};

const saveConfig = async () => {
  formError.value = null;
  if (!form.value.name) {
    formError.value = "名称必填";
    return;
  }
  if (!form.value.json) {
    formError.value = "配置 JSON 必填";
    return;
  }
  const body = parseJson();
  if (!body) return;
  saving.value = true;
  try {
    await api.createConfig({ name: form.value.name, description: form.value.description, config: body });
    msg.success("已创建");
    showCreate.value = false;
    validateMsg.value = null;
    await loadConfigs();
  } catch (err: any) {
    msg.error(err?.response?.data?.detail || err.message || "保存失败");
  } finally {
    saving.value = false;
  }
};

const handleDelete = async (row: any) => {
  await api.deleteConfig(row.id);
  msg.success("已删除");
  await loadConfigs();
};

const openCreate = () => {
  form.value = { name: "", description: "", json: "" };
  validateMsg.value = null;
  validateOk.value = false;
  formError.value = null;
  showCreate.value = true;
};

const columns = [
  { title: "名称", key: "name" },
  { title: "描述", key: "description" },
  { title: "更新时间", key: "updated_at" },
  {
    title: "操作",
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
              { default: () => "删除" },
            ),
          ],
        },
      );
    },
  },
];

onMounted(loadConfigs);
</script>
