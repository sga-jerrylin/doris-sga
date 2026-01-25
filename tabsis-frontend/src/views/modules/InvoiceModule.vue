<template>
  <div class="invoice-module">
    <div class="module-header">
      <h2>发票分析 (Invoice Analysis)</h2>
      <div class="actions">
        <a-space>
          <a-button :disabled="!selectedInvoiceProjectId" @click="openExportModal">导出</a-button>
        </a-space>
      </div>
    </div>

    <div class="invoice-body">
    <div v-if="canShowUpload">
      <!-- 上传区域 -->
      <div class="upload-section">
        <div class="upload-grid">
          <a-card class="upload-card" title="销项 Excel (可批量上传)">
            <div class="upload-drop-zone">
              <a-upload-dragger
                v-model:file-list="salesFileList"
                accept=".xlsx,.xls"
                :multiple="true"
                :customRequest="handleUploadSales"
                :showUploadList="false"
              >
                <p class="ant-upload-drag-icon">
                  <span class="upload-icon">^</span>
                </p>
                <p class="ant-upload-text">点击或拖拽上传销项 Excel</p>
                <p class="ant-upload-hint">支持批量上传，上传后会自动解析并写入 Doris 写入状态</p>
              </a-upload-dragger>
            </div>
          </a-card>

          <a-card class="upload-card" title="进项 Excel (可批量上传)">
            <div class="upload-drop-zone">
              <a-upload-dragger
                v-model:file-list="purchaseFileList"
                accept=".xlsx,.xls"
                :multiple="true"
                :customRequest="handleUploadPurchase"
                :showUploadList="false"
              >
                <p class="ant-upload-drag-icon">
                  <span class="upload-icon">^</span>
                </p>
                <p class="ant-upload-text">点击或拖拽上传进项 Excel</p>
                <p class="ant-upload-hint">支持批量上传，上传后会自动解析并写入 Doris 写入状态</p>
              </a-upload-dragger>
            </div>
          </a-card>
        </div>
      </div>

      <!-- 文件列表 -->
      <div class="file-list-section">
        <div class="file-list-grid">
          <a-card :title="`销项 Excel (${salesFileList.length}个文件)`" class="file-list-card">
            <template #extra>
              <a-space>
                <a-button @click="clearSalesList" :disabled="salesUploading">清空列表</a-button>
              </a-space>
            </template>

            <a-table
              :columns="fileListColumns"
              :data-source="salesFileListData"
              :pagination="false"
              size="small"
              :scroll="fileListScroll"
              :rowKey="(row: any) => row.uid || row.name"
              :locale="{ emptyText: '暂无上传文件' }"
            >
              <template #bodyCell="{ column, record }">
                <template v-if="column.key === 'status'">
                  <a-tag :color="getStatusColor(record.status)">
                    {{ formatUploadStatus(record.status) }}
                  </a-tag>
                </template>
                <template v-if="column.key === 'actions'">
                  <a-space>
                    <a-button type="link" size="small" @click="handlePreviewUploadFile(record)">删除</a-button>
                    <a-button type="link" size="small" @click="handlePreviewUploadFile(record)">重新上传</a-button>
                  </a-space>
                </template>
              </template>
            </a-table>
          </a-card>

          <a-card :title="`进项 Excel (${purchaseFileList.length}个文件)`" class="file-list-card">
            <template #extra>
              <a-space>
                <a-button @click="clearPurchaseList" :disabled="purchaseUploading">清空列表</a-button>
              </a-space>
            </template>

            <a-table
              :columns="fileListColumns"
              :data-source="purchaseFileListData"
              :pagination="false"
              size="small"
              :scroll="fileListScroll"
              :rowKey="(row: any) => row.uid || row.name"
              :locale="{ emptyText: '暂无上传文件' }"
            >
              <template #bodyCell="{ column, record }">
                <template v-if="column.key === 'status'">
                  <a-tag :color="getStatusColor(record.status)">
                    {{ formatUploadStatus(record.status) }}
                  </a-tag>
                </template>
                <template v-if="column.key === 'actions'">
                  <a-space>
                    <a-button type="link" size="small" @click="handlePreviewUploadFile(record)">删除</a-button>
                    <a-button type="link" size="small" @click="handlePreviewUploadFile(record)">重新上传</a-button>
                  </a-space>
                </template>
              </template>
            </a-table>
          </a-card>
        </div>
      </div>

      <!-- 分析结果展示 -->
      <div v-if="analysisData" class="analysis-section">
        <a-card title="发票分析结果">
          <template #extra>
            <a-space>
              <a-button @click="refreshAnalysis" :disabled="analysisRefreshing">刷新分析</a-button>
            </a-space>
          </template>

          <!-- 摘要卡片 -->
          <div class="summary-cards">
            <div class="card" v-for="s in analysisData.summary" :key="s.category">
              <div class="card-title">{{ s.category }}</div>
              <div class="card-metric">￥{{ formatNumber(s.total_amount) }}</div>
              <div class="card-sub">
                <span>有效发票: {{ s.count }}</span>
                <span>作废: {{ s.void_count }} | 红冲: {{ s.red_flush_count }}</span>
              </div>
            </div>
          </div>

          <!-- 分析表 Tabs -->
          <a-tabs v-model:activeKey="activeTab" type="card" class="analysis-tabs">
            <a-tab-pane key="sales_item" tab="表一 · 销项类别">
              <a-table
                :dataSource="analysisData.sales_by_item"
                :columns="salesItemColumns"
                :rowKey="(row: any) => row._key"
                :pagination="tablePagination"
                size="small"
                :loading="analysisLoading"
                :locale="{ emptyText: emptyTextSales }"
                :scroll="tableScroll"
              />
            </a-tab-pane>

            <a-tab-pane key="sales_buyer" tab="表二 · 销项客户">
              <a-table
                :dataSource="analysisData.sales_by_buyer"
                :columns="salesBuyerColumns"
                :rowKey="(row: any) => row._key"
                :pagination="tablePagination"
                size="small"
                :loading="analysisLoading"
                :locale="{ emptyText: emptyTextSales }"
                :scroll="tableScroll"
              />
            </a-tab-pane>

            <a-tab-pane key="purchase_item" tab="表三 · 进项类别">
              <a-table
                :dataSource="analysisData.purchase_by_item"
                :columns="purchaseItemColumns"
                :rowKey="(row: any) => row._key"
                :pagination="tablePagination"
                size="small"
                :loading="analysisLoading"
                :locale="{ emptyText: emptyTextPurchase }"
                :scroll="tableScroll"
              />
            </a-tab-pane>

            <a-tab-pane key="purchase_seller" tab="表四 · 进项供应商">
              <a-table
                :dataSource="analysisData.purchase_by_seller"
                :columns="purchaseSellerColumns"
                :rowKey="(row: any) => row._key"
                :pagination="tablePagination"
                size="small"
                :loading="analysisLoading"
                :locale="{ emptyText: emptyTextPurchase }"
                :scroll="tableScroll"
              />
            </a-tab-pane>

            <a-tab-pane key="match" tab="表五 · 进销匹配">
              <a-table
                :dataSource="analysisData.match_by_category"
                :columns="matchColumns"
                :rowKey="(row: any) => row._key"
                :pagination="tablePagination"
                size="small"
                :loading="analysisLoading"
                :locale="{ emptyText: emptyTextMatch }"
                :scroll="tableScroll"
              />
            </a-tab-pane>
          </a-tabs>

          <!-- AI 问答面板 -->
          <div class="qa-panel">
            <div class="qa-title">AI 问答（仅限本发票项目7张表）</div>
            <a-space>
              <a-input
                v-model:value="question"
                style="width: 520px"
                placeholder="例如：表五中进销数量差异最大的前10个大类？"
                @keyup.enter="askQuestion"
              />
              <a-button type="primary" :loading="asking" @click="askQuestion">提问</a-button>
            </a-space>
            <div v-if="qaSql" class="qa-sql">SQL: {{ qaSql }}</div>
            <a-table
              v-if="qaRows && qaRows.length"
              :dataSource="qaRows"
              :columns="qaColumns"
              :rowKey="(row: any, idx: number) => idx"
              size="small"
            />
          </div>
        </a-card>
      </div>

      <!-- Doris 写入状态 -->
      <div class="status-section">
        <a-card title="Doris 写入状态（7张表）" :loading="dorisStatusLoading">
          <template #extra>
            <a-space>
              <a-button @click="clearAllLists">清空列表</a-button>
            </a-space>
          </template>

          <a-table
            :columns="dorisStatusColumns"
            :data-source="dorisStatusRows"
            :pagination="false"
            size="small"
            :rowKey="(row: any) => row.table_name"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'exists'">
                <a-tag :color="record.exists === '已写入' ? 'success' : 'default'">
                  {{ record.exists }}
                </a-tag>
              </template>
              <template v-if="column.key === 'actions'">
                <a-button type="link" size="small">操作</a-button>
              </template>
            </template>
          </a-table>
        </a-card>
      </div>
    </div>

    <div v-else class="empty-state">
      <div class="icon">^</div>
      <p>初始化中...</p>
    </div>
    </div>
  </div>

  <a-modal v-model:open="previewOpen" title="文件预览（前10行）" :footer="null" width="1100px">
    <div class="preview-toolbar">
      <a-space>
        <span class="preview-label">预览行数</span>
        <a-input-number v-model:value="previewRows" :min="0" :max="200000" style="width: 140px" />
        <a-button @click="setPreviewAll">全量</a-button>
        <a-button type="primary" :loading="previewLoading" :disabled="!previewFile" @click="reloadPreview">刷新</a-button>
      </a-space>
    </div>
    <div v-if="previewLoading" class="preview-loading">加载中...</div>
    <div v-else-if="previewData" class="preview-body">
      <a-table
        :columns="previewColumns"
        :data-source="previewData.data"
        :pagination="false"
        size="small"
        :scroll="{ x: 'max-content', y: 520 }"
        :rowKey="(row: any, idx: number) => idx"
      />
    </div>
    <div v-else class="preview-empty">暂无预览数据</div>
  </a-modal>

  <a-modal
    v-model:open="exportModalOpen"
    title="选择导出表"
    :confirm-loading="exporting"
    @ok="downloadSelectedExport"
    @cancel="closeExportModal"
    width="720px"
  >
    <a-checkbox-group v-model:value="exportSelectedKeys" style="width: 100%">
      <div class="export-grid">
        <a-checkbox v-for="opt in exportOptions" :key="opt.value" :value="opt.value">
          {{ opt.label }}
        </a-checkbox>
      </div>
    </a-checkbox-group>
    <div class="export-actions">
      <a-space>
        <a-button @click="selectAllExports">全选</a-button>
        <a-button @click="clearAllExports">清空</a-button>
      </a-space>
    </div>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import axios from 'axios'
import { message } from 'ant-design-vue'

const route = useRoute()
const analysisData = ref<any | null>(null)
const activeTab = ref('sales_item')

const API_BASE = (import.meta.env.VITE_API_BASE_URL || '/api').trim() || '/api'

const invoiceProjects = ref<any[]>([])
const loadingProjects = ref(false)
const selectedInvoiceProjectId = ref<number | null>(null)
const canShowUpload = computed(() => !!route.params.projectId && !!route.params.companyId)

const salesUploadingCount = ref(0)
const purchaseUploadingCount = ref(0)
const salesUploading = computed(() => salesUploadingCount.value > 0)
const purchaseUploading = computed(() => purchaseUploadingCount.value > 0)
const salesFileList = ref<any[]>([])
const purchaseFileList = ref<any[]>([])

const removeUploadFile = (listRef: { value: any[] }, file: any) => {
  const target = file?.uid || file?.name
  if (!target) return
  listRef.value = listRef.value.filter((item) => (item?.uid || item?.name) !== target)
}

const removeSalesFile = (file: any) => removeUploadFile(salesFileList, file)
const removePurchaseFile = (file: any) => removeUploadFile(purchaseFileList, file)

const formatUploadStatus = (status?: string) => {
  if (status === 'uploading') return '上传中'
  if (status === 'done') return '完成'
  if (status === 'error') return '失败'
  return '等待'
}

const getStatusColor = (status?: string) => {
  if (status === 'uploading') return 'processing'
  if (status === 'done') return 'success'
  if (status === 'error') return 'error'
  return 'default'
}

const fileListColumns = [
  { title: '文件名', dataIndex: 'name', key: 'name', width: 280, ellipsis: true },
  { title: '文件大小', dataIndex: 'size', key: 'size', width: 120 },
  { title: '上传时间', dataIndex: 'uploadTime', key: 'uploadTime', width: 180 },
  { title: '处理状态', dataIndex: 'status', key: 'status', width: 120 },
  { title: '操作', key: 'actions', width: 180 }
]
const fileListScroll = { y: 320 }

const salesFileListData = computed(() => {
  return salesFileList.value.map(file => ({
    ...file,
    size: formatFileSize(file.size),
    uploadTime: file.uploadTime || new Date().toLocaleString('zh-CN')
  }))
})

const purchaseFileListData = computed(() => {
  return purchaseFileList.value.map(file => ({
    ...file,
    size: formatFileSize(file.size),
    uploadTime: file.uploadTime || new Date().toLocaleString('zh-CN')
  }))
})

const formatFileSize = (bytes?: number) => {
  if (!bytes) return '-'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

const clearAllLists = () => {
  salesFileList.value = []
  purchaseFileList.value = []
}

const previewOpen = ref(false)
const previewLoading = ref(false)
const previewData = ref<any | null>(null)
const previewColumns = ref<any[]>([])
const previewRows = ref<number>(10)
const previewFile = ref<File | null>(null)

const analysisRefreshing = ref(false)

const analysisLoading = ref(false)
let analysisRequestId = 0
let dorisStatusRequestId = 0
const pendingRefresh = ref(false)

const emptyTextSales = computed(() =>
  analysisLoading.value ? '加载中...' : '暂无数据，请上传销项发票'
)
const emptyTextPurchase = computed(() =>
  analysisLoading.value ? '加载中...' : '暂无数据，请上传进项发票'
)
const emptyTextMatch = computed(() =>
  analysisLoading.value ? '加载中...' : '暂无数据，请先上传销项和进项'
)

const dorisStatusLoading = ref(false)
const dorisStatusRows = ref<any[]>([])
const dorisStatusColumns = [
  { title: '表', dataIndex: 'label', key: 'label', width: 160 },
  { title: 'Doris表名', dataIndex: 'table_name', key: 'table_name', ellipsis: true },
  { title: '写入', dataIndex: 'exists', key: 'exists', width: 90 },
  { title: '行数', dataIndex: 'row_count', key: 'row_count', width: 120 },
  { title: '操作', key: 'actions', width: 100 }
]

const question = ref('')
const asking = ref(false)
const qaRows = ref<any[]>([])

const qaSql = ref('')
const qaColumns = ref<any[]>([])

// 导出相关状态（提前定义，避免 TDZ 问题）
const exportModalOpen = ref(false)
const exporting = ref(false)
const exportSelectedKeys = ref<string[]>([])

const fetchInvoiceProjects = async () => {
  loadingProjects.value = true
  try {
    const res = await axios.get(
      `${API_BASE}/projects/${route.params.projectId}/companies/${route.params.companyId}/invoice-projects`
    )
    invoiceProjects.value = res.data || []
  } catch (error: any) {
    message.error('加载项目失败: ' + (error?.response?.data?.detail || error?.message || error))
  } finally {
    loadingProjects.value = false
  }
}

const ensureDefaultInvoiceProject = async () => {
  await fetchInvoiceProjects()
  if (invoiceProjects.value.length) {
    return invoiceProjects.value[0]?.id as number
  }
  const res = await axios.post(
    `${API_BASE}/projects/${route.params.projectId}/companies/${route.params.companyId}/invoice-projects`,
    { name: '默认发票项目', description: null }
  )
  await fetchInvoiceProjects()
  return (res.data?.id || invoiceProjects.value[0]?.id) as number
}

const ensureInvoiceProjectId = async () => {
  if (selectedInvoiceProjectId.value) {
    return selectedInvoiceProjectId.value
  }
  const id = await ensureDefaultInvoiceProject()
  selectedInvoiceProjectId.value = id
  return id
}

const getAnalysisCacheKey = (invoiceProjectId: number) => `invoice_analysis_${invoiceProjectId}`
const getStatusCacheKey = (invoiceProjectId: number) => `invoice_doris_status_${invoiceProjectId}`

const loadAnalysis = async (invoiceProjectId: number, useCache: boolean = true) => {
  const requestId = ++analysisRequestId
  analysisLoading.value = true
  if (useCache) {
    try {
      const cached = localStorage.getItem(getAnalysisCacheKey(invoiceProjectId))
      if (cached) {
        analysisData.value = JSON.parse(cached)
        analysisLoading.value = false
        return
      }
    } catch (error) {
      // ignore cache parse errors
    }
  }
  try {
    const res = await axios.get(`${API_BASE}/modules/invoice/projects/${invoiceProjectId}/analysis`)
    if (requestId !== analysisRequestId) return
    analysisData.value = res.data
    try {
      localStorage.setItem(getAnalysisCacheKey(invoiceProjectId), JSON.stringify(res.data))
    } catch (error) {
      // ignore cache write errors
    }
  } catch (error: any) {
    if (requestId !== analysisRequestId) return
    analysisData.value = null
    const detail = error?.response?.data?.detail
    const errMsg = detail?.error || detail || error?.message || error
    message.error('????????: ' + errMsg)
  } finally {
    if (requestId === analysisRequestId) {
      analysisLoading.value = false
    }
  }
}

const loadDorisStatus = async (invoiceProjectId: number, useCache: boolean = true) => {
  const requestId = ++dorisStatusRequestId
  dorisStatusLoading.value = true
  if (useCache) {
    try {
      const cached = localStorage.getItem(getStatusCacheKey(invoiceProjectId))
      if (cached) {
        dorisStatusRows.value = JSON.parse(cached)
        dorisStatusLoading.value = false
        return
      }
    } catch (error) {
      // ignore cache parse errors
    }
  }
  try {
    const res = await axios.get(`${API_BASE}/modules/invoice/projects/${invoiceProjectId}/doris-status`)
    if (requestId !== dorisStatusRequestId) return
    const rows = (res.data?.tables || []).map((t: any) => ({
      ...t,
      exists: t.exists ? '???' : '??',
      row_count: typeof t.row_count === 'number' ? t.row_count.toLocaleString('zh-CN') : '-'
    }))
    dorisStatusRows.value = rows
    try {
      localStorage.setItem(getStatusCacheKey(invoiceProjectId), JSON.stringify(rows))
    } catch (error) {
      // ignore cache write errors
    }
  } catch (error: any) {
    if (requestId !== dorisStatusRequestId) return
    dorisStatusRows.value = []
    const detail = error?.response?.data?.detail
    const errMsg = detail?.error || detail || error?.message || error
    message.error('?? Doris ??????: ' + errMsg)
  } finally {
    if (requestId === dorisStatusRequestId) {
      dorisStatusLoading.value = false
    }
  }
}

const uploadHistoryLoading = ref(false)
const normalizeUploadHistory = (item: any) => ({
  uid: `history-${item.id}`,
  name: item.filename,
  size: item.file_size,
  status: item.status === 'success' ? 'done' : item.status === 'failed' ? 'error' : 'uploading',
  uploadTime: item.created_at ? new Date(item.created_at).toLocaleString('zh-CN') : undefined,
  rowCount: item.row_count,
  errorMessage: item.error_message
})

const getUploadCacheKey = (invoiceProjectId: number) => `invoice_uploads_${invoiceProjectId}`
const loadUploadHistory = async (invoiceProjectId: number, useCache: boolean = true) => {
  uploadHistoryLoading.value = true
  if (useCache) {
    try {
      const cached = localStorage.getItem(getUploadCacheKey(invoiceProjectId))
      if (cached) {
        const parsed = JSON.parse(cached)
        salesFileList.value = (parsed?.sales || []).map(normalizeUploadHistory)
        purchaseFileList.value = (parsed?.purchase || []).map(normalizeUploadHistory)
      }
    } catch {
      // ignore cache errors
    }
  }
  try {
    const res = await axios.get(`${API_BASE}/modules/invoice/projects/${invoiceProjectId}/uploads`)
    const rows = res.data || []
    const sales = rows.filter((r: any) => r.direction === 'sales')
    const purchase = rows.filter((r: any) => r.direction === 'purchase')
    salesFileList.value = sales.map(normalizeUploadHistory)
    purchaseFileList.value = purchase.map(normalizeUploadHistory)
    try {
      localStorage.setItem(getUploadCacheKey(invoiceProjectId), JSON.stringify({ sales, purchase }))
    } catch {
      // ignore cache errors
    }
  } catch (error: any) {
    message.error('加载上传记录失败: ' + (error?.response?.data?.detail || error?.message || error))
  } finally {
    uploadHistoryLoading.value = false
  }
}

const resetInvoiceState = () => {
  analysisData.value = null
  analysisLoading.value = false
  pendingRefresh.value = false
  analysisRequestId = 0
  dorisStatusRequestId = 0
  activeTab.value = 'sales_item'
  salesFileList.value = []
  purchaseFileList.value = []
  previewOpen.value = false
  previewLoading.value = false
  previewData.value = null
  previewColumns.value = []
  previewRows.value = 10
  previewFile.value = null
  dorisStatusRows.value = []
  qaRows.value = []
  qaSql.value = ''
  qaColumns.value = []
  question.value = ''
  exportModalOpen.value = false
  exportSelectedKeys.value = []
}

watch(
  () => [route.params.projectId, route.params.companyId],
  async ([projectId, companyId], prev) => {
    const [prevProjectId, prevCompanyId] = prev || []
    if (!projectId || !companyId) return
    if (projectId !== prevProjectId || companyId !== prevCompanyId) {
      resetInvoiceState()
      selectedInvoiceProjectId.value = null
    }
    try {
      const id = await ensureDefaultInvoiceProject()
      selectedInvoiceProjectId.value = id
      await loadUploadHistory(id)
      // 不阻塞上传历史展示
      loadAnalysis(id)
      loadDorisStatus(id)
    } catch (error: any) {
      selectedInvoiceProjectId.value = null
      message.error('初始化发票模块失败: ' + (error?.response?.data?.detail || error?.message || error))
    }
  },
  { immediate: true }
)

const uploadInvoice = async (file: File, direction: 'sales' | 'purchase') => {
  let invoiceProjectId = selectedInvoiceProjectId.value
  if (!invoiceProjectId) {
    try {
      invoiceProjectId = await ensureInvoiceProjectId()
    } catch (error: any) {
      message.error('初始化发票项目失败: ' + (error?.response?.data?.detail || error?.message || error))
      return
    }
  }
  if (!invoiceProjectId) return
  const formData = new FormData()
  formData.append('file', file)
  formData.append('invoice_project_id', String(invoiceProjectId))
  formData.append('direction', direction)

  try {
    const res = await axios.post(`${API_BASE}/modules/invoice/upload`, formData)
    if (res.data.success) {
      message.success('上传成功')
      pendingRefresh.value = true
    } else {
      message.error('上传失败')
    }
  } catch (error: any) {
    const detail = error?.response?.data?.detail
    const errMsg = detail?.error || detail || error?.message || error
    message.error('上传失败: ' + errMsg)
  }
}

type UploadTask = {
  file: File
  onSuccess?: (res: any, file: File) => void
  onError?: (err: any) => void
  onProgress?: (event: { percent: number }) => void
}

const salesQueue = ref<UploadTask[]>([])
const purchaseQueue = ref<UploadTask[]>([])
const salesProcessing = ref(false)
const purchaseProcessing = ref(false)

const maybeRefreshAfterUploads = async () => {
  if (
    pendingRefresh.value &&
    salesUploadingCount.value === 0 &&
    purchaseUploadingCount.value === 0 &&
    !salesProcessing.value &&
    !purchaseProcessing.value &&
    salesQueue.value.length === 0 &&
    purchaseQueue.value.length === 0
  ) {
    pendingRefresh.value = false
    await refreshAnalysis()
  }
}

const processQueue = async (direction: 'sales' | 'purchase') => {
  const queueRef = direction === 'sales' ? salesQueue : purchaseQueue
  const processingRef = direction === 'sales' ? salesProcessing : purchaseProcessing

  if (processingRef.value) return
  processingRef.value = true

  while (queueRef.value.length > 0) {
    const task = queueRef.value.shift()!
    const { file, onSuccess, onError, onProgress } = task
    if (direction === 'sales') {
      salesUploadingCount.value += 1
    } else {
      purchaseUploadingCount.value += 1
    }
    try {
      onProgress && onProgress({ percent: 30 })
      await uploadInvoice(file as File, direction)
      onProgress && onProgress({ percent: 100 })
      onSuccess && onSuccess({}, file)
    } catch (e) {
      onError && onError(e)
    } finally {
      if (direction === 'sales') {
        salesUploadingCount.value = Math.max(0, salesUploadingCount.value - 1)
      } else {
        purchaseUploadingCount.value = Math.max(0, purchaseUploadingCount.value - 1)
      }
      await maybeRefreshAfterUploads()
    }
  }

  processingRef.value = false
  await maybeRefreshAfterUploads()
}

const handleUploadSales = async (options: any) => {
  const { file, onSuccess, onError, onProgress } = options
  salesQueue.value.push({ file, onSuccess, onError, onProgress })
  processQueue('sales')
}

const handleUploadPurchase = async (options: any) => {
  const { file, onSuccess, onError, onProgress } = options
  purchaseQueue.value.push({ file, onSuccess, onError, onProgress })
  processQueue('purchase')
}

const clearSalesList = () => {
  salesFileList.value = []
}

const clearPurchaseList = () => {
  purchaseFileList.value = []
}

const refreshAnalysis = async () => {
  let invoiceProjectId = selectedInvoiceProjectId.value
  if (!invoiceProjectId) {
    try {
      invoiceProjectId = await ensureInvoiceProjectId()
    } catch (error: any) {
      message.error('初始化发票项目失败: ' + (error?.response?.data?.detail || error?.message || error))
      return
    }
  }
  if (!invoiceProjectId) return
  analysisRefreshing.value = true
  try {
    await loadUploadHistory(invoiceProjectId, false)
    await Promise.allSettled([loadAnalysis(invoiceProjectId, false), loadDorisStatus(invoiceProjectId, false)])
  } finally {
    analysisRefreshing.value = false
  }
}

const handlePreviewUploadFile = async (file: any) => {
  const f = file?.originFileObj
  if (!f || !(f instanceof File)) {
    message.info('历史记录无法预览，请重新上传文件。')
    return
  }
  previewOpen.value = true
  previewFile.value = f as File
  previewLoading.value = true
  previewData.value = null
  previewColumns.value = []
  try {
    const formData = new FormData()
    formData.append('file', f)
    formData.append('rows', String(previewRows.value))
    const res = await axios.post(`${API_BASE}/upload/preview`, formData)
    const data = res.data
    previewData.value = data
    const cols = (data?.columns || []).map((c: string) => ({
      title: c,
      dataIndex: c,
      key: c,
      ellipsis: true,
      width: 160
    }))
    previewColumns.value = cols
  } catch (error: any) {
    message.error('预览失败: ' + (error?.response?.data?.detail?.error || error?.message || error))
  } finally {
    previewLoading.value = false
  }
}

const reloadPreview = async () => {
  if (!previewFile.value) return
  await handlePreviewUploadFile(previewFile.value)
}

const setPreviewAll = () => {
  previewRows.value = 0
}

const exportOptions = [
  { label: '全量销项原始数据（销项原始）', value: 'sales_raw' },
  { label: '全量进项原始数据（进项原始）', value: 'purchase_raw' },
  { label: '表一：销项类别', value: 'table1' },
  { label: '表二：销项客户', value: 'table2' },
  { label: '表三：进项类别', value: 'table3' },
  { label: '表四：进项供应商', value: 'table4' },
  { label: '表五：进销匹配', value: 'table5' }
]

const openExportModal = () => {
  exportModalOpen.value = true
  if (exportSelectedKeys.value.length === 0) {
    exportSelectedKeys.value = exportOptions.map((o) => o.value)
  }
}

const closeExportModal = () => {
  exportModalOpen.value = false
}

const selectAllExports = () => {
  exportSelectedKeys.value = exportOptions.map((o) => o.value)
}

const clearAllExports = () => {
  exportSelectedKeys.value = []
}

const downloadSelectedExport = async () => {
  let invoiceProjectId = selectedInvoiceProjectId.value
  if (!invoiceProjectId) {
    try {
      invoiceProjectId = await ensureInvoiceProjectId()
    } catch (error: any) {
      message.error('初始化发票项目失败: ' + (error?.response?.data?.detail || error?.message || error))
      return
    }
  }
  if (!invoiceProjectId) return
  if (exportSelectedKeys.value.length === 0) {
    message.warning('请至少选择一张表')
    return
  }
  exporting.value = true
  try {
    const items = exportSelectedKeys.value.join(',')
    const res = await axios.get(
      `${API_BASE}/modules/invoice/projects/${invoiceProjectId}/export-selected`,
      { params: { items }, responseType: 'blob' }
    )
    const url = window.URL.createObjectURL(res.data)
    const link = document.createElement('a')
    link.href = url
    link.download = `invoice_project_${invoiceProjectId}_export.xlsx`
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.URL.revokeObjectURL(url)
    exportModalOpen.value = false
  } catch (error: any) {
    message.error('导出失败: ' + (error?.response?.data?.detail || error?.message || error))
  } finally {
    exporting.value = false
  }
}

const askQuestion = async () => {
  if (!question.value.trim()) return
  let invoiceProjectId = selectedInvoiceProjectId.value
  if (!invoiceProjectId) {
    try {
      invoiceProjectId = await ensureInvoiceProjectId()
    } catch (error: any) {
      message.error('初始化发票项目失败: ' + (error?.response?.data?.detail || error?.message || error))
      return
    }
  }
  if (!invoiceProjectId) return
  asking.value = true
  try {
    const res = await axios.post(`${API_BASE}/modules/invoice/query/natural`, {
      invoice_project_id: invoiceProjectId,
      query: question.value.trim()
    })
    qaSql.value = res.data.sql || ''
    qaRows.value = res.data.data || []
    const cols = qaRows.value.length ? Object.keys(qaRows.value[0]) : []
    qaColumns.value = cols.map((c) => ({ title: c, dataIndex: c, key: c }))
  } catch (error: any) {
    qaRows.value = []
    qaColumns.value = []
    qaSql.value = ''
    message.error(
      '提问失败: ' +
        (error?.response?.data?.detail?.error || error?.response?.data?.detail || error?.message || error)
    )
  } finally {
    asking.value = false
  }
}

const baseColumns = [
  { title: '税率', dataIndex: 'tax_rate', key: 'tax_rate', width: 90, align: 'right', customRender: ({ text }: any) => formatRate(text) },
  { title: '价税合计', dataIndex: 'amount_with_tax', key: 'amount_with_tax', width: 160, align: 'right', customRender: ({ text }: any) => formatNumber(Number(text || 0)) },
  { title: '占比', dataIndex: 'share', key: 'share', width: 110, align: 'right', customRender: ({ text }: any) => `${formatNumber(Number(text || 0))}%` },
  { title: '数量', dataIndex: 'quantity', key: 'quantity', width: 120, align: 'right', customRender: ({ text }: any) => formatNumber(Number(text || 0)) },
  { title: '平均单价', dataIndex: 'avg_unit_price', key: 'avg_unit_price', width: 140, align: 'right', customRender: ({ text }: any) => formatNumber(Number(text || 0)) },
  { title: '最高单价', dataIndex: 'max_unit_price', key: 'max_unit_price', width: 140, align: 'right', customRender: ({ text }: any) => formatNumber(Number(text || 0)) },
  { title: '开票份数', dataIndex: 'invoice_count', key: 'invoice_count', width: 120, align: 'right', customRender: ({ text }: any) => formatInt(Number(text || 0)) },
  { title: '平均月度开票份数', dataIndex: 'avg_monthly_invoice_count', key: 'avg_monthly_invoice_count', width: 160, align: 'right', customRender: ({ text }: any) => formatNumber(Number(text || 0)) },
  { title: '专票金额', dataIndex: 'special_amount', key: 'special_amount', width: 160, align: 'right', customRender: ({ text }: any) => formatNumber(Number(text || 0)) },
  { title: '普票金额', dataIndex: 'normal_amount', key: 'normal_amount', width: 160, align: 'right', customRender: ({ text }: any) => formatNumber(Number(text || 0)) },
  { title: '作废发票数量', dataIndex: 'void_count', key: 'void_count', width: 140, align: 'right', customRender: ({ text }: any) => formatInt(Number(text || 0)) },
  { title: '红冲发票数量', dataIndex: 'red_flush_count', key: 'red_flush_count', width: 140, align: 'right', customRender: ({ text }: any) => formatInt(Number(text || 0)) }
]

const salesItemColumns = [
  { title: '销方名称', dataIndex: 'seller_name', key: 'seller_name', width: 220, ellipsis: true },
  { title: '货物/劳务大类', dataIndex: 'item_category', key: 'item_category', width: 200, ellipsis: true },
  ...baseColumns
]

const salesBuyerColumns = [
  { title: '销方名称', dataIndex: 'seller_name', key: 'seller_name', width: 220, ellipsis: true },
  { title: '购买方名称', dataIndex: 'buyer_name', key: 'buyer_name', width: 220, ellipsis: true },
  ...baseColumns
]

const purchaseItemColumns = [
  { title: '购买方名称', dataIndex: 'buyer_name', key: 'buyer_name', width: 220, ellipsis: true },
  { title: '货物/劳务大类', dataIndex: 'item_category', key: 'item_category', width: 200, ellipsis: true },
  ...baseColumns
]

const purchaseSellerColumns = [
  { title: '购买方名称', dataIndex: 'buyer_name', key: 'buyer_name', width: 220, ellipsis: true },
  { title: '销方名称', dataIndex: 'seller_name', key: 'seller_name', width: 220, ellipsis: true },
  ...baseColumns
]

const matchColumns = [
  { title: '企业名称', dataIndex: 'company_name', key: 'company_name', width: 220, ellipsis: true },
  { title: '货物/劳务大类', dataIndex: 'item_category', key: 'item_category', width: 200, ellipsis: true },
  { title: '销项数量', dataIndex: 'sales_quantity', key: 'sales_quantity', width: 140, align: 'right', customRender: ({ text }: any) => formatNumber(Number(text || 0)) },
  { title: '进项数量', dataIndex: 'purchase_quantity', key: 'purchase_quantity', width: 140, align: 'right', customRender: ({ text }: any) => formatNumber(Number(text || 0)) },
  { title: '进销数量差异', dataIndex: 'quantity_diff', key: 'quantity_diff', width: 150, align: 'right', customRender: ({ text }: any) => formatNumber(Number(text || 0)) },
  { title: '销项平均单价', dataIndex: 'sales_avg_unit_price', key: 'sales_avg_unit_price', width: 150, align: 'right', customRender: ({ text }: any) => formatNumber(Number(text || 0)) },
  { title: '进项平均单价', dataIndex: 'purchase_avg_unit_price', key: 'purchase_avg_unit_price', width: 150, align: 'right', customRender: ({ text }: any) => formatNumber(Number(text || 0)) },
  { title: '进销单价差异', dataIndex: 'avg_unit_price_diff', key: 'avg_unit_price_diff', width: 150, align: 'right', customRender: ({ text }: any) => formatNumber(Number(text || 0)) }
]

const formatNumber = (n: number) => {
  if (n === undefined || n === null) return 0
  return Number(n).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

const formatInt = (n: number) => {
  if (n === undefined || n === null) return 0
  return Math.round(Number(n)).toLocaleString('zh-CN')
}

const formatRate = (n: any) => {
  const v = Number(n || 0)
  if (!Number.isFinite(v)) return '0%'
  if (v > 1) return `${v}%`
  return `${(v * 100).toFixed(0)}%`
}

const tableScroll = { x: 2400, y: 520 }
const tablePagination = { pageSize: 20, showSizeChanger: true, pageSizeOptions: ['10', '20', '50', '100'] }
</script>

<style scoped>
.invoice-module {
  color: var(--text-primary);
  display: flex;
  flex-direction: column;
  box-sizing: border-box;
  gap: 16px;
  min-height: 0;
  min-width: 0;
  width: 100%;
  overflow: hidden;
}

.module-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0;
}

.module-header h2 {
  color: var(--neon-blue);
  margin: 0;
  font-family: 'Orbitron', sans-serif;
}

.invoice-body {
  display: flex;
  flex-direction: column;
  gap: 20px;
  box-sizing: border-box;
  min-width: 0;
  overflow-x: hidden;
}

.upload-section {
  flex-shrink: 0;
}

.upload-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  min-width: 0;
}

.upload-card {
  height: 100%;
  min-width: 0;
  overflow: hidden;
}

.upload-drop-zone {
  height: 200px;
}

.upload-drop-zone :deep(.ant-upload) {
  width: 100%;
}

.upload-drop-zone :deep(.ant-upload-drag) {
  height: 200px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.upload-icon {
  display: inline-flex;
  width: 44px;
  height: 44px;
  border-radius: 12px;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  color: var(--neon-blue);
  background: rgba(0, 86, 179, 0.08);
}

.file-list-section {
  flex-shrink: 0;
}

.file-list-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  min-width: 0;
}

.file-list-card {
  margin-bottom: 0;
  min-width: 0;
  overflow: hidden;
}

.file-list-card :deep(.ant-table) {
  font-size: 13px;
}

.file-list-card :deep(.ant-table-wrapper) {
  overflow-x: auto;
}

.analysis-section {
  flex-shrink: 0;
  min-width: 0;
  overflow: hidden;
}

.analysis-section :deep(.ant-table-wrapper) {
  overflow-x: auto;
}

.analysis-section .summary-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
  margin-bottom: 20px;
}

.analysis-section .card {
  background: var(--card-hover-bg);
  border: 1px solid var(--border-color);
  border-radius: 10px;
  padding: 12px;
  box-shadow: 0 0 12px rgba(0, 0, 0, 0.1);
  transition: all 0.3s;
}

.analysis-section .card:hover {
  border-color: var(--neon-blue);
  transform: translateY(-2px);
}

.analysis-section .card-title {
  color: var(--text-secondary);
  font-size: 13px;
  letter-spacing: 1px;
}

.analysis-section .card-metric {
  font-size: 20px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 6px 0;
}

.analysis-section .card-sub {
  color: var(--text-secondary);
  font-size: 12px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.analysis-tabs {
  margin-top: 16px;
}

.qa-panel {
  margin-top: 20px;
  padding: 16px;
  border: 1px solid var(--border-color);
  background: var(--card-hover-bg);
  border-radius: 10px;
}

.qa-title {
  color: var(--neon-blue);
  font-size: 14px;
  margin-bottom: 12px;
  font-weight: 600;
}

.qa-sql {
  margin-top: 12px;
  margin-bottom: 12px;
  color: var(--text-secondary);
  font-size: 12px;
  white-space: pre-wrap;
  word-break: break-word;
  background: var(--glass-bg);
  padding: 8px;
  border-radius: 4px;
}

.status-section {
  flex-shrink: 0;
  min-width: 0;
  overflow: hidden;
}

.status-section :deep(.ant-table) {
  font-size: 13px;
}

.status-section :deep(.ant-table-wrapper) {
  overflow-x: auto;
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

.preview-loading,
.preview-empty {
  padding: 16px;
  color: var(--text-secondary);
}

.preview-toolbar {
  padding: 0 0 12px 0;
}

.preview-label {
  color: var(--text-secondary);
}

.preview-body {
  padding-top: 8px;
}

.export-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px 16px;
  padding: 6px 2px;
}

.export-actions {
  margin-top: 14px;
  display: flex;
  justify-content: flex-end;
}

@media (max-width: 1200px) {
  .upload-grid,
  .file-list-grid {
    grid-template-columns: 1fr;
  }
}
</style>
