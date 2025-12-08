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

  <NModal v-model:show="showCreate" preset="card" title="新建任务" style="width: 720px;">
    <NSpace vertical>
      <NInput v-model:value="form.name" placeholder="名称（必填）" />
      <NInput v-model:value="form.config_id" placeholder="配置ID (可选，填此则忽略下方JSON)" />
      <NInput type="textarea" rows="8" v-model:value="form.json" placeholder="直接粘贴配置 JSON (可选)" />
      <div v-if="formError" style="color: red;">{{ formError }}</div>
      <NButton type="primary" :loading="saving" @click="createRun">{{ $t('run') }}</NButton>
    </NSpace>
  </NModal>
</template>

<script setup lang="ts">
import { h, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { NButton, NButtonGroup, NDataTable, NInput, NModal, NSpace, NTag, useMessage, NEmpty } from "naive-ui";
import { api } from "../modules/api";

const router = useRouter();
const msg = useMessage();
const runs = ref<any[]>([]);
const loading = ref(false);
const showCreate = ref(false);
const saving = ref(false);
const formError = ref<string | null>(null);

const form = ref({
  name: "",
  config_id: "",
  json: "",
});

const emptyRender = () => h(NEmpty, { description: "暂无任务" });

const loadRuns = async () => {
  loading.value = true;
  try {
    runs.value = await api.runs();
  } catch {
    msg.error("加载失败");
  } finally {
    loading.value = false;
  }
};

const createRun = async () => {
  formError.value = null;
  if (!form.value.name) {
    formError.value = "名称必填";
    return;
  }
  saving.value = true;
  try {
    const body: any = { name: form.value.name };
    if (form.value.config_id) body.config_id = form.value.config_id;
    if (form.value.json) body.config = JSON.parse(form.value.json);
    const run = await api.createRun(body);
    msg.success("已创建");
    showCreate.value = false;
    await loadRuns();
    router.push(`/runs/${run.id}`);
  } catch (err: any) {
    msg.error(err?.response?.data?.detail || "创建失败");
  } finally {
    saving.value = false;
  }
};

const handleCancel = async (row: any) => {
  await api.cancelRun(row.id);
  msg.success("已取消");
  await loadRuns();
};

const columns = [
  { title: "名称", key: "name" },
  { title: "状态", key: "status", render: (row: any) => h(NTag, { type: row.status === "succeeded" ? "success" : row.status === "failed" ? "error" : "info", size: "small" }, { default: () => row.status }) },
  { title: "进度", key: "progress", render: (row: any) => `${Math.round((row.progress || 0) * 100)}%` },
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
              { size: "small", onClick: () => router.push(`/runs/${row.id}`) },
              { default: () => "详情" },
            ),
            h(
              NButton,
              { size: "small", onClick: () => handleCancel(row) },
              { default: () => "取消" },
            ),
          ],
        },
      );
    },
  },
];

onMounted(loadRuns);

const openCreate = () => {
  form.value = { name: "", config_id: "", json: "" };
  formError.value = null;
  showCreate.value = true;
};
</script>
