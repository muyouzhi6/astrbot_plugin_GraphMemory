<template>
  <div class="graph-view">
    <div class="view-header">
      <h2>图谱可视化</h2>
      <div class="view-actions">
        <select v-model="viewMode" class="select" @change="loadGraph">
          <option value="global">全局视图</option>
          <option value="session">会话视图</option>
        </select>
        <input
          v-if="viewMode === 'session'"
          v-model="sessionId"
          type="text"
          class="input"
          placeholder="会话 ID"
          style="width: 200px"
        />
        <button @click="loadGraph" class="btn" :disabled="loading">
          {{ loading ? '加载中...' : '刷新' }}
        </button>
      </div>
    </div>

    <div class="graph-container">
      <div v-if="loading" class="loading">
        <div class="spinner"></div>
        <p>加载图谱数据...</p>
      </div>
      <div v-else-if="error" class="error">
        <p>{{ error }}</p>
        <button @click="loadGraph" class="btn">重试</button>
      </div>
      <GraphViewer
        v-else-if="graphData.nodes.length > 0"
        :nodes="graphData.nodes"
        :edges="graphData.edges"
      />
      <div v-else class="empty">
        <p>暂无图谱数据</p>
        <p class="text-secondary">请先进行对话以生成记忆</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { graphApi } from '@/api/graph'
import GraphViewer from '@/components/GraphViewer.vue'

const loading = ref(false)
const error = ref('')
const viewMode = ref('global')
const sessionId = ref('')
const graphData = ref<{ nodes: any[]; edges: any[] }>({
  nodes: [],
  edges: [],
})

const loadGraph = async () => {
  loading.value = true
  error.value = ''

  try {
    let response

    if (viewMode.value === 'session' && sessionId.value) {
      response = await graphApi.getSessionGraph(sessionId.value)
    } else {
      response = await graphApi.getGlobalGraph({ limit: 200 })
    }

    if (response.success) {
      graphData.value = response.data
    } else {
      error.value = response.message || '加载失败'
    }
  } catch (err: any) {
    error.value = err.response?.data?.message || '加载图谱失败'
    console.error(err)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadGraph()
})
</script>

<style scoped>
.graph-view {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.view-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 24px;
  border-bottom: 1px solid var(--color-border);
  background: var(--color-bg-primary);
}

.view-header h2 {
  font-size: 24px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.view-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.select {
  padding: 8px 12px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-bg-primary);
  color: var(--color-text-primary);
  font-size: 14px;
  cursor: pointer;
  transition: var(--transition);
}

.select:focus {
  outline: none;
  border-color: var(--color-accent);
}

.graph-container {
  flex: 1;
  position: relative;
  overflow: hidden;
}

.loading,
.error,
.empty {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  text-align: center;
}

.loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
}

.spinner {
  width: 40px;
  height: 40px;
  border: 3px solid var(--color-border);
  border-top-color: var(--color-accent);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.loading p {
  font-size: 14px;
  color: var(--color-text-secondary);
}

.error {
  color: var(--color-error);
}

.error p {
  margin-bottom: 16px;
}

.empty p {
  font-size: 16px;
  color: var(--color-text-primary);
  margin-bottom: 8px;
}

.text-secondary {
  font-size: 14px;
  color: var(--color-text-secondary);
}
</style>
