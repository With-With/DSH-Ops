import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

const STORAGE_KEY = 'dsh-ops-theme'

export const useThemeStore = defineStore('theme', () => {
  // ---- state
  const savedMode = localStorage.getItem(STORAGE_KEY)
  const mode = ref(savedMode || 'light')

  // ---- actions ----
  function applyTheme(newMode) {
    const html = document.documentElement
    if (newMode === 'dark') {
      html.classList.add('dark')
    } else {
      html.classList.remove('dark')
    }
  }

  function toggle() {
    mode.value = mode.value === 'dark' ? 'light' : 'dark'
  }

  function setTheme(newMode) {
    mode.value = newMode
  }

  // ---- effect: 持久化 + 切换 html class
  watch(
    mode,
    (newMode) => {
      applyTheme(newMode)
      localStorage.setItem(STORAGE_KEY, newMode)
    },
    { immediate: true }
  )

  return {
    mode,
    toggle,
    setTheme,
  }
})
