<template>
  <div class="card" v-if="run">
    <div style="display: flex; justify-content: space-between; align-items: center;">
      <div>
        <h3 style="margin: 0;">任务 {{ run.name }}</h3>
        <div class="small">{{ run.id }}</div>
      </div>
      <n-space>
        <n-tag type="info">{{ run.status }}</n-tag>
        <n-button size="small" @click="loadRun">{{ $t('retry') }}</n-button>
      </n-space>
    </div>
    <div style="margin-top: 12px;">
      进度：{{ Math.round((run.progress || 0) * 100) }}%
    </div>
    <div style="margin-top: 8px;">消息：{{ run.message || "-" }}</div>
    <div style="margin-top: 8px;">连接：{{ streamStatus }}</div>
    <div style="margin-top: 12px;">
      <n-button size="small" @click="cancelRun" :disabled="canceling">{{ $t('cancel') }}</n-button>
    </div>
    <div style="margin-top: 16px;">
      <h4>事件</h4>
      <n-list bordered>
        <n-list-item v-for="(evt, idx) in events" :key="idx">
          <div class="small">{{ evt }}</div>
        </n-list-item>
      </n-list>
    </div>
  </div>
  <div v-else class="card">未找到任务</div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from "vue";
import { useRoute } from "vue-router";
import { NButton, NList, NListItem, NSpace, NTag, useMessage } from "naive-ui";
import { api } from "../modules/api";
import { connectSSE, connectWS } from "../modules/runStream";
import { useAuthStore } from "../stores/auth";

const route = useRoute();
const runId = route.params.id as string;
const msg = useMessage();
const auth = useAuthStore();

const run = ref<any>(null);
const events = ref<string[]>([]);
const canceling = ref(false);
const streamStatus = ref("connecting...");

let sse: EventSource | null = null;
let ws: WebSocket | null = null;

const loadRun = async () => {
  try {
    run.value = await api.runs().then((list) => list.find((r: any) => r.id === runId));
  } catch {
    msg.error("加载失败");
  }
};

const startStream = () => {
  if (!auth.token) return;
  streamStatus.value = "connecting...";
  sse = connectSSE(runId, auth.token, (evt) => handleEvent(evt));
  ws = connectWS(runId, auth.token, (evt) => handleEvent(evt));
  streamStatus.value = "connected";
};

const handleEvent = (evt: any) => {
  events.value.unshift(JSON.stringify(evt));
  if (evt.run) {
    run.value = evt.run;
  }
  if (evt.error) {
    streamStatus.value = `error: ${evt.error}`;
  }
};

const cancelRun = async () => {
  canceling.value = true;
  try {
    await api.cancelRun(runId);
    msg.success("已取消");
    await loadRun();
  } catch {
    msg.error("取消失败");
  } finally {
    canceling.value = false;
  }
};

onMounted(async () => {
  await loadRun();
  startStream();
});

onBeforeUnmount(() => {
  sse?.close();
  ws?.close();
});
</script>
