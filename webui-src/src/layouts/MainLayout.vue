<template>
  <div class="main-layout">
    <!-- 顶部导航栏 -->
    <header class="header">
      <div class="header-left">
        <h1 class="logo">GraphMemory</h1>
      </div>

      <nav class="nav">
        <router-link to="/graph" class="nav-link">图谱</router-link>
        <router-link to="/entities" class="nav-link">实体</router-link>
        <router-link to="/relations" class="nav-link">关系</router-link>
        <router-link to="/search" class="nav-link">搜索</router-link>
        <router-link to="/stats" class="nav-link">统计</router-link>
        <router-link to="/system" class="nav-link">系统</router-link>
      </nav>

      <div class="header-right">
        <button @click="toggleTheme" class="btn btn-icon" title="切换主题">
          <span v-if="theme === 'light'">🌙</span>
          <span v-else>☀️</span>
        </button>
        <button @click="handleLogout" class="btn" title="退出登录">
          退出
        </button>
      </div>
    </header>

    <!-- 主内容区 -->
    <main class="main-content">
      <router-view />
    </main>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useTheme } from '@/composables/useTheme'

const router = useRouter()
const { theme, toggleTheme } = useTheme()

const handleLogout = () => {
  localStorage.removeItem('webui_key')
  router.push('/login')
}
</script>

<style scoped>
.main-layout {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.header {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  background: var(--color-bg-primary);
  border-bottom: 1px solid var(--color-border);
}

.header-left {
  display: flex;
  align-items: center;
}

.logo {
  font-size: 20px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.nav {
  display: flex;
  gap: 8px;
}

.nav-link {
  padding: 8px 16px;
  border-radius: var(--radius-sm);
  color: var(--color-text-secondary);
  text-decoration: none;
  font-size: 14px;
  font-weight: 500;
  transition: var(--transition);
}

.nav-link:hover {
  background: var(--color-bg-hover);
  color: var(--color-text-primary);
}

.nav-link.router-link-active {
  background: var(--color-bg-tertiary);
  color: var(--color-text-primary);
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.btn-icon {
  width: 36px;
  height: 36px;
  padding: 0;
  font-size: 18px;
}

.main-content {
  flex: 1;
  overflow: auto;
}
</style>
