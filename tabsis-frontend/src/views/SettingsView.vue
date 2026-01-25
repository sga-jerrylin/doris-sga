<template>
  <div class="settings-view">
    <div class="settings-header">
      <div>
        <h2>系统设置</h2>
        <p>按项目配置大模型与维护工具</p>
      </div>
    </div>

    <LLMConfig />
    <ProjectAgentPrompt />

    <a-card title="项目数据库维护">
      <div v-if="!currentProjectId" class="empty-tip">请先选择项目</div>
      <template v-else>
        <div class="reset-row">
          <div>
            <div class="reset-title">重置项目数据库</div>
            <div class="reset-desc">
              删除并重建该项目数据库，可选清空上传历史
            </div>
          </div>
          <div class="reset-actions">
            <a-switch v-model:checked="clearUploads" />
            <span class="switch-label">清空上传历史</span>
            <a-popconfirm
              title="该操作会清空此项目所有数据，确定继续？"
              @confirm="handleResetDb"
            >
              <a-button danger :loading="resetting">重置数据库</a-button>
            </a-popconfirm>
          </div>
        </div>
      </template>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { message } from 'ant-design-vue'
import LLMConfig from '../components/LLMConfig.vue'
import ProjectAgentPrompt from '../components/ProjectAgentPrompt.vue'
import { useProjectStore } from '../stores/projectStore'
import { dorisApi } from '../api/doris'

const projectStore = useProjectStore()
const currentProjectId = computed(() => projectStore.currentProject?.id)

const clearUploads = ref(true)
const resetting = ref(false)

const handleResetDb = async () => {
  if (!currentProjectId.value) return
  resetting.value = true
  try {
    const res = await dorisApi.resetProjectDb(currentProjectId.value, clearUploads.value)
    if (res.data?.doris_reset === false) {
      message.warning('已清空文件列表，但 Doris 未连接，库未清空：' + (res.data?.doris_error || ''))
    } else {
      message.success('项目数据库已重置')
    }
  } catch (err: any) {
    message.error('重置失败: ' + (err.response?.data?.detail?.error || err.message))
  } finally {
    resetting.value = false
  }
}
</script>

<style scoped>
.settings-view {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-width: 0;
}

.settings-header h2 {
  margin: 0 0 6px;
  color: var(--text-primary);
  font-size: 20px;
}

.settings-header p {
  margin: 0;
  color: var(--text-secondary);
  font-size: 13px;
}

.empty-tip {
  color: var(--text-secondary);
  font-size: 13px;
}

.reset-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.reset-title {
  font-weight: 600;
  color: var(--text-primary);
}

.reset-desc {
  color: var(--text-secondary);
  font-size: 13px;
  margin-top: 4px;
}

.reset-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.switch-label {
  font-size: 12px;
  color: var(--text-secondary);
}
</style>
