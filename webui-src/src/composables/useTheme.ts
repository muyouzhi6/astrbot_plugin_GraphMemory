import { ref, watch, onMounted } from 'vue'

export type Theme = 'light' | 'dark'

const THEME_KEY = 'graphmemory-theme'

export function useTheme() {
  const theme = ref<Theme>('light')

  // 初始化主题
  const initTheme = () => {
    const saved = localStorage.getItem(THEME_KEY) as Theme | null
    if (saved) {
      theme.value = saved
    } else {
      // 检测系统主题
      const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches
      theme.value = prefersDark ? 'dark' : 'light'
    }
    applyTheme(theme.value)
  }

  // 应用主题
  const applyTheme = (newTheme: Theme) => {
    document.documentElement.setAttribute('data-theme', newTheme)
  }

  // 切换主题
  const toggleTheme = () => {
    theme.value = theme.value === 'light' ? 'dark' : 'light'
  }

  // 设置主题
  const setTheme = (newTheme: Theme) => {
    theme.value = newTheme
  }

  // 监听主题变化
  watch(theme, (newTheme) => {
    applyTheme(newTheme)
    localStorage.setItem(THEME_KEY, newTheme)
  })

  onMounted(() => {
    initTheme()
  })

  return {
    theme,
    toggleTheme,
    setTheme,
  }
}
