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

  <NModal v-model:show="showCreate" preset="card" title="新建数据源" style="width: 640px;">
    <NSpace vertical>
      <NInput v-model:value="form.name" placeholder="名称（必填）" />
      <NInput v-model:value="form.type" placeholder="类型 local_csv/rest/websocket/adata（必填）" />
      <NInput v-model:value="form.path" placeholder="路径/URL (可选)" />
      <NInput v-model:value="form.symbol" placeholder="符号 (可选)" />
      <NInput v-model:value="form.description" placeholder="描述 (可选)" />
      <div v-if="formError" style="color: red;">{{ formError }}</div>
      <NButton type="primary" :loading="saving" @click="saveDataSource">{{ $t('save') }}</NButton>
    </NSpace>
  </NModal>
</template>

<script setup lang="ts">
import { h, onMounted, ref } from "vue";
import { NButton, NButtonGroup, NDataTable, NInput, NModal, NSpace, NTag, useMessage, NEmpty } from "naive-ui";
import { api } from "../modules/api";

const msg = useMessage();
const dataSources = ref<any[]>([]);
const loading = ref(false);
const showCreate = ref(false);
const saving = ref(false);
const formError = ref<string | null>(null);

const form = ref({
  name: "",
  type: "",
  path: "",
  symbol: "",
  description: "",
});

const emptyRender = () => h(NEmpty, { description: "暂无数据源" });

const loadDataSources = async () => {
  loading.value = true;
  try {
    dataSources.value = await api.dataSources();
  } catch {
    msg.error("加载失败");
  } finally {
    loading.value = false;
  }
};

const saveDataSource = async () => {
  formError.value = null;
  if (!form.value.name) {
    formError.value = "名称必填";
    return;
  }
  if (!form.value.type) {
    formError.value = "类型必填";
    return;
  }
  saving.value = true;
  try {
    await api.createDataSource(form.value);
    msg.success("已创建");
    showCreate.value = false;
    await loadDataSources();
  } catch (err: any) {
    msg.error(err?.response?.data?.detail || "保存失败");
  } finally {
    saving.value = false;
  }
};

const handleProbe = async (row: any) => {
  const res = await api.probeDataSource(row.id);
  msg.success(`探测结果: ${res.healthy ? "正常" : "异常"}`);
  await loadDataSources();
};

const columns = [
  { title: "名称", key: "name" },
  { title: "类型", key: "type" },
  { title: "路径", key: "path" },
  {
    title: "健康",
    key: "healthy",
    render(row: any) {
      return row.healthy === null || row.healthy === undefined ? "未知" : h(NTag, { type: row.healthy ? "success" : "error", size: "small" }, { default: () => (row.healthy ? "健康" : "异常") });
    },
  },
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
              { size: "small", onClick: () => handleProbe(row) },
              { default: () => "探测" },
            ),
          ],
        },
      );
    },
  },
];

onMounted(loadDataSources);

const openCreate = () => {
  form.value = { name: "", type: "", path: "", symbol: "", description: "" };
  formError.value = null;
  showCreate.value = true;
};
</script>
