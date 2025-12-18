<template>
  <div class="login-container">
    <div class="login-card">
      <div class="login-header">
        <h1>GraphMemory WebUI</h1>
        <p>图谱记忆可视化管理界面</p>
      </div>

      <form @submit.prevent="handleLogin" class="login-form">
        <div class="form-group">
          <label for="key">访问密钥</label>
          <input
            id="key"
            v-model="key"
            type="password"
            class="input"
            placeholder="请输入访问密钥"
            required
          />
        </div>

        <div v-if="error" class="error-message">
          {{ error }}
        </div>

        <button type="submit" class="btn btn-primary btn-block" :disabled="loading">
          {{ loading ? '验证中...' : '登录' }}
        </button>
      </form>

      <div class="login-footer">
        <p>提示: 访问密钥在插件启动日志中</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { statsApi } from '@/api/stats'

const router = useRouter()
const key = ref('')
const error = ref('')
const loading = ref(false)

const handleLogin = async () => {
  if (!key.value.trim()) {
    error.value = '请输入访问密钥'
    return
  }

  loading.value = true
  error.value = ''

  try {
    // 保存密钥
    localStorage.setItem('webui_key', key.value)

    // 验证密钥
    await statsApi.getOverview()

    // 验证成功，跳转到主页
    router.push('/')
  } catch (err: any) {
    // 验证失败
    localStorage.removeItem('webui_key')
    error.value = '访问密钥无效'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-container {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--color-bg-secondary);
  padding: 24px;
}

.login-card {
  width: 100%;
  max-width: 400px;
  background: var(--color-bg-primary);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  padding: 48px 32px;
  box-shadow: var(--shadow-lg);
}

.login-header {
  text-align: center;
  margin-bottom: 32px;
}

.login-header h1 {
  font-size: 28px;
  font-weight: 600;
  color: var(--color-text-primary);
  margin-bottom: 8px;
}

.login-header p {
  font-size: 14px;
  color: var(--color-text-secondary);
}

.login-form {
  margin-bottom: 24px;
}

.form-group {
  margin-bottom: 20px;
}

.form-group label {
  display: block;
  font-size: 14px;
  font-weight: 500;
  color: var(--color-text-primary);
  margin-bottom: 8px;
}

.error-message {
  padding: 12px;
  background: rgba(220, 53, 69, 0.1);
  border: 1px solid var(--color-error);
  border-radius: var(--radius-sm);
  color: var(--color-error);
  font-size: 14px;
  margin-bottom: 20px;
}

.btn-block {
  width: 100%;
  padding: 12px;
  font-size: 16px;
}

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.login-footer {
  text-align: center;
  padding-top: 24px;
  border-top: 1px solid var(--color-border);
}

.login-footer p {
  font-size: 13px;
  color: var(--color-text-tertiary);
}
</style>
