<template>
  <a-card title="项目 Agent 提示词">
    <div v-if="!currentProjectId" class="empty-tip">
      请先选择项目后再配置。
    </div>
    <template v-else>
      <div class="hint">
        当前使用：<span class="source">{{ sourceLabel }}</span>
      </div>
      <a-textarea
        v-model:value="promptText"
        :rows="10"
        placeholder="请输入该项目的表姐提示词（保存后仅作用于当前项目）"
      />
      <div class="actions">
        <a-button type="primary" :loading="saving" @click="handleSave">保存</a-button>
        <a-popconfirm title="确认恢复为默认提示词？" @confirm="handleReset">
          <a-button>恢复默认</a-button>
        </a-popconfirm>
        <a-button :loading="loading" @click="loadPrompt">刷新</a-button>
      </div>
    </template>
  </a-card>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { message } from 'ant-design-vue'
import { dorisApi } from '../api/doris'
import { useProjectStore } from '../stores/projectStore'

const projectStore = useProjectStore()
const currentProjectId = computed(() => projectStore.currentProject?.id)

const promptText = ref('')
const source = ref<'project' | 'default'>('default')
const loading = ref(false)
const saving = ref(false)

const sourceLabel = computed(() => (source.value === 'project' ? '项目自定义' : '默认模板'))

const loadPrompt = async () => {
  if (!currentProjectId.value) return
  loading.value = true
  try {
    const res = await dorisApi.projectPrompt.get(currentProjectId.value)
    promptText.value = res.data?.prompt || ''
    source.value = res.data?.source === 'project' ? 'project' : 'default'
  } catch (err: any) {
    message.error('加载失败: ' + (err.response?.data?.detail || err.message))
  } finally {
    loading.value = false
  }
}

const handleSave = async () => {
  if (!currentProjectId.value) return
  const text = (promptText.value || '').trim()
  if (!text) {
    message.warning('提示词不能为空')
    return
  }
  saving.value = true
  try {
    const res = await dorisApi.projectPrompt.save(currentProjectId.value, text)
    promptText.value = res.data?.prompt || text
    source.value = 'project'
    message.success('保存成功')
  } catch (err: any) {
    message.error('保存失败: ' + (err.response?.data?.detail || err.message))
  } finally {
    saving.value = false
  }
}

const handleReset = async () => {
  if (!currentProjectId.value) return
  loading.value = true
  try {
    const res = await dorisApi.projectPrompt.reset(currentProjectId.value)
    promptText.value = res.data?.prompt || ''
    source.value = 'default'
    message.success('已恢复默认')
  } catch (err: any) {
    message.error('恢复失败: ' + (err.response?.data?.detail || err.message))
  } finally {
    loading.value = false
  }
}

onMounted(loadPrompt)
watch(currentProjectId, () => loadPrompt())
</script>

<style scoped>
.empty-tip {
  color: var(--text-secondary);
  font-size: 13px;
}

.hint {
  margin-bottom: 8px;
  font-size: 12px;
  color: var(--text-secondary);
}

.source {
  color: var(--neon-blue);
  font-weight: 600;
}

.actions {
  display: flex;
  gap: 8px;
  margin-top: 10px;
}
</style>
