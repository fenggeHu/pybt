import axios from "axios";
import { createDiscreteApi } from "naive-ui";
import { useAuthStore } from "../stores/auth";

export const API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000/api";

export const apiInstance = axios.create({
  baseURL: API_BASE,
  timeout: 15000,
});

const { message } = createDiscreteApi(["message"]);

apiInstance.interceptors.request.use((config) => {
  const auth = useAuthStore();
  if (auth.token) {
    config.headers = config.headers || {};
    config.headers.Authorization = `Bearer ${auth.token}`;
  }
  return config;
});

apiInstance.interceptors.response.use(
  (resp) => resp,
  (error) => {
    const status = error?.response?.status;
    if (status === 401) {
      const auth = useAuthStore();
      auth.logout();
      message.error("认证过期，请重新登录");
    } else {
      message.error(error?.response?.data?.detail || error.message || "请求失败");
    }
    return Promise.reject(error);
  },
);

export const api = {
  async login(payload: { username: string; password: string }) {
    const { data } = await apiInstance.post("/auth/login", payload);
    return data;
  },
  async me() {
    const { data } = await apiInstance.get("/auth/me");
    return data;
  },
  async configs() {
    const { data } = await apiInstance.get("/configs");
    return data;
  },
  async createConfig(body: any) {
    const { data } = await apiInstance.post("/configs", body);
    return data;
  },
  async validateConfig(config: any) {
    const { data } = await apiInstance.post("/configs/validate", { config });
    return data;
  },
  async deleteConfig(id: string) {
    const { data } = await apiInstance.delete(`/configs/${id}`);
    return data;
  },
  async dataSources() {
    const { data } = await apiInstance.get("/data-sources");
    return data;
  },
  async createDataSource(body: any) {
    const { data } = await apiInstance.post("/data-sources", body);
    return data;
  },
  async probeDataSource(id: string) {
    const { data } = await apiInstance.post(`/data-sources/${id}/probe`);
    return data;
  },
  async runs() {
    const { data } = await apiInstance.get("/runs");
    return data;
  },
  async createRun(body: any) {
    const { data } = await apiInstance.post("/runs", body);
    return data;
  },
  async cancelRun(id: string) {
    const { data } = await apiInstance.post(`/runs/${id}/cancel`);
    return data;
  },
  async definitions() {
    const { data } = await apiInstance.get("/definitions");
    return data;
  },
  async audit() {
    const { data } = await apiInstance.get("/audit");
    return data;
  },
};
