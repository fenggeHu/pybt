import { defineStore } from "pinia";
import { ref } from "vue";
import { api } from "../modules/api";

export interface User {
  username: string;
  role: string;
}

const TOKEN_KEY = "pybt_token";

export const useAuthStore = defineStore("auth", () => {
  const token = ref<string | null>(localStorage.getItem(TOKEN_KEY));
  const user = ref<User | null>(null);

  const setToken = (t: string | null) => {
    token.value = t;
    if (t) {
      localStorage.setItem(TOKEN_KEY, t);
    } else {
      localStorage.removeItem(TOKEN_KEY);
    }
  };

  const login = async (username: string, password: string) => {
    const res = await api.login({ username, password });
    setToken(res.access_token);
    user.value = res.user;
  };

  const register = async (username: string, password: string) => {
    const res = await api.register({ username, password });
    setToken(res.access_token);
    user.value = res.user;
  };

  const fetchMe = async () => {
    if (!token.value) return;
    try {
      const me = await api.me();
      user.value = me;
    } catch {
      logout();
    }
  };

  const logout = () => {
    setToken(null);
    user.value = null;
  };

  return { token, user, login, register, fetchMe, logout };
});
