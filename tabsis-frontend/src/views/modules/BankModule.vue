<!-- @ts-nocheck -->
<template>
  <div class="bank-module">
    <div class="module-header">
      <h2>银行流水分析 (Bank Statement Analysis)</h2>
      <div class="actions">
        <a-upload
          :customRequest="handleUpload"
          :showUploadList="false"
          accept=".pdf"
        >
          <a-button type="primary" :loading="uploading">
            <template #icon>📤</template>
            上传流水 PDF
          </a-button>
        </a-upload>
      </div>
    </div>

    <div v-if="analysisData" class="analysis-content">
      <!-- Summary Cards -->
      <div class="summary-cards">
        <div class="card">
          <div class="label">公司</div>
          <div class="value">{{ analysisData.company || '未知' }}</div>
        </div>
        <div class="card">
          <div class="label">银行</div>
          <div class="value">{{ analysisData.bank || '未知' }}</div>
        </div>
        <div class="card">
          <div class="label">期间</div>
          <div class="value">{{ analysisData.period || '未知' }}</div>
        </div>
        <div class="card">
          <div class="label">交易笔数</div>
          <div class="value">{{ analysisData.transaction_count }}</div>
        </div>
      </div>

      <!-- Validation Errors -->
      <div v-if="analysisData.validation_errors && analysisData.validation_errors.length > 0" class="error-alert">
        <h3>⚠️ 余额校验异常</h3>
        <ul>
          <li v-for="(err, idx) in analysisData.validation_errors" :key="idx">{{ err }}</li>
        </ul>
      </div>

      <!-- Data Table -->
      <div class="data-table-container">
        <h3>数据预览 (已存入 Doris: {{ analysisData.table_name }})</h3>
        <p class="hint">完整数据请通过 Agent 查询或下载 Excel</p>
      </div>
    </div>
    
    <div v-else class="empty-state">
      <div class="icon">🏦</div>
      <p>暂无数据。请上传银行对账单 PDF 文件。</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRoute } from 'vue-router'
import axios from 'axios'
import { message } from 'ant-design-vue'

const route = useRoute()
const uploading = ref(false)
const analysisData = ref<any | null>(null)

const API_BASE = (import.meta.env.VITE_API_BASE_URL || '/api').trim() || '/api'

const handleUpload = async (options: any) => {
  const { file } = options
  const formData = new FormData()
  formData.append('file', file)
  formData.append('project_id', route.params.projectId as string)
  formData.append('company_id', route.params.companyId as string)

  uploading.value = true
  try {
    const res = await axios.post(`${API_BASE}/modules/bank/upload`, formData)
    if (res.data.success) {
      message.success('上传并分析成功')
      analysisData.value = res.data
    }
  } catch (error) {
    message.error('上传失败: ' + error)
  } finally {
    uploading.value = false
  }
}
</script>

<style scoped>
.bank-module {
  padding: 20px;
  color: var(--text-primary);
}

.module-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 30px;
}

.module-header h2 {
  color: var(--neon-purple);
  margin: 0;
  font-family: 'Orbitron', sans-serif;
}

.empty-state {
  text-align: center;
  padding: 100px;
  background: var(--glass-bg);
  border-radius: 16px;
  border: 1px dashed var(--border-color);
}

.empty-state .icon {
  font-size: 60px;
  margin-bottom: 20px;
  color: var(--text-secondary);
}

.analysis-content {
  background: var(--sidebar-bg);
  padding: 20px;
  border-radius: 16px;
  border: 1px solid var(--border-color);
}

.summary-cards {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 20px;
  margin-bottom: 30px;
}

.card {
  background: var(--glass-bg);
  padding: 15px;
  border-radius: 8px;
  border: 1px solid var(--border-color);
  transition: all 0.3s;
}

.card:hover {
  border-color: var(--neon-purple);
  transform: translateY(-2px);
  background: var(--card-hover-bg);
}

.card .label {
  color: var(--text-secondary);
  font-size: 12px;
  margin-bottom: 5px;
}

.card .value {
  color: var(--text-primary);
  font-size: 18px;
  font-weight: bold;
}

.error-alert {
  background: rgba(255, 0, 0, 0.1);
  border: 1px solid #ff4d4f;
  padding: 15px;
  border-radius: 8px;
  margin-bottom: 20px;
  color: #ff4d4f;
}

.error-alert h3 {
  color: #ff4d4f;
  margin-top: 0;
}

.hint {
  color: var(--text-secondary);
  font-style: italic;
}
</style>
