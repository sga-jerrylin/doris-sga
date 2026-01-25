<!-- @ts-nocheck -->
<template>
  <div class="app-wrapper">
    <!-- 1. Unified Sidebar -->
    <div class="main-sidebar glass-panel">
      <!-- Header / Logo -->
      <div class="sidebar-header">
        <div class="logo-area">
          <img src="/logo_neon.png" alt="Logo" class="sidebar-logo" />
          <span class="app-name">TabSis 表姐</span>
        </div>
      </div>

      <!-- Context Switcher (Project & Company) -->
      <div class="context-section">
        <div class="context-label">当前项目</div>
        <a-select
          v-model:value="currentProjectId"
          class="context-select"
          placeholder="选择项目"
          :dropdown-style="{ background: 'var(--sidebar-bg)', border: '1px solid var(--border-color)' }"
          @change="handleProjectChange"
        >
          <a-select-option v-for="p in projectStore.projects" :key="p.id" :value="p.id">
            {{ p.name }}
          </a-select-option>
          <template #dropdownRender="{ menuNode: menu }">
            <v-nodes :vnodes="menu" />
            <div class="select-footer" @mousedown="e => e.preventDefault()" @click="createNewProject">
              <PlusIcon :size="14" /> 新建项目
            </div>
          </template>
        </a-select>

        <div class="context-label mt-3">当前企业</div>
        <a-select
          v-model:value="currentCompanyId"
          class="context-select"
          placeholder="选择企业"
          :disabled="!currentProjectId"
          @change="handleCompanyChange"
        >
          <a-select-option v-for="c in projectStore.companies" :key="c.id" :value="c.id">
            <span class="company-option">
              <span class="dot" :style="{ background: getCompanyColor(c.id) }"></span>
              {{ c.name }}
            </span>
          </a-select-option>
          <template #dropdownRender="{ menuNode: menu }">
            <v-nodes :vnodes="menu" />
            <div class="select-footer" @mousedown="e => e.preventDefault()" @click="showAddCompanyModal = true">
              <PlusIcon :size="14" /> 添加企业
            </div>
          </template>
        </a-select>
      </div>

      <!-- Navigation Menu -->
      <div class="nav-menu">
        <div class="nav-label">功能导航</div>
        
        <div class="nav-item" :class="{ active: isRouteActive('home') }" @click="navTo('home')">
          <LayoutDashboardIcon :size="18" />
          <span>企业概览</span>
        </div>

        <div class="nav-item" :class="{ active: isRouteActive('invoice'), disabled: !canUseModules }" @click="navTo('invoice')">
          <FileTextIcon :size="18" />
          <span>发票分析</span>
        </div>

        <div class="nav-item" :class="{ active: isRouteActive('bank'), disabled: !canUseModules }" @click="navTo('bank')">
          <LandmarkIcon :size="18" />
          <span>银行流水</span>
        </div>

        <div class="nav-item disabled">
          <FileCheckIcon :size="18" />
          <span>纳税申报</span>
          <span class="badge">Coming</span>
        </div>
      </div>

      <!-- Footer -->
      <div class="sidebar-footer">
        <div class="nav-item" :class="{ active: route.name === 'settings' }" @click="goSettings">
          <SettingsIcon :size="18" />
          <span>系统设置</span>
        </div>
        <div class="user-profile">
          <div class="avatar">A</div>
          <div class="user-info">
            <div class="name">Admin User</div>
            <div class="role">超级管理员</div>
          </div>
        </div>
      </div>
    </div>

    <!-- 2. Main Content Area -->
    <div class="content-area">
      <!-- Top Header -->
      <header class="app-header">
        <div class="header-left">
          <h2 class="page-title">{{ currentPageTitle }}</h2>
        </div>

        <div class="header-right">
          <!-- Theme Toggle -->
          <button class="icon-btn theme-btn" @click="toggleTheme" :title="currentTheme === 'dark' ? '切换亮色' : '切换暗色'">
            <SunIcon v-if="currentTheme === 'dark'" :size="20" />
            <MoonIcon v-else :size="20" />
          </button>

          <!-- Search -->
          <div class="search-bar">
            <SearchIcon :size="16" class="search-icon" />
            <input type="text" placeholder="全局搜索..." />
            <span class="kbd">Ctrl K</span>
          </div>

          <!-- Agent Toggle -->
          <button class="agent-btn" @click="toggleAgent" :class="{ active: agentOpen }">
            <BotIcon :size="20" />
            <span>AI 助手</span>
          </button>
        </div>
      </header>

      <!-- Router View -->
      <main class="main-view">
        <router-view v-if="canShowMainView"></router-view>
        <div v-else class="welcome-empty">
          <div class="empty-content">
            <div class="logo-big">
              <img src="/logo_neon.png" alt="Logo" />
            </div>
            <h1>欢迎使用 TabSis 表姐</h1>
            <p>请在左侧边栏选择或创建项目与企业以开始工作。</p>
            <div class="quick-actions">
              <a-button type="primary" size="large" @click="createNewProject">
                <PlusIcon :size="16" /> 创建新项目
              </a-button>
            </div>
          </div>
        </div>
      </main>
    </div>

    <!-- 3. Agent Drawer -->
    <div 
      class="agent-drawer" 
      :class="{ open: agentOpen, fullscreen: agentFullscreen }" 
      :style="agentStyle"
    >
      <div v-if="!agentFullscreen" class="resize-handle" @mousedown="startResize"></div>
      <div class="agent-panel glass-panel">
        <div class="agent-header">
          <div class="agent-title">
            <div class="ai-avatar">
              <BotIcon :size="20" />
            </div>
            <div class="ai-info">
              <span class="name">表姐助手</span>
              <span class="status">在线</span>
            </div>
          </div>
          <div class="header-actions">
            <button class="icon-btn" @click="toggleSessionList" title="历史对话">
              <HistoryIcon :size="16" />
            </button>
            <button class="icon-btn" @click="startNewChat" title="新对话">
              <PlusIcon :size="16" />
            </button>
            <button class="icon-btn" @click="toggleFullscreen" :title="agentFullscreen ? '退出全屏' : '全屏模式'">
              <Maximize2Icon v-if="!agentFullscreen" :size="16" />
              <Minimize2Icon v-else :size="16" />
            </button>
            <button class="icon-btn" @click="agentOpen = false" title="关闭">
              <XIcon :size="18" />
            </button>
          </div>
        </div>

        <!-- 历史对话列表 -->
        <div v-if="showSessionList" class="session-list-panel">
          <div class="session-list-header">
            <span>历史对话</span>
            <button class="icon-btn" @click="showSessionList = false">
              <XIcon :size="14" />
            </button>
          </div>
          <div class="session-list-body">
            <div v-if="loadingSessions" class="session-loading">加载中...</div>
            <div v-else-if="chatSessions.length === 0" class="session-empty">暂无历史对话</div>
            <div
              v-else
              v-for="session in chatSessions"
              :key="session.id"
              class="session-item"
              :class="{ active: chatSessionId === session.id }"
              @click="switchToSession(session)"
            >
              <div class="session-title">{{ session.title || '未命名对话' }}</div>
              <div class="session-time">{{ formatSessionTime(session.updated_at) }}</div>
              <button class="session-delete" @click.stop="deleteSession(session.id)" title="删除">
                <TrashIcon :size="12" />
              </button>
            </div>
          </div>
        </div>
        
        <div class="agent-body" ref="chatBody">
          <div v-for="(msg, index) in chatMessages" :key="index" class="chat-bubble" :class="msg.role">
            <!-- 工具调用步骤展示 -->
            <div v-if="msg.toolSteps && msg.toolSteps.length > 0" class="tool-steps">
              <div
                v-for="(step, stepIdx) in msg.toolSteps"
                :key="stepIdx"
                class="tool-step"
                :class="step.status"
              >
                <div class="step-icon">
                  <span v-if="step.status === 'running'" class="spinner"></span>
                  <span v-else-if="step.status === 'success'">✓</span>
                  <span v-else>✗</span>
                </div>
                <div class="step-info">
                  <div class="step-name">{{ getToolDisplayName(step.name) }}</div>
                  <div class="step-content" v-html="renderMarkdown(step.content)"></div>
                </div>
              </div>
            </div>
            <!-- 消息内容 -->
            <div v-if="msg.content" class="bubble-content" v-html="renderMarkdown(msg.content)"></div>
            <div v-if="msg.widget" class="widget-preview">
              <div class="widget-title">{{ msg.widget.title || '数据卡片' }}</div>
              <pre class="widget-json">{{ JSON.stringify(msg.widget, null, 2) }}</pre>
            </div>
          </div>
          <div v-if="isThinking" class="thinking-bubble">
            <div class="typing-dots">
              <span></span><span></span><span></span>
            </div>
            <span>正在思考中...</span>
          </div>
        </div>
        
        <div class="agent-footer">
          <div class="input-container">
            <input 
              v-model="inputMessage" 
              placeholder="问点什么..." 
              @keyup.enter="sendMessage"
            />
            <button class="send-btn" @click="sendMessage">
              <SendIcon :size="16" />
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- Modals -->
  <a-modal
    v-model:open="showAddCompanyModal"
    title="添加企业"
    :confirm-loading="addingCompany"
    @ok="handleAddCompany"
    @cancel="resetCompanyForm"
  >
    <a-form layout="vertical">
      <a-form-item label="企业名称" required>
        <a-input v-model:value="addCompanyForm.name" placeholder="请输入企业名称" />
      </a-form-item>
      <a-form-item label="税号">
        <a-input v-model:value="addCompanyForm.taxId" placeholder="可选，企业税号" />
      </a-form-item>
      <a-form-item label="企业背景">
        <a-textarea v-model:value="addCompanyForm.background" :rows="4" placeholder="主营业务、行业、成立时间等" />
      </a-form-item>
    </a-form>
  </a-modal>

  <a-modal
    v-model:open="showCreateProjectModal"
    title="新建项目"
    @ok="handleCreateProject"
  >
    <a-input v-model:value="newProjectName" placeholder="请输入项目名称" />
  </a-modal>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, nextTick, computed, defineComponent, h, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useProjectStore } from '../stores/projectStore'
import axios from 'axios'
import { message } from 'ant-design-vue'
import MarkdownIt from 'markdown-it'
import DOMPurify from 'dompurify'
import {
  LayoutDashboardIcon,
  FileTextIcon,
  LandmarkIcon,
  FileCheckIcon,
  SettingsIcon,
  SearchIcon,
  BotIcon,
  Maximize2Icon,
  Minimize2Icon,
  XIcon,
  SunIcon,
  MoonIcon,
  PlusIcon,
  SendIcon,
  HistoryIcon,
  TrashIcon
} from 'lucide-vue-next'

// Helper for VNodes in Select Dropdown
const VNodes = defineComponent({
  props: { vnodes: { type: Object, required: true } },
  render() { return this.vnodes }
})

const router = useRouter()
const route = useRoute()
const projectStore = useProjectStore()

// State
const currentProjectId = ref<number | undefined>(undefined)
const currentCompanyId = ref<number | undefined>(undefined)
const currentTheme = ref('light')

const agentWidth = ref(380)
const agentOpen = ref(true)
const agentFullscreen = ref(false)

const md = new MarkdownIt({ linkify: true, breaks: true })
const renderMarkdown = (text: string) => DOMPurify.sanitize(md.render(text || ''))

// 工具名称映射
const getToolDisplayName = (name: string): string => {
  const map: Record<string, string> = {
    'init_database': '连接数据库',
    'list_tables': '获取表列表',
    'get_llm_config': '加载 LLM 配置',
    'get_context': '获取上下文',
    'generate_sql': '生成 SQL',
    'run_sql': '执行查询',
    'format_result': '格式化结果'
  }
  return map[name] || name
}

const showAddCompanyModal = ref(false)
const showCreateProjectModal = ref(false)
const newProjectName = ref('')
const addingCompany = ref(false)
const addCompanyForm = reactive({ name: '', taxId: '', background: '' })

// Chat State
const inputMessage = ref('')
const isThinking = ref(false)
const chatBody = ref<HTMLElement | null>(null)
interface ToolStep { name: string; content: string; status: 'running' | 'success' | 'error' }
interface ChatMessage { role: 'user' | 'ai'; content: string; widget?: any; toolSteps?: ToolStep[] }
const chatMessages = ref<ChatMessage[]>([
  { role: 'ai', content: '你好！我是 TabSis 智能助手，可以帮助您分析发票、查询流水或生成报表。' }
])
const chatSessionId = ref<number | null>(null)
const showSessionList = ref(false)
const loadingSessions = ref(false)
interface ChatSessionItem { id: number; title: string; updated_at: string }
const chatSessions = ref<ChatSessionItem[]>([])

// Computed
const canUseModules = computed(() => !!currentProjectId.value && !!currentCompanyId.value)

const currentPageTitle = computed(() => {
  if (route.name === 'home' || route.name === 'company-dashboard' || route.name === 'project-dashboard') return '企业概览'
  if (route.name === 'module-invoice') return '发票智能分析'
  if (route.name === 'module-bank') return '银行流水核查'
  if (route.name === 'settings') return '系统设置'
  return '工作台'
})

const canShowMainView = computed(() => {
  if (route.name === 'settings') return true
  return !!(projectStore.currentProject && projectStore.currentCompany)
})

const agentStyle = computed((): any => {
  if (!agentOpen.value) return { width: '0px', padding: '0px', opacity: 0, pointerEvents: 'none' }
  if (agentFullscreen.value) {
    return {
      position: 'absolute',
      top: '0',
      left: '0',
      width: '100%',
      height: '100%',
      zIndex: 2000,
      background: 'rgba(0,0,0,0.6)',
      padding: '40px'
    }
  }
  return { width: `${agentWidth.value}px`, opacity: 1 }
})

// Lifecycle
onMounted(async () => {
  // 1. Theme
  const savedTheme = localStorage.getItem('theme') || 'light'
  setTheme(savedTheme)

  // 2. Fetch Projects
  await projectStore.fetchProjects()
  
  // 3. Auto-select logic
  if (projectStore.projects.length > 0) {
    // If URL has params, prioritize them
    const paramPid = Number(route.params.projectId)
    const paramCid = Number(route.params.companyId)

    if (paramPid) {
      currentProjectId.value = paramPid
      await projectStore.fetchProject(paramPid)
      
      if (paramCid) {
        currentCompanyId.value = paramCid
        await projectStore.fetchCompany(paramCid)
        projectStore.setCurrentCompany(projectStore.companies.find(c => c.id === paramCid) || null)
      } else if (projectStore.companies.length > 0) {
        // Auto select first company
        handleCompanyChange(projectStore.companies[0].id)
      }
    } else {
      // No params, select first project
      handleProjectChange(projectStore.projects[0].id)
    }
  }
})

watch([currentProjectId, currentCompanyId], async () => {
  if (currentProjectId.value && currentCompanyId.value) {
    await loadChatHistory()
  } else {
    resetChat()
  }
})

// Methods
const setTheme = (theme: string) => {
  currentTheme.value = theme
  document.documentElement.setAttribute('data-theme', theme)
  localStorage.setItem('theme', theme)
}

const toggleTheme = () => {
  const newTheme = currentTheme.value === 'dark' ? 'light' : 'dark'
  setTheme(newTheme)
}

const handleProjectChange = async (val: number) => {
  currentProjectId.value = val
  await projectStore.fetchProject(val)
  currentCompanyId.value = undefined
  
  if (projectStore.companies.length > 0) {
    handleCompanyChange(projectStore.companies[0].id)
  } else {
    // No companies, go to project root? or stay
    router.push(`/project/${val}`)
  }
}

const handleCompanyChange = async (val: number) => {
  currentCompanyId.value = val
  const comp = projectStore.companies.find(c => c.id === val)
  if (comp) projectStore.setCurrentCompany(comp)
  
  // If we are on root, go to home
  router.push(`/project/${currentProjectId.value}/company/${val}`)
}

const createNewProject = () => {
  showCreateProjectModal.value = true
}

const handleCreateProject = async () => {
  if (newProjectName.value) {
    const p = await projectStore.createProject(newProjectName.value, "New Project")
    showCreateProjectModal.value = false
    newProjectName.value = ''
    handleProjectChange(p.id)
  }
}

const navTo = (name: string) => {
  if (!canUseModules.value) return
  const pid = currentProjectId.value
  const cid = currentCompanyId.value
  
  if (name === 'home') router.push(`/project/${pid}/company/${cid}`)
  if (name === 'invoice') router.push(`/project/${pid}/company/${cid}/module/invoice`)
  if (name === 'bank') router.push(`/project/${pid}/company/${cid}/module/bank`)
}

const goSettings = () => {
  router.push('/settings')
}

const isRouteActive = (name: string) => {
  if (name === 'home' && route.name === 'company-dashboard') return true
  if (name === 'invoice' && route.name === 'module-invoice') return true
  if (name === 'bank' && route.name === 'module-bank') return true
  return false
}


const getChatSessionKey = () => {
  if (!currentProjectId.value || !currentCompanyId.value) return ''
  return `chat_session_${currentProjectId.value}_${currentCompanyId.value}`
}

const resetChat = () => {
  chatMessages.value = [
    { role: 'ai', content: '你好！我是 TabSis 智能助手，可以帮助您分析发票、查询流水或生成报表。' }
  ]
}

const loadChatHistory = async () => {
  const key = getChatSessionKey()
  if (!key) {
    resetChat()
    return
  }
  const saved = localStorage.getItem(key)
  if (!saved) {
    resetChat()
    return
  }
  const sessionId = Number(saved)
  if (!sessionId) {
    resetChat()
    return
  }
  const API_BASE = (import.meta.env.VITE_API_BASE_URL || '/api').trim() || '/api'
  try {
    const res = await axios.get(`${API_BASE}/chat-sessions/${sessionId}/messages`, { params: { limit: 50 } })
    const items = res.data?.messages || []
    if (items.length > 0) {
      chatSessionId.value = sessionId
      chatMessages.value = items.map((m: any) => ({
        role: m.role === 'assistant' ? 'ai' : 'user',
        content: m.content,
        widget: m.widget || null
      }))
    } else {
      resetChat()
    }
  } catch {
    resetChat()
  }
}

// ... existing agent/company methods ...
const toggleAgent = () => { agentOpen.value = !agentOpen.value }
const toggleFullscreen = () => { agentFullscreen.value = !agentFullscreen.value }
const startResize = (e: MouseEvent) => {
  const startX = e.clientX
  const startWidth = agentWidth.value
  const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value))
  const doDrag = (e: MouseEvent) => {
    const next = startWidth + (startX - e.clientX)
    agentWidth.value = clamp(next, 300, 720)
  }
  const stopDrag = () => { document.removeEventListener('mousemove', doDrag); document.removeEventListener('mouseup', stopDrag) }
  document.addEventListener('mousemove', doDrag); document.addEventListener('mouseup', stopDrag)
}

const handleAddCompany = async () => {
  if (!addCompanyForm.name) return message.warning('请输入名称')
  addingCompany.value = true
  try {
    const created = await projectStore.createCompany(currentProjectId.value!, addCompanyForm.name, addCompanyForm.taxId, addCompanyForm.background)
    message.success('已添加')
    showAddCompanyModal.value = false
    resetCompanyForm()
    handleCompanyChange(created.id)
  } catch (e) { message.error('失败') }
  finally { addingCompany.value = false }
}
const resetCompanyForm = () => { addCompanyForm.name = ''; addCompanyForm.taxId = ''; addCompanyForm.background = '' }
const getCompanyColor = (id: number) => ['#0056b3', '#6f42c1', '#28a745', '#dc3545'][id % 4]

const sendMessage = async () => {
  if (!inputMessage.value.trim() || isThinking.value) return
  const msg = inputMessage.value
  chatMessages.value.push({ role: 'user', content: msg })
  inputMessage.value = ''
  isThinking.value = true
  scrollToBottom()

  // 添加一个空的AI消息用于流式更新
  const aiMessageIndex = chatMessages.value.length
  chatMessages.value.push({ role: 'ai', content: '', widget: null })

  const updateAiMessage = (patch: Partial<ChatMessage>) => {
    const target = chatMessages.value[aiMessageIndex]
    if (!target) return
    Object.assign(target, patch)
  }


  try {
    const fd = new FormData()
    fd.append('message', msg)
    fd.append('project_id', String(currentProjectId.value || 0))
    fd.append('company_id', String(currentCompanyId.value || 0))
      if (chatSessionId.value) {
        fd.append('session_id', String(chatSessionId.value))
      }
    const API_BASE = (import.meta.env.VITE_API_BASE_URL || '/api').trim() || '/api'

    // 使用流式API
    const response = await fetch(`${API_BASE}/agent/chat/stream/with-history`, {
      method: 'POST',
      body: fd
    })

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }

    const reader = response.body?.getReader()
    const decoder = new TextDecoder()

    if (!reader) {
      throw new Error('No response body')
    }

    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6))

            if (data.type === 'session') {
              if (data.session_id) {
                chatSessionId.value = data.session_id
                const key = getChatSessionKey()
                if (key) localStorage.setItem(key, String(data.session_id))
              }
            } else if (data.type === 'thinking') {
              updateAiMessage({ content: data.content })
            } else if (data.type === 'content' || data.type === 'table') {
              updateAiMessage({ content: data.content })
              scrollToBottom()
            } else if (data.type === 'done') {
              updateAiMessage({ content: data.content })
              updateAiMessage({ widget: data.widget })
              isThinking.value = false
            } else if (data.type === 'error') {
              updateAiMessage({ content: data.content })
              isThinking.value = false
            }
          } catch (e) {
            // 忽略解析错误
          }
        }
      }
    }
  } catch (error) {
    // 流式失败，回退到普通API
    try {
      const fd = new FormData()
      fd.append('message', msg)
      fd.append('project_id', String(currentProjectId.value || 0))
      fd.append('company_id', String(currentCompanyId.value || 0))
      if (chatSessionId.value) {
        fd.append('session_id', String(chatSessionId.value))
      }
      const API_BASE = (import.meta.env.VITE_API_BASE_URL || '/api').trim() || '/api'
      const res = await axios.post(`${API_BASE}/agent/chat/with-history`, fd)
      updateAiMessage({ content: res.data.message })
      updateAiMessage({ widget: res.data.widget })
      if (res.data.session_id) {
        chatSessionId.value = res.data.session_id
        const key = getChatSessionKey()
        if (key) localStorage.setItem(key, String(res.data.session_id))
      }
    } catch {
      updateAiMessage({ content: '查询失败，请稍后重试' })
    }
  } finally {
    isThinking.value = false
    scrollToBottom()
  }
}
const scrollToBottom = () => nextTick(() => chatBody.value && (chatBody.value.scrollTop = chatBody.value.scrollHeight))

// 历史对话功能
const toggleSessionList = async () => {
  showSessionList.value = !showSessionList.value
  if (showSessionList.value) {
    await loadSessions()
  }
}

const loadSessions = async () => {
  if (!currentProjectId.value || !currentCompanyId.value) return
  loadingSessions.value = true
  try {
    const API_BASE = (import.meta.env.VITE_API_BASE_URL || '/api').trim() || '/api'
    const res = await axios.get(`${API_BASE}/projects/${currentProjectId.value}/companies/${currentCompanyId.value}/chat-sessions`)
    chatSessions.value = res.data?.sessions || []
  } catch {
    chatSessions.value = []
  } finally {
    loadingSessions.value = false
  }
}

const startNewChat = () => {
  chatSessionId.value = null
  const key = getChatSessionKey()
  if (key) localStorage.removeItem(key)
  resetChat()
  showSessionList.value = false
  message.success('已开启新对话')
}

const switchToSession = async (session: ChatSessionItem) => {
  chatSessionId.value = session.id
  const key = getChatSessionKey()
  if (key) localStorage.setItem(key, String(session.id))

  const API_BASE = (import.meta.env.VITE_API_BASE_URL || '/api').trim() || '/api'
  try {
    const res = await axios.get(`${API_BASE}/chat-sessions/${session.id}/messages`, { params: { limit: 50 } })
    const items = res.data?.messages || []
    if (items.length > 0) {
      chatMessages.value = items.map((m: any) => ({
        role: m.role === 'assistant' ? 'ai' : 'user',
        content: m.content,
        widget: m.widget || null
      }))
    } else {
      resetChat()
    }
  } catch {
    resetChat()
  }
  showSessionList.value = false
  scrollToBottom()
}

const deleteSession = async (sessionId: number) => {
  const API_BASE = (import.meta.env.VITE_API_BASE_URL || '/api').trim() || '/api'
  try {
    await axios.delete(`${API_BASE}/chat-sessions/${sessionId}`)
    chatSessions.value = chatSessions.value.filter(s => s.id !== sessionId)
    if (chatSessionId.value === sessionId) {
      startNewChat()
    }
    message.success('已删除')
  } catch {
    message.error('删除失败')
  }
}

const formatSessionTime = (dateStr: string) => {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  const now = new Date()
  const diff = now.getTime() - date.getTime()
  const days = Math.floor(diff / (1000 * 60 * 60 * 24))
  if (days === 0) {
    return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  } else if (days === 1) {
    return '昨天'
  } else if (days < 7) {
    return `${days}天前`
  } else {
    return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
  }
}
</script>

<style scoped>
.app-wrapper {
  display: flex;
  width: 100vw;
  height: 100vh;
  overflow: hidden;
  background: var(--bg-dark);
  color: var(--text-primary);
}

/* Sidebar */
.main-sidebar {
  width: 260px;
  background: var(--sidebar-bg);
  border-right: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  transition: all 0.3s;
}

.sidebar-header {
  height: 64px;
  display: flex;
  align-items: center;
  padding: 0 20px;
  border-bottom: 1px solid var(--border-color);
}

.logo-area {
  display: flex;
  align-items: center;
  gap: 12px;
}

.sidebar-logo {
  height: 32px;
  width: 32px;
}

.app-name {
  font-weight: 700;
  font-size: 16px;
  font-family: 'Orbitron', sans-serif;
  color: var(--text-primary);
}

.context-section {
  padding: 20px;
  border-bottom: 1px solid var(--border-color);
}

.context-label {
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: 8px;
  font-weight: 500;
}

.mt-3 { margin-top: 12px; }

.context-select {
  width: 100%;
}

.select-footer {
  padding: 8px 12px;
  cursor: pointer;
  border-top: 1px solid var(--border-color);
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--neon-blue);
  font-size: 13px;
}

.select-footer:hover {
  background: var(--card-hover-bg);
}

.nav-menu {
  flex: 1;
  padding: 20px 12px;
  overflow-y: auto;
}

.nav-label {
  padding: 0 12px;
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: 10px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  color: var(--text-secondary);
  transition: all 0.2s;
  font-weight: 500;
  font-size: 14px;
}

.nav-item:hover {
  background: var(--card-hover-bg);
  color: var(--text-primary);
}

.nav-item.active {
  background: var(--active-item-bg);
  color: var(--neon-blue);
}

.nav-item.disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.badge {
  margin-left: auto;
  font-size: 10px;
  background: var(--border-color);
  padding: 2px 6px;
  border-radius: 4px;
}

.sidebar-footer {
  padding: 16px;
  border-top: 1px solid var(--border-color);
}

.user-profile {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 12px;
  padding: 8px;
  border-radius: 8px;
  cursor: pointer;
}

.user-profile:hover {
  background: var(--card-hover-bg);
}

.avatar {
  width: 32px;
  height: 32px;
  background: var(--neon-purple);
  color: #fff;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
}

.user-info {
  flex: 1;
}

.user-info .name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.user-info .role {
  font-size: 11px;
  color: var(--text-secondary);
}

/* Content Area */
.content-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: var(--bg-dark);
  position: relative;
  min-width: 0;
  overflow: hidden;
}

.app-header {
  height: 64px;
  background: var(--glass-bg);
  border-bottom: 1px solid var(--border-color);
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 24px;
}

.page-title {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
}

.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.search-bar {
  display: flex;
  align-items: center;
  background: var(--card-hover-bg);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  padding: 6px 12px;
  width: 240px;
}

.search-bar input {
  border: none;
  background: transparent;
  outline: none;
  margin-left: 8px;
  font-size: 13px;
  color: var(--text-primary);
  flex: 1;
}

.search-icon {
  color: var(--text-secondary);
}

.kbd {
  font-size: 10px;
  color: var(--text-secondary);
  border: 1px solid var(--border-color);
  padding: 2px 4px;
  border-radius: 4px;
}

.icon-btn {
  background: transparent;
  border: none;
  cursor: pointer;
  color: var(--text-secondary);
  padding: 6px;
  border-radius: 6px;
}

.icon-btn:hover {
  background: var(--card-hover-bg);
  color: var(--text-primary);
}

.agent-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  background: transparent;
  border: 1px solid var(--border-color);
  padding: 6px 12px;
  border-radius: 6px;
  cursor: pointer;
  color: var(--text-secondary);
  transition: all 0.2s;
}

.agent-btn:hover, .agent-btn.active {
  border-color: var(--neon-blue);
  color: var(--neon-blue);
  background: rgba(0, 86, 179, 0.05);
}

.main-view {
  flex: 1;
  overflow: auto;
  padding: 24px;
  min-height: 0;
  min-width: 0;
}

.welcome-empty {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  text-align: center;
}

.empty-content h1 {
  margin: 20px 0 10px;
  color: var(--text-primary);
}

.empty-content p {
  color: var(--text-secondary);
  margin-bottom: 30px;
}

.logo-big img {
  width: 80px;
  opacity: 0.8;
}

/* Agent Drawer */
.agent-drawer {
  background: var(--glass-bg);
  border-left: 1px solid var(--border-color);
  display: flex;
  z-index: 100;
  transition: width 0.3s;
  flex: 0 0 auto;
  flex-shrink: 0;
  position: relative;
  min-width: 0;
}

.agent-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.agent-header {
  height: 64px;
  border-bottom: 1px solid var(--border-color);
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 20px;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 6px;
}

.agent-title {
  display: flex;
  align-items: center;
  gap: 12px;
}

.ai-avatar {
  width: 32px;
  height: 32px;
  background: var(--neon-blue);
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
}

.ai-info {
  display: flex;
  flex-direction: column;
}

.ai-info .name {
  font-weight: 600;
  font-size: 14px;
  color: var(--text-primary);
}

.ai-info .status {
  font-size: 11px;
  color: var(--neon-green);
}

.agent-body {
  flex: 1;
  padding: 20px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 16px;
  background: var(--bg-dark);
}

.chat-bubble {
  max-width: 85%;
  padding: 12px 16px;
  border-radius: 12px;
  font-size: 14px;
  line-height: 1.5;
}

.bubble-content :deep(p) {
  margin: 0 0 8px;
}

.bubble-content :deep(pre) {
  margin: 8px 0;
  padding: 10px 12px;
  background: #0f172a;
  color: #e2e8f0;
  border-radius: 8px;
  overflow-x: auto;
  font-size: 12px;
}

.bubble-content :deep(code) {
  background: rgba(15, 23, 42, 0.2);
  padding: 2px 4px;
  border-radius: 4px;
}

.bubble-content :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 8px 0;
  font-size: 12px;
}

.bubble-content :deep(th),
.bubble-content :deep(td) {
  border: 1px solid var(--border-color);
  padding: 6px 8px;
  text-align: left;
  vertical-align: top;
}

.bubble-content :deep(th) {
  background: rgba(0, 86, 179, 0.08);
}

.chat-bubble.ai {
  background: var(--glass-bg);
  border: 1px solid var(--border-color);
  color: var(--text-primary);
  border-top-left-radius: 2px;
}

.chat-bubble.user {
  background: var(--neon-blue);
  color: white;
  align-self: flex-end;
  border-top-right-radius: 2px;
}

.agent-footer {
  padding: 16px;
  border-top: 1px solid var(--border-color);
  background: var(--glass-bg);
}

.input-container {
  display: flex;
  gap: 8px;
  background: var(--bg-dark);
  padding: 8px;
  border-radius: 8px;
  border: 1px solid var(--border-color);
}

.input-container input {
  flex: 1;
  background: transparent;
  border: none;
  outline: none;
  font-size: 14px;
  color: var(--text-primary);
}

.send-btn {
  background: var(--neon-blue);
  color: white;
  border: none;
  border-radius: 6px;
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}

.resize-handle {
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 8px;
  cursor: col-resize;
  background: rgba(15, 23, 42, 0.08);
  z-index: 2;
}
.resize-handle:hover {
  background: rgba(0, 86, 179, 0.35);
}

/* Tool Steps UI */
.tool-steps {
  margin-bottom: 12px;
  border-radius: 8px;
  background: rgba(0, 86, 179, 0.05);
  padding: 8px;
  font-size: 12px;
}

.tool-step {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 6px 8px;
  border-radius: 6px;
  margin-bottom: 4px;
  background: var(--glass-bg);
  border: 1px solid var(--border-color);
}

.tool-step:last-child {
  margin-bottom: 0;
}

.tool-step.running {
  border-color: var(--neon-blue);
  background: rgba(0, 86, 179, 0.08);
}

.tool-step.success {
  border-color: var(--neon-green);
}

.tool-step.error {
  border-color: #dc3545;
}

.step-icon {
  width: 18px;
  height: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  font-size: 11px;
}

.tool-step.success .step-icon {
  color: var(--neon-green);
}

.tool-step.error .step-icon {
  color: #dc3545;
}

.spinner {
  width: 12px;
  height: 12px;
  border: 2px solid var(--border-color);
  border-top-color: var(--neon-blue);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.step-info {
  flex: 1;
  min-width: 0;
}

.step-name {
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 2px;
}

.step-content {
  color: var(--text-secondary);
  word-break: break-word;
}

.step-content :deep(p) {
  margin: 0;
}

.step-content :deep(pre) {
  margin: 4px 0;
  padding: 6px 8px;
  background: #0f172a;
  color: #e2e8f0;
  border-radius: 4px;
  font-size: 11px;
  overflow-x: auto;
}

.step-content :deep(code) {
  font-size: 11px;
}

/* Session List Panel */
.session-list-panel {
  position: absolute;
  top: 64px;
  left: 0;
  right: 0;
  bottom: 0;
  background: var(--bg-dark);
  z-index: 10;
  display: flex;
  flex-direction: column;
}

.session-list-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid var(--border-color);
  font-weight: 600;
  color: var(--text-primary);
}

.session-list-body {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.session-loading,
.session-empty {
  text-align: center;
  padding: 40px 20px;
  color: var(--text-secondary);
  font-size: 13px;
}

.session-item {
  position: relative;
  padding: 12px 14px;
  border-radius: 8px;
  cursor: pointer;
  margin-bottom: 4px;
  border: 1px solid transparent;
  transition: all 0.2s;
}

.session-item:hover {
  background: var(--card-hover-bg);
  border-color: var(--border-color);
}

.session-item.active {
  background: rgba(0, 86, 179, 0.1);
  border-color: var(--neon-blue);
}

.session-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
  margin-bottom: 4px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  padding-right: 24px;
}

.session-time {
  font-size: 11px;
  color: var(--text-secondary);
}

.session-delete {
  position: absolute;
  right: 10px;
  top: 50%;
  transform: translateY(-50%);
  background: transparent;
  border: none;
  color: var(--text-secondary);
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
  opacity: 0;
  transition: opacity 0.2s;
}

.session-item:hover .session-delete {
  opacity: 1;
}

.session-delete:hover {
  background: rgba(220, 53, 69, 0.1);
  color: #dc3545;
}
</style>
