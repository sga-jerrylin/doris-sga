<!-- @ts-nocheck -->
<template>
  <div class="dashboard-container" v-if="projectStore.currentCompany">
    <!-- Welcome Header -->
    <div class="dashboard-header">
      <div class="welcome-text">
        <h1>早安，管理员</h1>
        <p>今天是 {{ currentDate }}，这里是 {{ projectStore.currentCompany.name }} 的财务概览。</p>
      </div>
      <div class="header-actions">
        <button class="action-btn primary" @click="router.push(`/project/${projectStore.currentProject?.id}/company/${projectStore.currentCompany?.id}/module/invoice`)">
          <UploadIcon :size="16" /> 上传发票
        </button>
      </div>
    </div>

    <!-- Key Metrics -->
    <div class="metrics-grid">
      <div class="metric-card">
        <div class="metric-icon blue">
          <DollarSignIcon :size="24" />
        </div>
        <div class="metric-info">
          <span class="label">本月进项总额</span>
          <span class="value">{{ formatCurrency(metrics.monthly_purchase_total) }}</span>
          <span :class="['trend', purchaseTrend.className]">{{ purchaseTrend.text }}</span>
        </div>
      </div>
      
      <div class="metric-card">
        <div class="metric-icon purple">
          <CreditCardIcon :size="24" />
        </div>
        <div class="metric-info">
          <span class="label">本月销项总额</span>
          <span class="value">{{ formatCurrency(metrics.monthly_sales_total) }}</span>
          <span :class="['trend', salesTrend.className]">{{ salesTrend.text }}</span>
        </div>
      </div>

      <div class="metric-card">
        <div class="metric-icon orange">
          <AlertCircleIcon :size="24" />
        </div>
        <div class="metric-info">
          <span class="label">待处理异常</span>
          <span class="value">{{ formatInt(metrics.pending_exceptions) }} 笔</span>
          <span :class="['trend', exceptionTrend.className]">{{ exceptionTrend.text }}</span>
        </div>
      </div>
      
      <div class="metric-card">
        <div class="metric-icon green">
          <ActivityIcon :size="24" />
        </div>
        <div class="metric-info">
          <span class="label">银行余额</span>
          <span class="value">{{ formatCurrency(metrics.bank_balance) }}</span>
          <span class="trend neutral">{{ bankTrendText }}</span>
        </div>
      </div>
    </div>

    <!-- Main Content Grid -->
    <div class="content-grid">
      <!-- Left: Company Info -->
      <div class="info-section glass-panel">
        <div class="section-header">
          <h3>企业档案</h3>
          <button class="more-btn"><MoreHorizontalIcon :size="16" /></button>
        </div>
        <div class="company-profile">
          <div class="profile-header">
            <div class="building-icon">
              <BuildingIcon :size="32" />
            </div>
            <div class="profile-title">
              <h4>{{ projectStore.currentCompany.name }}</h4>
              <span class="tag">存续 (在营)</span>
            </div>
          </div>
          <div class="profile-details">
            <div class="detail-item">
              <span class="d-label">纳税人识别号</span>
              <span class="d-value">{{ projectStore.currentCompany.tax_id || '-' }}</span>
            </div>
            <div class="detail-item">
              <span class="d-label">成立日期</span>
              <span class="d-value">{{ projectStore.currentCompany.established_at || projectStore.currentCompany.establishedAt || '-' }}</span>
            </div>
            <div class="detail-item">
              <span class="d-label">注册资本</span>
              <span class="d-value">{{ projectStore.currentCompany.registered_capital || projectStore.currentCompany.registeredCapital || '-' }}</span>
            </div>
            <div class="detail-item full">
              <span class="d-label">经营范围</span>
              <p class="d-desc">{{ projectStore.currentCompany.background_info || '暂无详细背景信息...' }}</p>
            </div>
          </div>
        </div>
      </div>

      <!-- Right: Activity Feed -->
      <div class="activity-section glass-panel">
        <div class="section-header">
          <h3>最近动态</h3>
          <span class="badge">Live</span>
        </div>
        <div v-if="activityItems.length" class="activity-list">
          <div class="activity-item" v-for="(item, i) in activityItems" :key="i">
            <div class="activity-icon" :class="item.type">
              <component :is="item.icon" :size="14" />
            </div>
            <div class="activity-content">
              <span class="act-text">{{ item.text }}</span>
              <span class="act-time">{{ formatActivityTime(item.time) }}</span>
            </div>
          </div>
        </div>
        <div v-else class="activity-empty">暂无动态</div>
      </div>
    </div>

  </div>
  <div v-else class="empty-state">
    <p>正在加载企业数据...</p>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import axios from 'axios'
import { useProjectStore } from '../stores/projectStore'
import { useRouter } from 'vue-router'
import { 
  DollarSignIcon, 
  CreditCardIcon, 
  AlertCircleIcon, 
  ActivityIcon,
  BuildingIcon,
  MoreHorizontalIcon,
  FileTextIcon,
  UploadIcon,
  CheckCircleIcon
} from 'lucide-vue-next'

const router = useRouter()
const projectStore = useProjectStore()

const API_BASE = (import.meta.env.VITE_API_BASE_URL || '/api').trim() || '/api'

const dashboard = ref<any | null>(null)
const dashboardLoading = ref(false)

function buildTrend(mom?: number | null) {
  if (mom === null || mom === undefined || !Number.isFinite(Number(mom))) {
    return { text: '????', className: 'neutral' }
  }
  const pct = (Number(mom) * 100).toFixed(1)
  if (mom > 0) return { text: `+${pct}% ??`, className: 'positive' }
  if (mom < 0) return { text: `${pct}% ??`, className: 'negative' }
  return { text: '0% ??', className: 'neutral' }
}

const metrics = computed(() => ({
  monthly_purchase_total: dashboard.value?.metrics?.monthly_purchase_total ?? 0,
  monthly_purchase_mom: dashboard.value?.metrics?.monthly_purchase_mom ?? null,
  monthly_sales_total: dashboard.value?.metrics?.monthly_sales_total ?? 0,
  monthly_sales_mom: dashboard.value?.metrics?.monthly_sales_mom ?? null,
  pending_exceptions: dashboard.value?.metrics?.pending_exceptions ?? 0,
  bank_balance: dashboard.value?.metrics?.bank_balance ?? null
}))

const purchaseTrend = computed(() => buildTrend(metrics.value.monthly_purchase_mom))
const salesTrend = computed(() => buildTrend(metrics.value.monthly_sales_mom))
const exceptionTrend = computed(() => {
  if (metrics.value.pending_exceptions > 0) {
    return { text: '????', className: 'negative' }
  }
  return { text: '????', className: 'neutral' }
})
const bankTrendText = computed(() => (metrics.value.bank_balance === null ? '????' : '??'))

const activityIconMap: Record<string, any> = {
  upload: UploadIcon,
  alert: AlertCircleIcon,
  success: CheckCircleIcon,
  info: FileTextIcon
}

const activityItems = computed(() => {
  const items = dashboard.value?.activities || []
  return items.map((item: any) => ({
    ...item,
    icon: activityIconMap[item.type] || FileTextIcon
  }))
})

const fetchDashboard = async (projectId: number, companyId: number) => {
  dashboardLoading.value = true
  try {
    const res = await axios.get(`${API_BASE}/projects/${projectId}/companies/${companyId}/dashboard`)
    dashboard.value = res.data
  } catch (error) {
    dashboard.value = null
  } finally {
    dashboardLoading.value = false
  }
}

watch(
  () => [projectStore.currentProject?.id, projectStore.currentCompany?.id],
  async ([projectId, companyId]) => {
    if (!projectId || !companyId) {
      dashboard.value = null
      return
    }
    await fetchDashboard(projectId, companyId)
  },
  { immediate: true }
)

const formatCurrency = (value: number | null | undefined) => {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) return '--'
  const num = Number(value)
  return `? ${num.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

const formatInt = (value: number | null | undefined) => {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) return '0'
  return Math.round(Number(value)).toLocaleString('zh-CN')
}

const formatActivityTime = (value: string) => {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)
  return date.toLocaleString('zh-CN')
}

const currentDate = computed(() => {
  return new Date().toLocaleDateString('zh-CN', { year: 'numeric', month: 'long', day: 'numeric', weekday: 'long' })
})

</script>

<style scoped>
.dashboard-container {
  padding: 30px 40px;
  max-width: 1600px;
  margin: 0 auto;
  color: var(--text-primary);
}

.dashboard-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  margin-bottom: 40px;
}

.welcome-text h1 {
  font-size: 28px;
  font-weight: 700;
  margin: 0 0 10px 0;
  color: var(--text-primary);
}

.welcome-text p {
  color: var(--text-secondary);
  margin: 0;
}

.action-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 20px;
  border-radius: 8px;
  border: none;
  cursor: pointer;
  font-weight: 600;
  transition: all 0.2s;
}

.action-btn.primary {
  background: var(--neon-blue);
  color: #fff;
  box-shadow: 0 4px 12px rgba(0, 86, 179, 0.2);
}

.action-btn.primary:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(0, 86, 179, 0.3);
}

/* Metrics Grid */
.metrics-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 24px;
  margin-bottom: 40px;
}

.metric-card {
  background: var(--glass-bg);
  border: 1px solid var(--border-color);
  padding: 24px;
  border-radius: 12px;
  display: flex;
  align-items: flex-start;
  gap: 16px;
  transition: transform 0.2s;
}

.metric-card:hover {
  transform: translateY(-2px);
  border-color: var(--neon-blue);
}

.metric-icon {
  width: 48px;
  height: 48px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.metric-icon.blue { background: rgba(0, 86, 179, 0.1); color: var(--neon-blue); }
.metric-icon.purple { background: rgba(111, 66, 193, 0.1); color: var(--neon-purple); }
.metric-icon.green { background: rgba(40, 167, 69, 0.1); color: var(--neon-green); }
.metric-icon.orange { background: rgba(253, 126, 20, 0.1); color: #fd7e14; }

.metric-info {
  display: flex;
  flex-direction: column;
}

.metric-info .label {
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 6px;
}

.metric-info .value {
  font-size: 20px;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 6px;
}

.metric-info .trend {
  font-size: 12px;
  font-weight: 500;
}

.trend.positive { color: var(--neon-green); }
.trend.negative { color: #dc3545; }
.trend.neutral { color: var(--text-secondary); }

/* Content Grid */
.content-grid {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 30px;
}

.glass-panel {
  background: var(--glass-bg);
  border: 1px solid var(--border-color);
  border-radius: 16px;
  padding: 24px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.section-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
}

.more-btn {
  background: transparent;
  border: none;
  color: var(--text-secondary);
  cursor: pointer;
}

/* Company Profile */
.profile-header {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 30px;
}

.building-icon {
  width: 60px;
  height: 60px;
  background: var(--card-hover-bg);
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-primary);
}

.profile-title h4 {
  margin: 0 0 6px 0;
  font-size: 18px;
}

.tag {
  font-size: 11px;
  background: rgba(40, 167, 69, 0.1);
  color: var(--neon-green);
  padding: 2px 8px;
  border-radius: 4px;
}

.profile-details {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 24px;
}

.detail-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.detail-item.full {
  grid-column: span 2;
}

.d-label {
  font-size: 12px;
  color: var(--text-secondary);
}

.d-value {
  font-size: 14px;
  color: var(--text-primary);
  font-weight: 500;
}

.d-desc {
  font-size: 14px;
  color: var(--text-primary);
  line-height: 1.6;
  margin: 0;
}

/* Activity Feed */
.activity-list {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.activity-item {
  display: flex;
  gap: 12px;
  align-items: flex-start;
}

.activity-icon {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: var(--card-hover-bg);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary);
  flex-shrink: 0;
  margin-top: 2px;
}

.activity-icon.upload { color: var(--neon-blue); background: rgba(0, 86, 179, 0.1); }
.activity-icon.alert { color: #fd7e14; background: rgba(253, 126, 20, 0.1); }
.activity-icon.success { color: var(--neon-green); background: rgba(40, 167, 69, 0.1); }

.activity-content {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.activity-empty {
  color: var(--text-secondary);
  font-size: 12px;
  padding: 4px 0;
}

.act-text {
  font-size: 13px;
  color: var(--text-primary);
  line-height: 1.4;
}

.act-time {
  font-size: 11px;
  color: var(--text-secondary);
}

.badge {
  font-size: 10px;
  background: rgba(255, 0, 0, 0.1);
  color: red;
  padding: 2px 6px;
  border-radius: 4px;
}
</style>
