import { defineStore } from "pinia";
import { ref } from "vue";

export type ThemeMode = "light" | "dark" | "system";
export type Language = "zh" | "en";

export const useUiStore = defineStore("ui", () => {
  const theme = ref<ThemeMode>("system");
  const language = ref<Language>("zh");

  const setTheme = (t: ThemeMode) => {
    theme.value = t;
  };
  const setLanguage = (l: Language) => {
    language.value = l;
  };

  return { theme, language, setTheme, setLanguage };
});
