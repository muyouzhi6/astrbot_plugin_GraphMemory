<template>
  <div class="search-view">
    <div class="view-header">
      <h2>搜索测试</h2>
    </div>

    <div class="view-content">
      <!-- 搜索表单 -->
      <div class="search-form card">
        <div class="form-group">
          <label>查询文本</label>
          <input
            v-model="query"
            type="text"
            class="input"
            placeholder="输入搜索关键词..."
            @keyup.enter="handleSearch"
          />
        </div>

        <div class="form-row">
          <div class="form-group">
            <label>搜索模式</label>
            <select v-model="searchMode" class="select">
              <option value="hybrid">混合搜索</option>
              <option value="vector">向量搜索</option>
              <option value="keyword">关键词搜索</option>
            </select>
          </div>

          <div class="form-group">
            <label>结果数量</label>
            <input
              v-model.number="topK"
              type="number"
              class="input"
              min="1"
              max="20"
            />
          </div>
        </div>

        <button
          @click="handleSearch"
          class="btn btn-primary"
          :disabled="loading || !query"
        >
          {{ loading ? '搜索中...' : '搜索' }}
        </button>
      </div>

      <!-- 搜索结果 -->
      <div v-if="searchResults" class="results-section">
        <h3>搜索结果 ({{ searchResults.results?.length || 0 }})</h3>

        <div v-if="loading" class="loading">搜索中...</div>
        <div v-else-if="error" class="error">{{ error }}</div>
        <div v-else-if="searchResults.results?.length === 0" class="empty">
          未找到匹配结果
        </div>
        <div v-else class="results-list">
          <div
            v-for="(result, index) in searchResults.results"
            :key="index"
            class="result-item card"
          >
            <div class="result-header">
              <h4>{{ result.entity.name }}</h4>
              <span class="type-badge" :class="`type-${result.entity.type.toLowerCase()}`">
                {{ result.entity.type }}
              </span>
            </div>

            <p class="result-description">{{ result.entity.description }}</p>

            <div class="result-meta">
              <span v-if="result.score !== undefined" class="meta-item">
                分数: {{ result.score.toFixed(3) }}
              </span>
              <span v-if="result.similarity !== undefined" class="meta-item">
                相似度: {{ result.similarity.toFixed(3) }}
              </span>
              <span v-if="result.match_type" class="meta-item">
                匹配类型: {{ result.match_type }}
              </span>
              <span class="meta-item">
                重要性: {{ result.entity.importance.toFixed(2) }}
              </span>
            </div>
          </div>
        </div>

        <!-- 格式化文本 -->
        <div v-if="searchResults.formatted_text" class="formatted-text card">
          <h4>格式化记忆文本</h4>
          <pre>{{ searchResults.formatted_text }}</pre>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { searchApi } from '@/api/search'

const query = ref('')
const searchMode = ref('hybrid')
const topK = ref(7)
const loading = ref(false)
const error = ref('')
const searchResults = ref<any>(null)

const handleSearch = async () => {
  if (!query.value.trim()) {
    return
  }

  loading.value = true
  error.value = ''

  try {
    const params = {
      query: query.value,
      top_k: topK.value,
    }

    let response
    if (searchMode.value === 'hybrid') {
      response = await searchApi.hybrid(params)
    } else if (searchMode.value === 'vector') {
      response = await searchApi.vector(params)
    } else {
      response = await searchApi.keyword(params)
    }

    if (response.success) {
      searchResults.value = response.data
    } else {
      error.value = response.message || '搜索失败'
    }
  } catch (err: any) {
    error.value = err.response?.data?.message || '搜索失败'
    console.error(err)
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.search-view {
  padding: 24px;
  height: 100%;
  overflow: auto;
}

.view-header {
  margin-bottom: 24px;
}

.view-header h2 {
  font-size: 24px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.view-content {
  max-width: 1000px;
}

.search-form {
  margin-bottom: 32px;
}

.form-group {
  margin-bottom: 16px;
}

.form-group label {
  display: block;
  font-size: 14px;
  font-weight: 500;
  color: var(--color-text-primary);
  margin-bottom: 8px;
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.select {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-bg-primary);
  color: var(--color-text-primary);
  font-size: 14px;
}

.results-section {
  margin-top: 32px;
}

.results-section h3 {
  font-size: 18px;
  font-weight: 600;
  color: var(--color-text-primary);
  margin-bottom: 16px;
}

.results-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin-bottom: 24px;
}

.result-item {
  padding: 20px;
}

.result-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.result-header h4 {
  font-size: 16px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.type-badge {
  display: inline-block;
  padding: 4px 8px;
  border-radius: var(--radius-sm);
  font-size: 12px;
  font-weight: 500;
}

.type-person { background: #dbeafe; color: #1e40af; }
.type-place { background: #d1fae5; color: #065f46; }
.type-thing { background: #fef3c7; color: #92400e; }
.type-concept { background: #e9d5ff; color: #6b21a8; }
.type-event { background: #fee2e2; color: #991b1b; }

[data-theme="dark"] .type-person { background: #1e3a8a; color: #bfdbfe; }
[data-theme="dark"] .type-place { background: #064e3b; color: #a7f3d0; }
[data-theme="dark"] .type-thing { background: #78350f; color: #fde68a; }
[data-theme="dark"] .type-concept { background: #581c87; color: #e9d5ff; }
[data-theme="dark"] .type-event { background: #7f1d1d; color: #fecaca; }

.result-description {
  font-size: 14px;
  color: var(--color-text-secondary);
  margin-bottom: 12px;
  line-height: 1.5;
}

.result-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
}

.meta-item {
  font-size: 13px;
  color: var(--color-text-tertiary);
}

.formatted-text {
  padding: 20px;
}

.formatted-text h4 {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text-secondary);
  margin-bottom: 12px;
  text-transform: uppercase;
}

.formatted-text pre {
  font-family: 'Courier New', monospace;
  font-size: 13px;
  line-height: 1.6;
  color: var(--color-text-primary);
  white-space: pre-wrap;
  word-wrap: break-word;
}

.loading,
.error,
.empty {
  padding: 48px;
  text-align: center;
  color: var(--color-text-secondary);
}

.error {
  color: var(--color-error);
}
</style>
