<template>
  <div class="system-view">
    <div class="view-header">
      <h2>系统管理</h2>
    </div>

    <div class="view-content">
      <!-- 系统状态 -->
      <div class="card">
        <h3>系统状态</h3>
        <div v-if="status" class="status-grid">
          <div class="status-item">
            <span class="label">版本:</span>
            <span class="value">{{ status.version }}</span>
          </div>
          <div class="status-item">
            <span class="label">Embedding Provider:</span>
            <span class="value">{{ status.embedding_provider || '未配置' }}</span>
          </div>
          <div class="status-item">
            <span class="label">LLM Provider:</span>
            <span class="value">{{ status.llm_provider || '未配置' }}</span>
          </div>
          <div class="status-item">
            <span class="label">实体总数:</span>
            <span class="value">{{ status.total_entities }}</span>
          </div>
          <div class="status-item">
            <span class="label">关系总数:</span>
            <span class="value">{{ status.total_relations }}</span>
          </div>
          <div class="status-item">
            <span class="label">会话数:</span>
            <span class="value">{{ status.total_sessions }}</span>
          </div>
        </div>
        <button @click="loadStatus" class="btn" style="margin-top: 16px">
          刷新状态
        </button>
      </div>

      <!-- 导入导出 -->
      <div class="card">
        <h3>导入导出</h3>

        <div class="section">
          <h4>导出图谱</h4>
          <div class="form-row">
            <input
              v-model="exportPersonaId"
              type="text"
              class="input"
              placeholder="人格ID（留空导出全部）"
            />
            <button @click="handleExport" class="btn" :disabled="exporting">
              {{ exporting ? '导出中...' : '导出' }}
            </button>
          </div>
          <p v-if="exportResult" class="result-text">
            {{ exportResult }}
          </p>
        </div>

        <div class="section">
          <h4>导入图谱</h4>
          <div class="form-group">
            <label>
              <input type="checkbox" v-model="importMerge" />
              合并模式（保留现有数据）
            </label>
          </div>
          <textarea
            v-model="importContent"
            class="textarea"
            placeholder="粘贴 JSON 数据..."
            rows="8"
          ></textarea>
          <button @click="handleImport" class="btn btn-primary" :disabled="importing || !importContent">
            {{ importing ? '导入中...' : '导入' }}
          </button>
          <p v-if="importResult" class="result-text">
            {{ importResult }}
          </p>
        </div>
      </div>

      <!-- 图谱清理 -->
      <div class="card">
        <h3>图谱清理</h3>

        <div class="section">
          <h4>清理低重要性实体</h4>
          <div class="form-row">
            <input
              v-model.number="pruneThreshold"
              type="number"
              class="input"
              placeholder="重要性阈值"
              min="0"
              max="1"
              step="0.1"
            />
            <button @click="handlePrune" class="btn btn-danger" :disabled="cleaning">
              {{ cleaning ? '清理中...' : '清理' }}
            </button>
          </div>
          <p class="hint">将删除重要性低于阈值的实体</p>
        </div>

        <div class="section">
          <h4>应用时间衰减</h4>
          <div class="form-row">
            <input
              v-model.number="decayRate"
              type="number"
              class="input"
              placeholder="衰减率"
              min="0"
              max="1"
              step="0.05"
            />
            <button @click="handleDecay" class="btn" :disabled="cleaning">
              {{ cleaning ? '应用中...' : '应用' }}
            </button>
          </div>
          <p class="hint">对所有实体和关系应用时间衰减</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { systemApi } from '@/api/system'

const status = ref<any>(null)
const exportPersonaId = ref('')
const exporting = ref(false)
const exportResult = ref('')

const importContent = ref('')
const importMerge = ref(true)
const importing = ref(false)
const importResult = ref('')

const pruneThreshold = ref(0.1)
const decayRate = ref(0.95)
const cleaning = ref(false)

const loadStatus = async () => {
  try {
    const response = await systemApi.getStatus()
    if (response.success) {
      status.value = response.data
    }
  } catch (err) {
    console.error('Failed to load status:', err)
  }
}

const handleExport = async () => {
  exporting.value = true
  exportResult.value = ''

  try {
    const params: any = {}
    if (exportPersonaId.value) {
      params.persona_id = exportPersonaId.value
    }

    const response = await systemApi.export(params)

    if (response.success) {
      // 下载文件
      const blob = new Blob([response.data.content], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `graphmemory_export_${Date.now()}.json`
      a.click()
      URL.revokeObjectURL(url)

      exportResult.value = `导出成功: ${response.data.entity_count} 个实体, ${response.data.relation_count} 条关系`
    } else {
      exportResult.value = '导出失败: ' + response.message
    }
  } catch (err: any) {
    exportResult.value = '导出失败'
    console.error(err)
  } finally {
    exporting.value = false
  }
}

const handleImport = async () => {
  if (!importContent.value.trim()) {
    alert('请输入 JSON 数据')
    return
  }

  if (!confirm('确定要导入图谱数据吗？')) {
    return
  }

  importing.value = true
  importResult.value = ''

  try {
    const response = await systemApi.import({
      content: importContent.value,
      merge: importMerge.value,
    })

    if (response.success) {
      importResult.value = `导入成功: ${response.data.imported_entities} 个实体, ${response.data.imported_relations} 条关系`
      importContent.value = ''
      loadStatus()
    } else {
      importResult.value = '导入失败: ' + response.message
    }
  } catch (err: any) {
    importResult.value = '导入失败'
    console.error(err)
  } finally {
    importing.value = false
  }
}

const handlePrune = async () => {
  if (!confirm(`确定要清理重要性低于 ${pruneThreshold.value} 的实体吗？`)) {
    return
  }

  cleaning.value = true

  try {
    const response = await systemApi.cleanup({
      action: 'prune_low_importance',
      threshold: pruneThreshold.value,
    })

    if (response.success) {
      alert(response.message)
      loadStatus()
    } else {
      alert('清理失败: ' + response.message)
    }
  } catch (err: any) {
    alert('清理失败')
    console.error(err)
  } finally {
    cleaning.value = false
  }
}

const handleDecay = async () => {
  if (!confirm(`确定要应用 ${decayRate.value} 的时间衰减吗？`)) {
    return
  }

  cleaning.value = true

  try {
    const response = await systemApi.cleanup({
      action: 'apply_decay',
      threshold: decayRate.value,
    })

    if (response.success) {
      alert(response.message)
      loadStatus()
    } else {
      alert('应用失败: ' + response.message)
    }
  } catch (err: any) {
    alert('应用失败')
    console.error(err)
  } finally {
    cleaning.value = false
  }
}

onMounted(() => {
  loadStatus()
})
</script>

<style scoped>
.system-view {
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
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.card h3 {
  font-size: 18px;
  font-weight: 600;
  color: var(--color-text-primary);
  margin-bottom: 20px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--color-border);
}

.status-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 16px;
}

.status-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.status-item .label {
  font-size: 12px;
  font-weight: 500;
  color: var(--color-text-tertiary);
}

.status-item .value {
  font-size: 16px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.section {
  margin-bottom: 24px;
}

.section:last-child {
  margin-bottom: 0;
}

.section h4 {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text-secondary);
  margin-bottom: 12px;
}

.form-row {
  display: flex;
  gap: 12px;
  align-items: center;
}

.form-group {
  margin-bottom: 12px;
}

.form-group label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  color: var(--color-text-primary);
  cursor: pointer;
}

.form-group input[type="checkbox"] {
  width: 16px;
  height: 16px;
  cursor: pointer;
}

.textarea {
  width: 100%;
  padding: 12px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-bg-primary);
  color: var(--color-text-primary);
  font-family: 'Courier New', monospace;
  font-size: 13px;
  resize: vertical;
  margin-bottom: 12px;
}

.textarea:focus {
  outline: none;
  border-color: var(--color-accent);
}

.hint {
  font-size: 13px;
  color: var(--color-text-tertiary);
  margin-top: 8px;
}

.result-text {
  margin-top: 12px;
  padding: 12px;
  background: var(--color-bg-secondary);
  border-radius: var(--radius-sm);
  font-size: 13px;
  color: var(--color-text-primary);
}

.btn-danger {
  background: var(--color-error);
  color: white;
  border-color: var(--color-error);
}

.btn-danger:hover {
  background: #c82333;
  border-color: #bd2130;
}

.btn-primary {
  background: var(--color-accent);
  color: var(--color-bg-primary);
  border-color: var(--color-accent);
}

.btn-primary:hover {
  background: var(--color-accent-hover);
}
</style>
