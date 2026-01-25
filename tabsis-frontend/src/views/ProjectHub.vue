<!-- @ts-nocheck -->
<template>
  <div class="project-hub">
    <h1 class="hub-title">TabSis 项目中心</h1>
    <div class="project-grid">
      <div 
        v-for="p in projectStore.projects" 
        :key="p.id" 
        class="project-card"
        @click="openProject(p.id)"
      >
        <div class="card-icon">{{ p.name.substring(0, 2) }}</div>
        <div class="card-info">
          <h3>{{ p.name }}</h3>
          <p>{{ p.description || '无描述' }}</p>
        </div>
      </div>
      
      <div class="project-card new-card" @click="createProject">
        <div class="plus-icon">+</div>
        <h3>新建项目</h3>
      </div>
      <a-modal
        v-model:open="isModalVisible"
        title="新建项目"
        @ok="handleCreateProject"
      >
        <a-input v-model:value="newProjectName" placeholder="请输入项目名称" />
      </a-modal>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useProjectStore } from '../stores/projectStore'

const router = useRouter()
const projectStore = useProjectStore()
const isModalVisible = ref(false)
const newProjectName = ref('')

onMounted(() => {
  projectStore.fetchProjects()
})

const openProject = (id: number) => {
  router.push(`/project/${id}`)
}

const createProject = () => {
  isModalVisible.value = true
}

const handleCreateProject = async () => {
  if (newProjectName.value) {
    await projectStore.createProject(newProjectName.value, "New Project")
    isModalVisible.value = false
    newProjectName.value = ''
    // Refresh list
    await projectStore.fetchProjects()
  }
}
</script>


<style scoped>
.project-hub {
  padding: 50px;
  background: var(--bg-dark);
  min-height: 100vh;
  color: var(--text-primary);
}

.hub-title {
  font-size: 32px;
  margin-bottom: 40px;
  color: var(--neon-blue);
  text-shadow: var(--text-glow);
  font-family: 'Orbitron', sans-serif;
}

.project-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
  gap: 30px;
}

.project-card {
  background: var(--glass-bg);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  padding: 20px;
  cursor: pointer;
  transition: all 0.3s;
  display: flex;
  align-items: center;
}

.project-card:hover {
  transform: translateY(-5px);
  border-color: var(--neon-blue);
  box-shadow: 0 5px 20px rgba(0, 243, 255, 0.1);
  background: var(--card-hover-bg);
}

.card-icon {
  width: 50px;
  height: 50px;
  background: rgba(0, 0, 0, 0.2);
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  margin-right: 15px;
  color: var(--neon-blue);
  border: 1px solid var(--border-color);
}

.card-info h3 {
  margin: 0;
  color: var(--text-primary);
}

.card-info p {
  margin: 5px 0 0;
  color: var(--text-secondary);
  font-size: 12px;
}

.new-card {
  border-style: dashed;
  justify-content: center;
  flex-direction: column;
  background: transparent;
}

.new-card:hover {
  border-color: var(--neon-green);
  box-shadow: 0 5px 20px rgba(10, 255, 104, 0.1);
}

.plus-icon {
  font-size: 30px;
  color: var(--text-secondary);
  margin-bottom: 10px;
}
</style>
