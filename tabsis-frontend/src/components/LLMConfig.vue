<template>
  <div class="llm-config">
    <a-card title="项目 LLM 配置">
      <div v-if="!currentProjectId" class="empty-tip">
        请先选择项目后再配置。
      </div>
      <template v-else>
        <a-form :model="formState" layout="vertical">
          <a-form-item label="厂商" required>
            <a-select v-model:value="formState.provider_type" placeholder="选择厂商" @change="handleProviderChange">
              <a-select-option value="openai">OpenAI</a-select-option>
              <a-select-option value="deepseek">DeepSeek</a-select-option>
              <a-select-option value="qwen">通义千问</a-select-option>
              <a-select-option value="zhipu">智谱</a-select-option>
              <a-select-option value="moonshot">Moonshot</a-select-option>
              <a-select-option value="baichuan">百川</a-select-option>
              <a-select-option value="minimax">MiniMax</a-select-option>
              <a-select-option value="local">本地 (Ollama)</a-select-option>
            </a-select>
          </a-form-item>

          <a-form-item label="API 端点" required>
            <a-input v-model:value="formState.endpoint" :placeholder="endpointPlaceholder" />
          </a-form-item>

          <a-form-item label="模型" required>
            <a-select
              v-if="useModelSelect"
              v-model:value="formState.model_name"
              placeholder="选择模型"
            >
              <a-select-option
                v-for="opt in modelOptions"
                :key="opt.value"
                :value="opt.value"
              >
                {{ opt.label }}
              </a-select-option>
            </a-select>
            <a-input v-else v-model:value="formState.model_name" placeholder="gpt-4 / deepseek-chat" />
          </a-form-item>

          <a-form-item label="API Key">
            <a-input-password v-model:value="formState.api_key" placeholder="sk-xxx" />
          </a-form-item>

          <a-row :gutter="16">
            <a-col :span="12">
              <a-form-item label="温度 (0-1)">
                <a-input-number v-model:value="formState.temperature" :min="0" :max="1" :step="0.1" style="width: 100%" />
              </a-form-item>
            </a-col>
            <a-col :span="12">
              <a-form-item label="最大 Tokens">
                <a-input-number v-model:value="formState.max_tokens" :min="1" :max="32000" style="width: 100%" />
              </a-form-item>
            </a-col>
          </a-row>
        </a-form>

        <div class="actions">
          <a-button type="primary" :loading="saving" @click="handleSave">保存</a-button>
          <a-button :loading="testing" @click="handleTest">测试连接</a-button>
          <a-popconfirm title="确认删除当前项目配置？" @confirm="handleDelete">
            <a-button danger>删除</a-button>
          </a-popconfirm>
          <a-button @click="loadConfig">刷新</a-button>
        </div>
      </template>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { message } from 'ant-design-vue'
import { dorisApi } from '../api/doris'
import { useProjectStore } from '../stores/projectStore'

const projectStore = useProjectStore()
const currentProjectId = computed(() => projectStore.currentProject?.id)

const saving = ref(false)
const testing = ref(false)
const endpointPlaceholder = ref('https://api.deepseek.com/chat/completions')

const formState = ref({
  provider_type: 'deepseek',
  endpoint: 'https://api.deepseek.com/chat/completions',
  model_name: 'deepseek-chat',
  api_key: '',
  temperature: undefined,
  max_tokens: undefined,
})

const providerEndpoints: Record<string, string> = {
  openai: 'https://api.openai.com/v1/chat/completions',
  deepseek: 'https://api.deepseek.com/chat/completions',
  qwen: 'https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions',
  zhipu: 'https://open.bigmodel.cn/api/paas/v4/chat/completions',
  moonshot: 'https://api.moonshot.cn/v1/chat/completions',
  baichuan: 'https://api.baichuan-ai.com/v1/chat/completions',
  minimax: 'https://api.minimax.chat/v1/text/chatcompletion_v2',
  local: 'http://localhost:11434/v1/chat/completions',
}

const providerModels: Record<string, { label: string; value: string }[]> = {
  deepseek: [
    { label: 'deepseek-chat', value: 'deepseek-chat' },
    { label: 'deepseek-reasoner', value: 'deepseek-reasoner' },
  ],
}

const modelOptions = computed(() => providerModels[formState.value.provider_type] || [])
const useModelSelect = computed(() => modelOptions.value.length > 0)

const handleProviderChange = (provider: string) => {
  if (providerEndpoints[provider]) {
    formState.value.endpoint = providerEndpoints[provider]
    endpointPlaceholder.value = providerEndpoints[provider]
  }
  if (providerModels[provider]?.length) {
    formState.value.model_name = providerModels[provider]?.[0]?.value || ''
  }
}

const loadConfig = async () => {
  if (!currentProjectId.value) return
  try {
    const res = await dorisApi.projectLlm.get(currentProjectId.value)
    const cfg = res.data.config
    if (cfg) {
      formState.value = {
        provider_type: cfg.provider_type,
        endpoint: cfg.endpoint,
        model_name: cfg.model_name,
        api_key: cfg.api_key || '',
        temperature: cfg.temperature ?? undefined,
        max_tokens: cfg.max_tokens ?? undefined,
      }
      endpointPlaceholder.value = cfg.endpoint || endpointPlaceholder.value
    } else {
      formState.value = {
        provider_type: 'deepseek',
        endpoint: providerEndpoints.deepseek || '',
        model_name: 'deepseek-chat',
        api_key: '',
        temperature: undefined,
        max_tokens: undefined,
      }
    }
  } catch (err: any) {
    message.error('加载失败: ' + (err.response?.data?.detail || err.message))
  }
}

const handleSave = async () => {
  if (!currentProjectId.value) return
  if (!formState.value.provider_type || !formState.value.endpoint || !formState.value.model_name) {
    message.warning('请填写必填项')
    return
  }
  try {
    testing.value = true
    await dorisApi.projectLlm.test(currentProjectId.value, formState.value)
    message.success('连接成功，正在保存')
  } catch (err: any) {
    message.error('连接失败: ' + (err.response?.data?.detail?.error || err.message))
    return
  } finally {
    testing.value = false
  }

  saving.value = true
  try {
    await dorisApi.projectLlm.save(currentProjectId.value, formState.value)
    message.success('保存成功')
  } catch (err: any) {
    message.error('保存失败: ' + (err.response?.data?.detail || err.message))
  } finally {
    saving.value = false
  }
}

const handleTest = async () => {
  if (!currentProjectId.value) return
  testing.value = true
  try {
    await dorisApi.projectLlm.test(currentProjectId.value, formState.value)
    message.success('连接成功')
  } catch (err: any) {
    message.error('连接失败: ' + (err.response?.data?.detail?.error || err.message))
  } finally {
    testing.value = false
  }
}

const handleDelete = async () => {
  if (!currentProjectId.value) return
  try {
    await dorisApi.projectLlm.delete(currentProjectId.value)
    message.success('删除成功')
    await loadConfig()
  } catch (err: any) {
    message.error('删除失败: ' + (err.response?.data?.detail || err.message))
  }
}

onMounted(loadConfig)
watch(currentProjectId, () => loadConfig())
</script>

<style scoped>
.llm-config {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.empty-tip {
  color: var(--text-secondary);
  font-size: 13px;
}

.actions {
  display: flex;
  gap: 8px;
  margin-top: 8px;
}
</style>
